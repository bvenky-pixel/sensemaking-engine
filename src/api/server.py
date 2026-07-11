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

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from src.api import db
from src.api.schema import (
    ClarityBriefResponse,
    CreateSessionResponse,
    LearnedPatternOut,
    MessageOut,
    SendMessageRequest,
    SendMessageResponse,
    SessionSummary,
    SetBookmarkRequest,
)
from src.executor.engine import build_clarity_brief, render_clarity_brief
from src.instrumentation.usage import UsageTracker
from src.judgment.schema import Judgment
from src.orchestrator.engine import run_turn
from src.planner.schema import Planner
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


def _require_session(session_id: str) -> None:
    if not db.session_exists(session_id):
        raise HTTPException(status_code=404, detail=f"No session {session_id!r}")


@app.post("/sessions", response_model=CreateSessionResponse)
def create_session() -> CreateSessionResponse:
    return CreateSessionResponse(id=db.create_session())


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


@app.get("/sessions/{session_id}/messages", response_model=list[MessageOut])
def list_messages(session_id: str) -> list[MessageOut]:
    _require_session(session_id)
    return db.get_messages(session_id)


@app.post("/sessions/{session_id}/messages", response_model=SendMessageResponse)
def send_message(session_id: str, body: SendMessageRequest) -> SendMessageResponse:
    _require_session(session_id)

    state = db.load_state(session_id)
    tracker = UsageTracker()  # per-session, never the shared default -- see module docstring
    result = run_turn(body.content, state, tracker=tracker, session_id=session_id)

    db.append_message(session_id, "user", body.content)
    db.save_turn_result(session_id, result)
    db.save_events(session_id, result.behavioral_events)

    response_text = result.response.response_text if result.response else None
    confidence = result.response.confidence if result.response else None
    if response_text is not None:
        db.append_message(session_id, "assistant", response_text)

    return SendMessageResponse(
        response_text=response_text,
        confidence=confidence,
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
    brief = build_clarity_brief(state, judgment, planner)

    return ClarityBriefResponse(
        **brief.model_dump(),
        rendered_markdown=render_clarity_brief(brief),
        secondary_issues=judgment.secondary_issues,
        stagnation_notes=judgment.stagnation_notes,
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


if _FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIR), html=True), name="frontend")
