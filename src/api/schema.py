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
    (WorldState's own working-memory field), not a backend label."""

    id: str
    surface_complaint: str
    updated_at: str


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
