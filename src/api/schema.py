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

from typing import List, Optional

from pydantic import BaseModel

from src.orchestrator.schema import FailedStage


class CreateSessionResponse(BaseModel):
    id: str


class SendMessageRequest(BaseModel):
    content: str


class SendMessageResponse(BaseModel):
    response_text: Optional[str] = None
    confidence: Optional[float] = None
    failed_stage: Optional[FailedStage] = None
    error: Optional[str] = None


class MessageOut(BaseModel):
    role: str
    content: str
    created_at: str


class SessionSummary(BaseModel):
    """One row for the real frontend's Home screen (a list of a
    person's Journeys) -- see frontend/decisions.md "Build the real
    Confidant frontend". `surface_complaint` is plain language already
    (WorldState's own working-memory field), not a backend label.

    `bookmarked`/`has_stagnation_signal` added for the Home redesign
    (see frontend/decisions.md) -- `has_stagnation_signal` is
    deliberately just a boolean (whether compute_stagnation_signals
    found anything at all), not the mechanical signal text itself or
    Judgment's own worded stagnation_notes; the frontend renders one
    fixed, generic phrase when it's true, matching Learning Phase 1's
    own "mechanical signal only" precedent for a first pass."""

    id: str
    surface_complaint: str
    updated_at: str
    bookmarked: bool = False
    has_stagnation_signal: bool = False

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
    offline-computed, evidence-counted output. Deliberately NOT rendered
    anywhere in the frontend yet: interaction-model-v4.md requires
    "something noticed across Journeys" to read as a felt moment, never
    a dashboard list, and its exact form is its own, not-yet-done design
    pass (see frontend/decisions.md). This schema exists so the data
    contract is ready whenever that design lands."""

    pattern_type: str
    detail: str
    evidence_count: int


class InsightOut(BaseModel):
    """One row from GET /insights (see src/insight/engine.py::Insight,
    engine/decisions.md "Major update") -- the Insight Engine's own,
    offline-computed, cross-session output. Unlike LearnedPatternOut,
    this IS rendered in the frontend (Home.svelte, per an explicit
    product decision to show real theme text on each evidencing
    session's card) -- see src/api/db.py::list_sessions."""

    theme: str
    detail: str
    evidence_session_ids: List[str]
