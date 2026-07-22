"""
Request/response schema for the MVP API layer.

This is the first HTTP-facing surface for Confidant -- everything
upstream (Interpretation/Judgment/Planner/Response/WorldState) is a
plain Pydantic model already, but none of it was ever meant to be
returned to a browser as-is: Judgment and Planner are explicitly
internal cognitive artifacts, never user-facing (see
engine/specs/judgment-specification-v2.md, planner-specification-v1.md).
These models define the curated, deliberately narrow shape the API
actually exposes to a real client -- `SendMessageResponse` mirrors what
`response.response_text`/`response.confidence` plus `failed_stage`/
`error` already are on `TurnResult`, nothing more.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, field_validator

from src.orchestrator.modes import CounselingMode
from src.orchestrator.schema import FailedStage


class CreateSessionRequest(BaseModel):
    # Counseling modes (see engine/decisions.md, src/orchestrator/modes.py):
    # optional -- a person can still begin a Journey with no mode chosen,
    # same as every Journey created before this feature existed.
    mode: Optional[CounselingMode] = None


class CreateSessionResponse(BaseModel):
    id: str


class ModeOut(BaseModel):
    """One entry of GET /modes -- src/orchestrator/modes.py's MODE_COPY,
    reshaped into a list so the frontend's mode-select screen never
    hardcodes its own copy of these 5 labels/descriptions (see
    frontend/app/src/lib/api.js's own "Reflection of Backend Truth,
    Never a Second Copy" principle) -- this endpoint is the one place
    that copy is allowed to live."""

    id: str
    label: str
    description: str


class SendMessageRequest(BaseModel):
    content: str


class ResponseOptionOut(BaseModel):
    """Mirrors src/response/schema.py::ResponseOption -- same "curated,
    never the raw internal model" discipline as UnderstandingStatementOut
    below. `label` is what gets sent as the person's own reply if
    tapped; `description` (added same round, see engine/decisions.md
    "Response v3 -- option reasoning") is 1-2 sentences of grounded
    reasoning shown alongside the button, never sent anywhere itself.
    """

    label: str
    description: str


class SendMessageResponse(BaseModel):
    response_text: Optional[str] = None
    confidence: Optional[float] = None
    options: List[ResponseOptionOut] = []
    failed_stage: Optional[FailedStage] = None
    error: Optional[str] = None


class MessageOut(BaseModel):
    role: str
    content: str
    created_at: str
    # Response v3 -- real choice buttons (see engine/decisions.md): only
    # ever non-empty on an assistant message. Persisted (src/api/db.py)
    # so a page reload still shows the same tappable buttons, not just
    # the plain paragraph.
    options: List[ResponseOptionOut] = []


class SessionSummary(BaseModel):
    """One row for the real frontend's Home screen (a list of a
    person's Journeys) -- see frontend/decisions.md "Build the real
    Confidant frontend".

    `preview_text` (renamed from `surface_complaint` 2026-07-15, see
    engine/decisions.md "Frontend UX pass"): previously this field WAS
    literally `WorldState.surface_complaint`, which is overwritten every
    turn with a paraphrase of whatever was said MOST RECENTLY -- fine
    for Judgment/Planner's internal reasoning (which wants the freshest
    framing), wrong for a stable session-list label, which should read
    as "what this Journey is about," not "what did they say last." Now
    sourced from the session's FIRST user message instead (see
    src/api/db.py::list_sessions) -- plain language either way, still
    not a backend label, just a different and more stable source.

    `bookmarked`/`has_stagnation_signal` added for the Home redesign
    (see frontend/decisions.md) -- `has_stagnation_signal` is a boolean
    (whether compute_stagnation_signals found anything at all, a pure
    function of WorldState alone) that the frontend still uses as a
    fallback gate.

    `stagnation_note` (2026-07-21, backlog #255, see engine/decisions.md
    "Frontend: richer stagnation wording sourced from Judgment's own
    stagnation_notes") -- the actual richer text, sourced from the
    session's last completed turn's `Judgment.stagnation_notes` (read
    from `debug_json`, same source `get_session_texts_for_insights`
    already reads `judgment` from). `None` whenever there's no completed
    turn yet, or the last Judgment's own `stagnation_notes` came back
    empty (a real, common, correct answer -- see that field's own
    docstring in src/judgment/schema.py) even though
    `has_stagnation_signal`'s mechanical check found a raw signal --
    Judgment may have reasoned the raw signal isn't actually
    significant this turn. The frontend prefers this real text when
    present and only falls back to the old fixed generic phrase when
    `has_stagnation_signal` is true but this is `None`.

    `mode` (2026-07-18, see frontend/decisions.md "Home: time period +
    mode filtering"): the Counseling mode chosen at creation (see
    src/orchestrator/modes.py), already stored per-session and already
    exposed for a single session via GET-ing that session's own mode
    indirectly through Planner's prompt -- never previously surfaced on
    the LIST endpoint, which Home's new per-period mode filter needs to
    group by without a separate request per session. `None` for any
    Journey created with no mode chosen (every Journey from before this
    feature existed, and anyone who skips picking one) -- the frontend
    simply excludes those from the mode-filter chip row entirely rather
    than inventing a fake "no mode" category."""

    id: str
    preview_text: str
    updated_at: str
    bookmarked: bool = False
    has_stagnation_signal: bool = False
    stagnation_note: Optional[str] = None
    mode: Optional[str] = None

    # Major update (2026-07-11, see engine/decisions.md): the theme text
    # of any Insight (src/insight/) this session is evidence for, if any
    # -- real, LLM-detected theme text, not just a boolean flag, per an
    # explicit product decision to show the actual content rather than
    # follow has_stagnation_signal's boolean-only precedent. A session
    # can be evidence for at most one theme in this field (a documented
    # simplification -- see src/api/db.py::list_sessions).
    insight_theme: Optional[str] = None
    insight_detail: Optional[str] = None


class SetBookmarkRequest(BaseModel):
    bookmarked: bool


class ClarityBriefResponse(BaseModel):
    """Unlike Judgment/Planner, a Clarity Brief (src/executor/engine.py) is
    itself the user-facing artifact -- a fixed-template synthesis of a
    completed turn, not raw internal cognition -- so its fields are
    exposed directly rather than curated further. `rendered_markdown` is
    the same content pre-formatted as a document, for a client that just
    wants to display it without reassembling the sections itself."""

    situation: str
    key_insights: List[str]
    current_direction: str
    remaining_unknowns: List[str]
    decisions: List[str]
    rendered_markdown: str

    # Added for the real frontend's "quiet discovery" moment (see
    # frontend/specs/screen-design-v1.md, frontend/decisions.md "Build
    # the real Confidant frontend") -- NOT part of Executor's own fixed
    # Clarity Brief template (src/executor/engine.py::build_clarity_brief
    # is unchanged), passed through directly from Judgment in
    # src/api/server.py's endpoint instead. Still real, already-curated
    # content (Judgment itself holds these fields back unless genuinely
    # significant -- see judgment-specification-v2.md's Secondary Issues/
    # Stagnation Notes entries), not raw internal cognition.
    secondary_issues: List[str] = []
    stagnation_notes: List[str] = []

    # Added 2026-07-22 (see engine/decisions.md and
    # clarity-brief-specification-v1.md "Decided" section, section 8
    # "What changed recently") -- src/executor/engine.py::diff_clarity_briefs
    # against `sessions.previous_brief_json`, computed server-side in
    # src/api/server.py's endpoint (NOT a frontend JS diff -- this
    # supersedes frontend/app/src/lib/deepeningClarity.js's own count-based
    # diff). Empty list is correct and common: a session's first completed
    # turn has nothing to have changed FROM yet, same as every other
    # sparse-by-default section in this response.
    what_changed: List[str] = []


class UnderstandingStatementOut(BaseModel):
    """One row from GET /sessions/{id}/understanding -- see
    src/understanding/schema.py::UnderstandingStatement, which this
    directly mirrors field-for-field (a curated re-declaration, not a
    re-export, matching this file's own convention -- see module
    docstring). Tier 1 (src/understanding/engine.py) is a deterministic
    template render of WorldState, computed and persisted every turn.
    Tier 2 (src/understanding/tier2_engine.py) is LLM-synthesized and
    computed only CONDITIONALLY (see that module's own docstring for
    why) -- an empty or unchanged tier2 list on a given turn is the
    common, expected case, not a gap. `grounding_item_ids` is exposed
    for parity with the internal model; the frontend isn't expected to
    render it (see Understanding.svelte)."""

    id: str
    tier: int
    kind: str
    text: str
    grounding_item_ids: List[str] = []


class UnderstandingResponse(BaseModel):
    tier1: List[UnderstandingStatementOut]
    tier2: List[UnderstandingStatementOut]


class LearnedPatternOut(BaseModel):
    """One row from GET /patterns (see engine/specs/architecture-roadmap-v1.md
    Phase 1, src/learning/engine.py::Pattern) -- Learning's own,
    offline-computed, evidence-counted output. IS rendered in the
    frontend (Settings' "Patterns" card, backlog #214, see
    frontend/app/src/components/BehavioralPatterns.svelte) -- the
    docstring here previously (and inaccurately, see backlog #270)
    called this "not yet rendered," a claim #214 made stale without the
    docstring ever being updated to match.

    `computed_at` (added 2026-07-19, backlog #269, see engine/decisions.md
    "Learning/POM: surface computed_at staleness signal"): the offline
    computation's own timestamp, already stored in `learned_patterns`
    since this table was first created but never selected/returned
    until now -- lets the frontend show when this was last computed
    rather than presenting it as always-current."""

    pattern_type: str
    detail: str
    evidence_count: int
    computed_at: str


class InsightOut(BaseModel):
    """One row from GET /insights (see src/insight/engine.py::Insight,
    engine/decisions.md "Major update") -- the Insight Engine's own,
    offline-computed, cross-session output. Also rendered in the
    frontend, same as LearnedPatternOut now is (Home.svelte, per an
    explicit product decision to show real theme text on each
    evidencing session's card) -- see src/api/db.py::list_sessions."""

    theme: str
    detail: str
    evidence_session_ids: List[str]


class PrivacySettingsOut(BaseModel):
    """Privacy, made real (2026-07-18, see frontend/decisions.md) --
    GET/POST /privacy/settings. See src/api/db.py's `privacy_settings`
    table docstring for exactly what each field gates.
    `reflection_prompt_enabled` added 2026-07-19, backlog #207."""

    cross_session_learning_enabled: bool
    reflection_prompt_enabled: bool


class SetPrivacySettingsRequest(BaseModel):
    cross_session_learning_enabled: bool
    reflection_prompt_enabled: bool


class SubmitJourneyReflectionRequest(BaseModel):
    """POST /sessions/{id}/reflection body -- backlog #207."""

    content: str

    @field_validator("content", mode="after")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("content must not be empty or whitespace-only")
        return value


class SubmitPomFeedbackRequest(BaseModel):
    """POST /pom/feedback body -- backlog #209. `system`/`statement` are
    the section label and rendered text the person reacted to (e.g.
    system="stress", statement="You've been under a lot of pressure
    lately."); `correction_text` is optional even when feedback is
    "correct" -- a bare thumbs-down with no explanation is still a
    valid, "light" reaction."""

    system: str
    statement: str
    feedback: Literal["affirm", "correct"]
    correction_text: Optional[str] = None

    @field_validator("system", "statement", mode="after")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be empty or whitespace-only")
        return value

    @field_validator("correction_text", mode="after")
    @classmethod
    def _blank_to_none(cls, value: Optional[str]) -> Optional[str]:
        return value.strip() if value and value.strip() else None


class RequestMagicLinkRequest(BaseModel):
    email: str
    # Response-limit login UX gap fix (2026-07-18, see engine/decisions.md
    # "Return to the same Journey after magic-link verify") -- the
    # Journey the caller was actually in when they hit a login wall, if
    # any. Optional: Settings' own screen-wide login gate has no
    # session context at all, and still omits this entirely.
    return_session_id: Optional[str] = None


class RequestMagicLinkResponse(BaseModel):
    """Deliberately just a bare acknowledgement -- see
    src/api/server.py's POST /auth/request-link docstring for why this
    never reveals whether the email matched an existing account, and
    never includes the link/token itself."""

    sent: bool


class VerifyMagicLinkRequest(BaseModel):
    token: str


class AuthStatusOut(BaseModel):
    """GET /auth/me -- the frontend's one source of truth for whether
    the current browser is signed in (see lib/auth.svelte.js).
    `email` is None whenever `authenticated` is False.

    `return_session_id` (response-limit login UX gap fix, 2026-07-18,
    see engine/decisions.md "Return to the same Journey after
    magic-link verify"): only ever set by POST /auth/verify, and only
    when the magic link that was just clicked carried one AND it still
    resolves to a Journey this account now genuinely owns -- GET
    /auth/me (plain page-load sign-in check) never sets it."""

    authenticated: bool
    email: Optional[str] = None
    return_session_id: Optional[str] = None
