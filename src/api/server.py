"""
Minimal HTTP API wrapping Confidant's Orchestrator -- the first way a
real person (rather than a CLI or a GitHub Actions workflow) can talk to
the pipeline. Scope is deliberately narrow: this proves the whole system
works end to end for one person having a real, persistent, multi-turn
conversation. It is not a production API (no auth, no multi-tenant
isolation beyond per-session SQLite rows, no rate limiting) -- see
engine/decisions.md for the full scope discussion.

Per-request shape mirrors conversation_runner.py exactly: load the
session's WorldState, call `run_turn`, then treat `result.state` as the
new truth regardless of whether a later stage failed (that's the entire
point of TurnResult's design -- see src/orchestrator/schema.py). Each
session gets its own UsageTracker so concurrent sessions' instrumentation
(if CONFIDANT_TRACK_USAGE is ever set) never mixes -- same reasoning
conversation_runner.py already documents for its own single tracker.

Judgment/Planner/Interpretation are never returned from the main
messages endpoint -- per this project's own governing principle, they
are internal cognitive artifacts, not user-facing (see
engine/specs/judgment-specification-v2.md, planner-specification-v1.md).
`/sessions/{id}/debug` exists solely as a developer/demo window into
them, mirroring what conversation_runner.py already prints to a
terminal -- it is not linked from the placeholder frontend's main flow.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Optional, Tuple

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from src.api import db
from src.api.email import send_magic_link_email
from src.api.schema import (
    AuthStatusOut,
    ClarityBriefResponse,
    CreateSessionRequest,
    CreateSessionResponse,
    InsightOut,
    LearnedPatternOut,
    MessageOut,
    ModeOut,
    PrivacySettingsOut,
    RequestMagicLinkRequest,
    RequestMagicLinkResponse,
    ResponseOptionOut,
    SendMessageRequest,
    SendMessageResponse,
    SessionSummary,
    SetBookmarkRequest,
    SetPrivacySettingsRequest,
    UnderstandingResponse,
    UnderstandingStatementOut,
    VerifyMagicLinkRequest,
)
from src.executor.engine import build_clarity_brief, render_clarity_brief
from src.executor.voice import to_second_person
from src.insight.schema import Insight
from src.instrumentation.usage import UsageTracker
from src.judgment.schema import Judgment
from src.learning.engine import Pattern
from src.need_state.engine import infer_need_state
from src.orchestrator.engine import run_turn
from src.orchestrator.modes import MODE_COPY
from src.planner.schema import Planner
from src.pom.schema import PersonalOperatingModel
from src.retrieval.engine import build_retrieved_context
from src.state.world_state import WorldState

# Real frontend (see frontend/decisions.md "Build the real Confidant
# frontend") -- Svelte + Vite, built via `npm run build` in
# frontend/app/, mounted from its static output. frontend/mvp/ is kept
# in the repo as historical record (same treatment frontend/prototype/
# already got), no longer served.
_FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "app" / "dist"


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncIterator[None]:
    db.init_db()
    yield


app = FastAPI(title="Confidant MVP API", lifespan=_lifespan)

# Correlates GET /sessions/{id}/stream (below) with the POST
# /sessions/{id}/messages that's actually running the turn -- see
# engine/decisions.md "Major update" Part 5. In-process only, consistent
# with this module's own documented scope ("no multi-tenant isolation
# beyond per-session rows"); a session is only ever open in one browser
# tab against one server process today. Populated when a stream client
# connects, drained and removed by that same request's generator when
# the stream ends -- send_message only ever pushes into a queue that
# already exists, never creates one itself.
#
# asyncio.Queue + the event loop that owns it, NOT queue.Queue: a plain
# queue.Queue().get() blocking inside a threadpool-run sync generator
# cannot be cancelled when a client disconnects (a real blocking OS-level
# call ignores asyncio cancellation, which only works at await points) --
# an early first draft of this leaked one non-daemon threadpool worker
# thread, stuck retrying forever, per every abandoned/disconnected
# stream (caught by this file's own new test hanging the test process on
# a failure path -- a real production reliability bug, not just a test
# artifact, since a Fly.io deployment runs indefinitely). send_message
# runs as a plain `def` in a worker thread, not on the event loop, so it
# must push via loop.call_soon_threadsafe rather than put_nowait directly.
_stage_queues: dict[str, Tuple[asyncio.Queue, asyncio.AbstractEventLoop]] = {}


# Basic auth (2026-07-18, see engine/decisions.md, frontend/decisions.md
# "Auth, the low-friction way") -- two cookies, one per identity a
# request can carry. `_ANON_COOKIE` is minted by this server the first
# time ANY browser shows up with neither cookie set (see
# `resolve_identity` below) -- it exists purely so Journeys begun before
# signing up have a stable owner to be scoped by and later claimed onto
# an account (db.claim_anonymous_sessions). `_SESSION_COOKIE` only
# exists once a magic link has actually been clicked. `SameSite=Lax` +
# `httponly` on the session cookie (never on the anon one, which the
# frontend never needs to read directly either, but there's no reason
# to withhold the same protections) -- `secure` is deliberately NOT
# hardcoded here: Fly.io terminates TLS in front of this app, so from
# uvicorn's own point of view every request already looks like plain
# HTTP, and marking cookies `secure` unconditionally would silently
# break local `http://localhost` dev entirely.
_ANON_COOKIE = "confidant_anon_id"
_SESSION_COOKIE = "confidant_session"
_ANON_COOKIE_MAX_AGE = int(db.AUTH_SESSION_LIFETIME.total_seconds())
_SESSION_COOKIE_MAX_AGE = int(db.AUTH_SESSION_LIFETIME.total_seconds())

# How many responses an anonymous visitor gets in ONE conversation
# before being asked to log in to continue it (direct founder framing:
# "continue A conversation beyond a certain number of responses" -- a
# per-Journey cap, not a cumulative one across every anonymous Journey a
# browser has ever started). Counted as prior USER messages already in
# the session, so exactly this many turns complete for free before the
# next attempt is blocked.
ANONYMOUS_MESSAGE_LIMIT = 10


@dataclass
class Identity:
    """Whichever of the two a request resolves to -- see
    `resolve_identity`. Never both at once by construction: a request
    carrying a valid session cookie is always treated as that user,
    full stop, regardless of whatever stale anon cookie also happens to
    be sitting in the same browser."""

    user_id: Optional[str]
    anonymous_id: Optional[str]

    @property
    def is_authenticated(self) -> bool:
        return self.user_id is not None


def resolve_identity(request: Request, response: Response) -> Identity:
    """The one place a request's identity is decided -- every
    session-scoped endpoint below depends on this rather than reading
    cookies itself. A valid `_SESSION_COOKIE` wins outright. Otherwise,
    an existing `_ANON_COOKIE` is reused; a browser with neither gets a
    freshly minted one set on `response` right here (the same `Response`
    object FastAPI hands to the eventual route, so this Set-Cookie
    reaches the client even though this function never returns a
    Response itself)."""
    session_token = request.cookies.get(_SESSION_COOKIE)
    if session_token:
        user_id = db.get_user_id_for_auth_session(session_token)
        if user_id is not None:
            return Identity(user_id=user_id, anonymous_id=None)

    anonymous_id = request.cookies.get(_ANON_COOKIE)
    if not anonymous_id:
        anonymous_id = str(uuid.uuid4())
        response.set_cookie(
            _ANON_COOKIE, anonymous_id, max_age=_ANON_COOKIE_MAX_AGE,
            httponly=True, samesite="lax",
        )
    return Identity(user_id=None, anonymous_id=anonymous_id)


def require_user(identity: Identity = Depends(resolve_identity)) -> str:
    """Guards Settings/Privacy endpoints (see engine/decisions.md) --
    `detail="login_required"` is a stable string the frontend checks
    for (see lib/api.js), not just prose for a human reading the
    response."""
    if identity.user_id is None:
        raise HTTPException(status_code=401, detail="login_required")
    return identity.user_id


def _require_owned_session(session_id: str, identity: Identity) -> None:
    """Existence AND ownership -- returning 404 (never 403) either way,
    so a session_id belonging to someone else reveals nothing about
    whether it exists at all. A session with neither owner column set
    (created before this feature existed -- see src/api/db.py's own
    module docstring) matches no identity and 404s for everyone,
    including whoever was using it before auth existed; there is no
    "claim a legacy session" flow, a deliberate, documented consequence
    of introducing ownership after the fact rather than a silent gap."""
    owner = db.session_owner(session_id)
    if owner is None:
        raise HTTPException(status_code=404, detail=f"No session {session_id!r}")
    owner_user_id, owner_anonymous_id = owner
    owned = (
        (identity.user_id is not None and identity.user_id == owner_user_id)
        or (identity.user_id is None and identity.anonymous_id == owner_anonymous_id)
    )
    if not owned:
        raise HTTPException(status_code=404, detail=f"No session {session_id!r}")


@app.post("/sessions", response_model=CreateSessionResponse)
def create_session(
    body: CreateSessionRequest = CreateSessionRequest(),
    identity: Identity = Depends(resolve_identity),
) -> CreateSessionResponse:
    return CreateSessionResponse(
        id=db.create_session(mode=body.mode, user_id=identity.user_id, anonymous_id=identity.anonymous_id)
    )


@app.get("/modes", response_model=list[ModeOut])
def list_modes() -> list[ModeOut]:
    """Backs the mode-select screen shown before a new Journey begins
    (see frontend/app/src/screens/ModeSelect.svelte, engine/decisions.md
    "Counseling modes") -- never session-scoped, so no `_require_owned_session`
    guard, unlike every other endpoint in this file."""
    return [ModeOut(id=mode_id, **copy) for mode_id, copy in MODE_COPY.items()]


@app.get("/sessions", response_model=list[SessionSummary])
def list_sessions(
    bookmarked_only: bool = False, identity: Identity = Depends(resolve_identity)
) -> list[SessionSummary]:
    """Backs the real frontend's Home screen (a list of a person's
    Journeys) -- see frontend/decisions.md "Build the real Confidant
    frontend". `bookmarked_only` backs Home's All/Bookmarked filter
    (added for the Home redesign, see frontend/decisions.md). Scoped to
    the caller's own identity (basic auth, see engine/decisions.md) --
    this is the endpoint that used to return literally every Journey in
    the database to every visitor."""
    return db.list_sessions(
        bookmarked_only=bookmarked_only, user_id=identity.user_id, anonymous_id=identity.anonymous_id
    )


@app.post("/sessions/{session_id}/bookmark", response_model=SetBookmarkRequest)
def set_bookmark(
    session_id: str,
    body: SetBookmarkRequest,
    identity: Identity = Depends(resolve_identity),
    user_id: str = Depends(require_user),
) -> SetBookmarkRequest:
    """Added for the Home redesign (see frontend/decisions.md) -- returns
    the same shape back so the frontend can update optimistically without
    a second round trip to re-fetch the session list.

    Gated behind `require_user` (basic auth, see engine/decisions.md
    "Auth, the low-friction way") -- direct founder follow-up: bookmark
    and delete are login-required actions too, not just Settings/Privacy
    and the response cap. `identity` is still needed alongside `user_id`
    for the ownership check below -- `require_user` only proves SOME
    account is signed in, not that it owns THIS session."""
    _require_owned_session(session_id, identity)
    db.set_bookmark(session_id, body.bookmarked)
    return body


@app.get("/sessions/{session_id}/bookmark", response_model=SetBookmarkRequest)
def get_bookmark(session_id: str, identity: Identity = Depends(resolve_identity)) -> SetBookmarkRequest:
    """Added for Journey's own overflow menu (see frontend/decisions.md
    "Tuck destructive/secondary Journey actions behind an overflow
    menu") -- Journey.svelte never fetches the full session list the
    way Home does, so it has no other way to know this session's
    current bookmark state before rendering the toggle. Same response
    shape as the existing POST, reused rather than duplicated.

    Deliberately NOT behind `require_user`, unlike the POST right above
    -- this is a read of a Journey a caller already owns (still gated
    by `_require_owned_session`), not the login-required ACTION of
    changing it. Journey.svelte's own onMount depends on this
    succeeding for every visitor, logged in or not, just to render the
    current (possibly-false) toggle state correctly."""
    _require_owned_session(session_id, identity)
    return SetBookmarkRequest(bookmarked=db.get_bookmark(session_id))


@app.delete("/sessions/{session_id}", status_code=204)
def delete_session(
    session_id: str,
    identity: Identity = Depends(resolve_identity),
    user_id: str = Depends(require_user),
) -> None:
    """Added for Settings' Data section (see engine/decisions.md
    "Frontend UX pass") -- removes a Journey and every row that
    references it (see db.delete_session's own docstring for exactly
    what that means for insight_sessions specifically). Irreversible,
    same as any real delete -- no soft-delete/undo exists yet.

    Gated behind `require_user` (basic auth, see engine/decisions.md
    "Auth, the low-friction way") -- same follow-up as set_bookmark
    above: an irreversible action deserves at least as much protection
    as a reversible one."""
    _require_owned_session(session_id, identity)
    db.delete_session(session_id)


@app.get("/sessions/{session_id}/messages", response_model=list[MessageOut])
def list_messages(session_id: str, identity: Identity = Depends(resolve_identity)) -> list[MessageOut]:
    _require_owned_session(session_id, identity)
    return db.get_messages(session_id)


@app.get("/sessions/{session_id}/stream")
async def stream_stages(
    session_id: str, identity: Identity = Depends(resolve_identity)
) -> StreamingResponse:
    """Server-Sent Events -- one `{"stage": "<internal_id>"}` event per
    pipeline stage that finishes during the turn this session's next
    POST /messages runs (see src/orchestrator/engine.py's on_stage_complete,
    engine/decisions.md "Major update" Part 5). Payload is deliberately
    minimal -- no elapsed_ms, no ordinal/total -- a total stage count
    can't be known upfront (a turn can fail after 1 stage or complete
    after 4), and anything enabling "n of estimated total" would be a
    latent progress bar (see frontend/specs/motion-and-latency-philosophy-v1.md).
    A `: keepalive` comment every ~10s of silence keeps the connection
    alive through the Fly.io edge proxy's idle timeout without meaning
    anything itself -- SSE comments are invisible to EventSource
    listeners. The frontend is expected to open this BEFORE POSTing; a
    POST with no open stream still runs the turn correctly, it's just
    silent (on_stage_complete's callback is a no-op when nothing is
    listening).

    async def + asyncio.Queue, not a sync generator over queue.Queue --
    see _stage_queues' own docstring for why the sync version was a
    real thread-leak bug, not just a style choice."""
    _require_owned_session(session_id, identity)
    stage_queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()
    entry = (stage_queue, loop)
    _stage_queues[session_id] = entry

    async def _events() -> AsyncIterator[str]:
        try:
            while True:
                try:
                    stage = await asyncio.wait_for(stage_queue.get(), timeout=10)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                if stage is None:  # sentinel from send_message: turn finished
                    break
                yield f"data: {json.dumps({'stage': stage})}\n\n"
        finally:
            # Only remove if it's still this connection's own queue --
            # a second stream open (e.g. a page reload) may already have
            # replaced it. Also runs on client disconnect (asyncio
            # cancels this generator at its next await point, unlike the
            # blocking-thread version this replaced).
            if _stage_queues.get(session_id) == entry:
                del _stage_queues[session_id]

    return StreamingResponse(_events(), media_type="text/event-stream")


@app.post("/sessions/{session_id}/messages", response_model=SendMessageResponse)
def send_message(
    session_id: str, body: SendMessageRequest, identity: Identity = Depends(resolve_identity)
) -> SendMessageResponse:
    _require_owned_session(session_id, identity)

    # Basic auth's response-limit gate (see ANONYMOUS_MESSAGE_LIMIT's own
    # docstring above) -- checked BEFORE running the turn, so a blocked
    # message never reaches the LLM at all. Only ever applies to an
    # anonymous caller; a signed-in user's own session (which
    # `_require_owned_session` above already confirmed they own) has no
    # cap. `detail="response_limit_reached"` is a stable string the
    # frontend checks for (see lib/api.js) to show a login prompt
    # instead of a generic error.
    if not identity.is_authenticated:
        prior_user_messages = sum(1 for m in db.get_messages(session_id) if m.role == "user")
        if prior_user_messages >= ANONYMOUS_MESSAGE_LIMIT:
            raise HTTPException(status_code=401, detail="response_limit_reached")

    state = db.load_state(session_id)
    tracker = UsageTracker()  # per-session, never the shared default -- see module docstring
    stream_entry = _stage_queues.get(session_id)

    # Runs as a plain `def` route, i.e. in a worker thread, not on the
    # event loop that owns stage_queue -- asyncio.Queue isn't
    # thread-safe, so this must hand off via call_soon_threadsafe rather
    # than calling put_nowait directly from this thread.
    def _push(stage: Optional[str]) -> None:
        if stream_entry is not None:
            stage_queue, loop = stream_entry
            loop.call_soon_threadsafe(stage_queue.put_nowait, stage)

    # Retrieval v1 (see src/retrieval/engine.py, engine/decisions.md
    # "Retrieval") -- Learning/Insight Engine already compute these
    # offline, into the learned_patterns/insights tables; this is the
    # first live turn that actually reads them back. Converts the API's
    # own LearnedPatternOut/InsightOut rows into the engine-internal
    # Pattern/Insight types build_retrieved_context expects, keeping the
    # src.api -> engine dependency direction (engine packages never
    # import from src.api).
    #
    # Privacy, made real (2026-07-18, see frontend/decisions.md) --
    # gated behind cross_session_learning_enabled: when a person has
    # opted out, this live turn only ever sees THIS session's own
    # WorldState (already loaded above), never anything Learning/Insight
    # Engine/POM have inferred about them across other Journeys. The
    # in-session experience (Interpretation/Judgment/Planner/Response,
    # this session's own history) is completely unaffected either way.
    if db.get_cross_session_learning_enabled():
        patterns = [
            Pattern(pattern_type=p.pattern_type, detail=p.detail, evidence_count=p.evidence_count)
            for p in db.get_learned_patterns()
        ]
        insights = [
            Insight(theme=i.theme, detail=i.detail, evidence_session_ids=i.evidence_session_ids)
            for i in db.get_insights()
        ]
        # Personal Operating Model (see src/pom/engine.py,
        # engine/decisions.md "Personal Operating Model") -- a cheap,
        # read-only DB read of whatever scripts/run_pom_computation.py
        # last computed offline; never computed live. None until that
        # script has run at least once for THIS account. POM made
        # per-user (2026-07-18, see engine/decisions.md "POM made
        # per-user") -- an anonymous caller has no stable account to
        # own a standing profile, so they get None here regardless of
        # whether any account's POM has ever been computed; a signed-in
        # caller only ever sees their own.
        pom = db.get_personal_operating_model(identity.user_id) if identity.user_id else None
    else:
        patterns, insights, pom = [], [], None
    # Need State Inference v1 (see src/need_state/engine.py,
    # engine/decisions.md "Need State Inference") -- must run on the
    # PRE-turn `state` (loaded above), since it has to be ready before
    # Retrieval, which feeds Judgment before this turn's own
    # Interpretation has even run. Scoped entirely to THIS session's own
    # state, not cross-session, so it's unaffected by the opt-out above.
    need_state = infer_need_state(state)
    retrieved_context = build_retrieved_context(patterns, insights, need_state=need_state, pom=pom)

    result = run_turn(
        body.content, state, tracker=tracker, session_id=session_id,
        on_stage_complete=_push, mode=db.get_session_mode(session_id),
        retrieved_context=retrieved_context,
    )
    _push(None)  # sentinel: closes the GET /stream connection above

    db.append_message(session_id, "user", body.content)
    db.save_turn_result(session_id, result)
    db.save_events(session_id, result.behavioral_events)

    response_text = result.response.response_text if result.response else None
    confidence = result.response.confidence if result.response else None
    options = (
        [ResponseOptionOut(label=o.label, description=o.description) for o in result.response.options]
        if result.response
        else []
    )
    if response_text is not None:
        db.append_message(
            session_id, "assistant", response_text,
            options=[o.model_dump() for o in options],
        )

    return SendMessageResponse(
        response_text=response_text,
        confidence=confidence,
        options=options,
        failed_stage=result.failed_stage,
        error=result.error,
    )


@app.get("/sessions/{session_id}/debug")
def get_debug(session_id: str, identity: Identity = Depends(resolve_identity)) -> dict:
    _require_owned_session(session_id, identity)
    return db.load_debug(session_id) or {}


@app.get("/sessions/{session_id}/clarity-brief", response_model=ClarityBriefResponse)
def get_clarity_brief(
    session_id: str, identity: Identity = Depends(resolve_identity)
) -> ClarityBriefResponse:
    """Unlike /debug, this is meant to be shown to the actual user -- see
    src/api/schema.py's ClarityBriefResponse docstring. 404s until at
    least one turn has completed Judgment and Planner (a turn that failed
    before those stages has nothing to build a brief from yet)."""
    _require_owned_session(session_id, identity)
    debug = db.load_debug(session_id)
    if not debug or not debug.get("judgment") or not debug.get("planner"):
        raise HTTPException(status_code=404, detail="Nothing to summarize yet")

    state = WorldState.model_validate(debug["state"])
    judgment = Judgment.model_validate(debug["judgment"])
    planner = Planner.model_validate(debug["planner"])
    # Added 2026-07-15 (see engine/decisions.md "Frontend UX pass"): the
    # last real user message, so build_clarity_brief can suppress
    # `situation` when it's just an echo of what the person literally
    # just said -- see that function's own docstring for why.
    messages = db.get_messages(session_id)
    last_user_message = next((m.content for m in reversed(messages) if m.role == "user"), "")
    brief = build_clarity_brief(state, judgment, planner, last_user_message=last_user_message)

    # secondary_issues/stagnation_notes bypass build_clarity_brief's
    # mapping (they're not part of Executor's documented template -- see
    # ClarityBriefResponse's own docstring), but they're just as
    # user-facing as everything build_clarity_brief does cover, so they
    # need the same voice.py rewrite applied here directly (see
    # engine/decisions.md "Major update" -- Understanding.svelte renders
    # both as plain asides, unmodified, same as every other brief field).
    return ClarityBriefResponse(
        **brief.model_dump(),
        rendered_markdown=render_clarity_brief(brief),
        secondary_issues=[to_second_person(s) for s in judgment.secondary_issues],
        stagnation_notes=[to_second_person(s) for s in judgment.stagnation_notes],
    )


@app.get("/sessions/{session_id}/understanding", response_model=UnderstandingResponse)
def get_understanding(
    session_id: str, identity: Identity = Depends(resolve_identity)
) -> UnderstandingResponse:
    """Unlike /clarity-brief, this never 404s -- Tier 1
    (src/understanding/engine.py::build_tier1_statements) is computed
    unconditionally every turn (src/orchestrator/engine.py::run_turn),
    so even a brand-new session's first turn has SOME content. An empty
    tier1/tier2 list (e.g. before any turn has completed) is a valid,
    correct response -- nothing understood yet, not an error."""
    _require_owned_session(session_id, identity)
    state = db.load_state(session_id)
    return UnderstandingResponse(
        tier1=[UnderstandingStatementOut(**s.model_dump()) for s in state.understanding.tier1],
        tier2=[UnderstandingStatementOut(**s.model_dump()) for s in state.understanding.tier2],
    )


@app.get("/patterns", response_model=list[LearnedPatternOut])
def get_patterns() -> list[LearnedPatternOut]:
    """Phase 1 Learning's output (see engine/specs/architecture-roadmap-v1.md).
    Read-only -- serves whatever scripts/run_learning.py last computed
    offline; never computes anything live. Empty until that script has
    been run at least once, and stays empty below its evidence floor --
    both correct, not an error state. Not yet consumed by the frontend:
    the exact "something noticed across Journeys" surfacing form is its
    own, separate, not-yet-done design pass (see
    frontend/specs/interaction-model-v4.md)."""
    return db.get_learned_patterns()


@app.get("/insights", response_model=list[InsightOut])
def get_insights() -> list[InsightOut]:
    """The cross-session Insight Engine's output (see src/insight/engine.py,
    engine/decisions.md "Major update"). Read-only -- serves whatever
    scripts/run_insight_detection.py last computed offline; never
    computes anything live. Empty until that script has been run at
    least once, and stays empty below MIN_EVIDENCE_SESSIONS -- both
    correct, not an error state. Unlike /patterns, this IS consumed by
    the frontend (Home.svelte session cards), so its theme text is real,
    already-grounded content, not raw internal cognition."""
    return db.get_insights()


@app.get("/personal-operating-model", response_model=Optional[PersonalOperatingModel])
def get_personal_operating_model(user_id: str = Depends(require_user)) -> Optional[PersonalOperatingModel]:
    """Personal Operating Model's own output (see src/pom/engine.py,
    engine/decisions.md "Personal Operating Model"). Read-only -- serves
    whatever scripts/run_pom_computation.py last computed offline; never
    computes anything live. Returns null (not a 404) until that script
    has been run at least once -- a brand-new deployment has no POM yet,
    a correct state, not an error. Returned as the actual internal
    PersonalOperatingModel type directly, unlike /patterns'/insights'
    "Out" mirror types -- POM is stored and read back as one whole JSON
    blob (src/api/db.py::get_personal_operating_model), never assembled
    field-by-field from separate SQL columns, so a separate mirror type
    would just copy identical fields with no actual decoupling benefit.

    Gated behind `require_user` (2026-07-18, basic auth, see
    engine/decisions.md "POM surfaced to users") -- POM is now real,
    consumed content inside the already-login-gated Settings screen
    (`frontend/app/src/components/PersonalOperatingModel.svelte`), so
    it gets the same protection the four Privacy endpoints already
    have, matching this codebase's own "gate the action, not just hide
    the button" discipline.

    POM made per-user (2026-07-18, see engine/decisions.md "POM made
    per-user") -- `require_user`'s own `user_id` is passed straight
    through, so each account only ever sees its own standing profile,
    never another account's."""
    return db.get_personal_operating_model(user_id)


@app.get("/privacy/settings", response_model=PrivacySettingsOut)
def get_privacy_settings(user_id: str = Depends(require_user)) -> PrivacySettingsOut:
    """Privacy, made real (2026-07-18, see frontend/decisions.md) --
    backs Settings' Privacy card. See src/api/db.py's `privacy_settings`
    table docstring for exactly what `cross_session_learning_enabled`
    gates.

    Gated behind `require_user` (basic auth, see engine/decisions.md
    "Auth, the low-friction way") -- direct founder request: Settings
    and Privacy need a login. NOTE this gates ACCESS only; the
    underlying `privacy_settings` row is still the single, global
    singleton it already was (see src/api/db.py's own docstring on
    that table) -- it is not yet split per-account, so today every
    signed-in visitor shares the same setting. POM made per-user
    (2026-07-18, see engine/decisions.md "POM made per-user") is no
    longer part of this carve-out -- only `privacy_settings` itself and
    the cross-account `learned_patterns`/`insights` models remain
    global. Making `privacy_settings` genuinely per-account is a real,
    separate project, flagged here rather than silently assumed away."""
    return PrivacySettingsOut(cross_session_learning_enabled=db.get_cross_session_learning_enabled())


@app.post("/privacy/settings", response_model=PrivacySettingsOut)
def set_privacy_settings(
    body: SetPrivacySettingsRequest, user_id: str = Depends(require_user)
) -> PrivacySettingsOut:
    db.set_cross_session_learning_enabled(body.cross_session_learning_enabled)
    return PrivacySettingsOut(cross_session_learning_enabled=body.cross_session_learning_enabled)


@app.get("/privacy/export")
def export_privacy_data(user_id: str = Depends(require_user)) -> Response:
    """Everything Confidant has ever stored about this person, as one
    downloadable JSON file (see src/api/db.py::export_all_data's own
    docstring for exactly what's included). A plain `Response` with an
    explicit Content-Disposition rather than `response_model` -- this
    is a file download, not a typed API resource a frontend consumes
    programmatically.

    Scoped to `user_id` (2026-07-18, see engine/decisions.md "POM made
    per-user" -- the same round also fixed this endpoint): every
    user-facing surface in this app shows one account's own data only,
    never a cross-account or global view (that's reserved for a
    separate, internal-only founder dashboard, not this API)."""
    payload = json.dumps(db.export_all_data(user_id), indent=2)
    return Response(
        content=payload,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=confidant-export.json"},
    )


@app.post("/privacy/reset", status_code=204)
def reset_privacy_data(user_id: str = Depends(require_user)) -> None:
    """"Forget everything" -- irreversible (see
    src/api/db.py::reset_all_data's own docstring). Deliberately no
    request body/confirmation param here: the frontend's own two-step
    confirm (same pattern as Settings' existing per-Journey delete) is
    where the "are you sure" lives, matching every other destructive
    action in this API (DELETE /sessions/{id} has no confirmation
    param either).

    Scoped to `user_id` (2026-07-18, see engine/decisions.md "POM made
    per-user" -- the same round also fixed this endpoint): deletes only
    this account's own Journeys, never another account's."""
    db.reset_all_data(user_id)


@app.post("/auth/request-link", response_model=RequestMagicLinkResponse)
def request_magic_link(
    body: RequestMagicLinkRequest, request: Request, identity: Identity = Depends(resolve_identity)
) -> RequestMagicLinkResponse:
    """Low-friction signup/login (see engine/decisions.md "Auth, the
    low-friction way"): there's no separate "create an account" step --
    requesting a link for an email that's never been seen creates the
    account right here, deferred until the link is actually clicked
    (`get_or_create_user` isn't called until /auth/verify, so an
    unclicked link never litters the users table with an unverified
    row). Always returns `sent: true` regardless of anything about the
    email -- never reveals whether it matched an existing account,
    same email-enumeration defense every real auth system needs.
    `identity.anonymous_id` (this browser's own, minted by
    `resolve_identity` if it didn't already have one) rides along on
    the token so /auth/verify can claim this browser's anonymous
    Journeys onto the account once the link is clicked."""
    token = db.create_magic_link(body.email, anonymous_id=identity.anonymous_id)
    origin = str(request.base_url).rstrip("/")
    send_magic_link_email(body.email, f"{origin}/?token={token}")
    return RequestMagicLinkResponse(sent=True)


@app.post("/auth/verify", response_model=AuthStatusOut)
def verify_magic_link(body: VerifyMagicLinkRequest, response: Response) -> AuthStatusOut:
    """Exchanges a clicked magic-link token for a real, httpOnly session
    cookie -- see db.consume_magic_link's own docstring for why an
    invalid/expired/already-used token all collapse into the same 404
    here rather than telling the caller which. Claims this browser's
    prior anonymous Journeys onto the account in the same request
    (db.claim_anonymous_sessions) -- signing up must not cost a person
    the Journey they were already in the middle of."""
    consumed = db.consume_magic_link(body.token)
    if consumed is None:
        raise HTTPException(status_code=404, detail="That link isn't valid. Request a new one.")
    email, anonymous_id = consumed
    user_id = db.get_or_create_user(email)
    if anonymous_id:
        db.claim_anonymous_sessions(anonymous_id, user_id)
    session_token = db.create_auth_session(user_id)
    response.set_cookie(
        _SESSION_COOKIE, session_token, max_age=_SESSION_COOKIE_MAX_AGE,
        httponly=True, samesite="lax",
    )
    return AuthStatusOut(authenticated=True, email=email)


@app.post("/auth/logout", status_code=204)
def logout(request: Request, response: Response) -> None:
    session_token = request.cookies.get(_SESSION_COOKIE)
    if session_token:
        db.delete_auth_session(session_token)
    response.delete_cookie(_SESSION_COOKIE)


@app.get("/auth/me", response_model=AuthStatusOut)
def get_auth_status(request: Request, response: Response) -> AuthStatusOut:
    """The frontend's one source of truth for sign-in state on boot
    (see lib/auth.svelte.js) -- deliberately NOT `Depends(resolve_identity)`
    directly, since a fresh visitor hitting this on app load shouldn't
    mint an anon cookie a split second before their very first real
    request would have minted the same one anyway; reading the cookie
    directly here just to check "is there a valid session" avoids that
    redundant Set-Cookie."""
    session_token = request.cookies.get(_SESSION_COOKIE)
    if session_token:
        user_id = db.get_user_id_for_auth_session(session_token)
        if user_id is not None:
            email = db.get_user_email(user_id)
            return AuthStatusOut(authenticated=True, email=email)
    return AuthStatusOut(authenticated=False)


if _FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIR), html=True), name="frontend")
