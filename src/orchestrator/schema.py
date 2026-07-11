"""
Orchestrator output schema for Confidant's System Architecture v2.

Implements the Orchestrator section of
engine/specs/system-architecture-v2-specification.md. `TurnResult`
reports exactly how far one turn got through the fixed Sensemaking
Engine pipeline (Interpretation -> WorldState -> Judgment -> Planner ->
Response Generator) -- every field that ran successfully is populated,
regardless of whether a LATER stage failed. This is the structural fix
for a real bug found while building this: the two prior driver scripts
(conversation_runner.py, scripts/run_worldstate_walkthrough.py) each
inlined their own ad hoc try/except sequencing, and conversation_runner.py
specifically printed "State unchanged" on ANY failure -- which was false
whenever Judgment, Planner, or Response Generator failed, since
WorldState had already been genuinely updated by that point. See
engine/decisions.md for the full story.

`state` is always present and always accurate: genuinely unchanged only
when Interpretation itself failed (the only stage that runs before
WorldState is touched); reflects the real, committed update for every
later failure point.

Unlike every Sensemaking Engine schema (Interpretation, Judgment,
Planner, Response), TurnResult is never produced by an LLM call --
Orchestrator makes no LLM call of its own; it only coordinates calls to
the five Sensemaking Engine processes and reports what happened. There is
deliberately no prompt.py in this package for that reason.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from src.instrumentation.events import BehavioralEvent
from src.interpretation.schema import Interpretation
from src.judgment.schema import Judgment
from src.planner.schema import Planner
from src.response.schema import Response
from src.state.world_state import WorldState

FailedStage = Literal["interpretation", "judgment", "planner", "response"]


class TurnResult(BaseModel):
    state: WorldState

    interpretation: Optional[Interpretation] = None
    judgment: Optional[Judgment] = None
    planner: Optional[Planner] = None
    response: Optional[Response] = None

    failed_stage: Optional[FailedStage] = None
    error: Optional[str] = None

    # Phase 1 Learning (see engine/specs/architecture-roadmap-v1.md):
    # behavioral events detected by diffing WorldState before/after this
    # turn's mutations (src/instrumentation/events.py). Empty whenever
    # nothing's status changed, or whenever the turn failed before
    # update_state ran (Interpretation failure) -- both real, not a bug.
    behavioral_events: List[BehavioralEvent] = Field(default_factory=list)
