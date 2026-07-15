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
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Optional, Tuple

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from src.api import db
from src.api.schema import (
    ClarityBriefResponse,
    CreateSessionRequest,
    CreateSessionResponse,
    InsightOut,
    LearnedPatternOut,
    MessageOut,
    ModeOut,
    ResponseOptionOut,
    SendMessageRequest,
    SendMessageResponse,
    SessionSummary,
    SetBookmarkRequest,
    UnderstandingResponse,
    UnderstandingStatementOut,
)
from src.executor.engine import build_clarity_brief, render_clarity_brief
from src.executor.voice import to_second_person
from src.insight.schema import Insight
from src.instrumentation.usage import UsageTracker
from src.judgment.schema import Judgment
from src.learning.engine import Pattern
from src.orchestrator.engine import run_turn
from src.orchestrator.modes import MODE_COPY
from src.planner.schema import Planner
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


def _require_session(session_id: str) -> None:
    if not db.session_exists(session_id):
        raise HTTPException(status_code=404, detail=f"No session {session_id!r}")


@app.post("/sessions", response_model=CreateSessionResponse)
def create_session(body: CreateSessionRequest = CreateSessionRequest()) -> CreateSessionResponse:
    return CreateSessionResponse(id=db.create_session(mode=body.mode))


@app.get("/modes", response_model=list[ModeOut])
def list_modes() -> list[ModeOut]:
    """Backs the mode-select screen shown before a new Journey begins
    (see frontend/app/src/screens/ModeSelect.svelte, engine/decisions.md
    "Counseling modes") -- never session-scoped, so no `_require_session`
    guard, unlike every other endpoint in this file."""
    return [ModeOut(id=mode_id, **copy) for mode_id, copy in MODE_COPY.items()]


@app.get("/sessions", response_model=list[SessionSummary])
def list_sessions(bookmarked_only: bool = False) -> list[SessionSummary]:
    """Backs the real frontend's Home screen (a list of a person's
    Journeys) -- see frontend/decisions.md "Build the real Confidant
    frontend". `bookmarked_only` backs Home's All/Bookmarked filter
    (added for the Home redesign, see frontend/decisions.md)."""
    return db.list_sessions(bookmarked_only=bookmarked_only)


@app.post("/sessions/{session_id}/bookmark", response_model=SetBookmarkRequest)
def set_bookmark(session_id: str, body: SetBookmarkRequest) -> SetBookmarkRequest:
    """Added for the Home redesign (see frontend/decisions.md) -- returns
    the same shape back so the frontend can update optimistically without
    a second round trip to re-fetch the session list."""
    _require_session(session_id)
    db.set_bookmark(session_id, body.bookmarked)
    return body


@app.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: str) -> None:
    """Added for Settings' Data section (see engine/decisions.md
    "Frontend UX pass") -- removes a Journey and every row that
    references it (see db.delete_session's own docstring for exactly
    what that means for insight_sessions specifically). Irreversible,
    same as any real delete -- no soft-delete/undo exists yet."""
    _require_session(session_id)
    db.delete_session(session_id)


@app.get("/sessions/{session_id}/messages", response_model=list[MessageOut])
def list_messages(session_id: str) -> list[MessageOut]:
    _require_session(session_id)
    return db.get_messages(session_id)


@app.get("/sessions/{session_id}/stream")
async def stream_stages(session_id: str) -> StreamingResponse:
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
    _require_session(session_id)
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
def send_message(session_id: str, body: SendMessageRequest) -> SendMessageResponse:
    _require_session(session_id)

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
    patterns = [
        Pattern(pattern_type=p.pattern_type, detail=p.detail, evidence_count=p.evidence_count)
        for p in db.get_learned_patterns()
    ]
    insights = [
        Insight(theme=i.theme, detail=i.detail, evidence_session_ids=i.evidence_session_ids)
        for i in db.get_insights()
    ]
    retrieved_context = build_retrieved_context(patterns, insights)

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
def get_debug(session_id: str) -> dict:
    _require_session(session_id)
    return db.load_debug(session_id) or {}


@app.get("/sessions/{session_id}/clarity-brief", response_model=ClarityBriefResponse)
def get_clarity_brief(session_id: str) -> ClarityBriefResponse:
    """Unlike /debug, this is meant to be shown to the actual user -- see
    src/api/schema.py's ClarityBriefResponse docstring. 404s until at
    least one turn has completed Judgment and Planner (a turn that failed
    before those stages has nothing to build a brief from yet)."""
    _require_session(session_id)
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
def get_understanding(session_id: str) -> UnderstandingResponse:
    """Unlike /clarity-brief, this never 404s -- Tier 1
    (src/understanding/engine.py::build_tier1_statements) is computed
    unconditionally every turn (src/orchestrator/engine.py::run_turn),
    so even a brand-new session's first turn has SOME content. An empty
    tier1/tier2 list (e.g. before any turn has completed) is a valid,
    correct response -- nothing understood yet, not an error."""
    _require_session(session_id)
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


if _FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIR), html=True), name="frontend")
