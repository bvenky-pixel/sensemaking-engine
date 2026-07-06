"""
Orchestrator v1 -- coordinates one turn through the Sensemaking Engine
pipeline. First real System Architecture v2 component built after
Instrumentation (see engine/decisions.md).

Implements the Orchestrator section of
engine/specs/system-architecture-v2-specification.md, scoped down
deliberately, same discipline as every other "build X" task on this
branch:

BUILT: sequencing/coordination (which processes run, in what order) and
stage-level recovery (if a stage fails, stop the turn and report exactly
how far it got, including whatever state/artifacts earlier stages
already produced). This was previously duplicated, inline, in two driver
scripts (conversation_runner.py, scripts/run_worldstate_walkthrough.py)
-- extracting it here doesn't invent new behavior, it gives already-
working coordination logic one tested, shared home, and fixes a real
correctness bug found in the process (see TurnResult's docstring).

NOT built, deliberately deferred (named in the spec, no implementation
here yet, same as Learning's status):
- "Skipping unnecessary computation" (e.g. skip Judgment if Interpretation
  produced nothing new) -- no evidence yet that this optimization is
  needed, and the spec's own restriction ("skip logic must stay
  mechanical/structural, never semantic") means this would need a real
  structural trigger design, not a guess.
- "Selecting models" as interaction-level policy (e.g. a stronger model
  tier for a higher-stakes turn) -- no criteria for "higher-stakes"
  exists anywhere in this codebase today; inventing one now would be
  exactly the kind of ungrounded capability this project avoids building
  ahead of evidence.
- "Managing retries" beyond the stage-level stop-and-report done here --
  there's no evidence yet that retrying a whole failed stage (as opposed
  to the call-level provider fallback each engine already does) would
  help; the call-level retry/fallback chain already lives in
  src/llm/providers.py and stays there, per the spec's explicit scope
  boundary.

Orchestrator never performs user reasoning: it only sequences calls and
reports what happened, never judging what any stage's output means.
"""

from __future__ import annotations

from typing import Optional

from src.instrumentation.usage import UsageTracker, default_tracker
from src.interpretation.engine import InterpretationError, run_interpretation
from src.judgment.engine import JudgmentError, recommend_phase_transition, run_judgment
from src.orchestrator.schema import TurnResult
from src.planner.engine import PlannerError, run_planner
from src.response.engine import ResponseGeneratorError, run_response_generator
from src.state.builder import update_state
from src.state.world_state import WorldState


def run_turn(
    message: str, state: WorldState, tracker: Optional[UsageTracker] = None
) -> TurnResult:
    """
    Runs one turn through the fixed pipeline: Interpretation ->
    WorldState update/phase -> Judgment -> Planner -> Response Generator.
    This is the only order the Sensemaking Engine spec supports today --
    each stage's input is the previous stage's committed output, so
    there's no reordering or parallelism to decide between yet.

    Stops at the first stage that fails and returns immediately,
    reporting `failed_stage` and `error` -- but every stage that already
    succeeded before that point is still reflected in the returned
    TurnResult (`state`, and whichever of `interpretation`/`judgment`/
    `planner` already completed). Never raises -- a failure at any stage
    is data (a TurnResult), not an exception the caller has to catch.

    tracker: optional UsageTracker, passed through to every stage
    unchanged -- Orchestrator doesn't own instrumentation, it just makes
    sure every stage it calls gets the same one.
    """
    tracker = tracker or default_tracker

    try:
        interp = run_interpretation(message, tracker=tracker)
    except InterpretationError as exc:
        return TurnResult(state=state, failed_stage="interpretation", error=str(exc))

    # WorldState must be updated with this turn's Interpretation BEFORE
    # Judgment runs -- Judgment only ever sees WorldState, never the raw
    # Interpretation. Once this commits, `state` genuinely has changed,
    # regardless of what happens next.
    state = update_state(state, interp)
    next_phase = recommend_phase_transition(state)
    if next_phase:
        state.phase = next_phase

    try:
        judgment = run_judgment(state, tracker=tracker)
    except JudgmentError as exc:
        return TurnResult(
            state=state, interpretation=interp, failed_stage="judgment", error=str(exc),
        )

    try:
        plan = run_planner(state, judgment, tracker=tracker)
    except PlannerError as exc:
        return TurnResult(
            state=state, interpretation=interp, judgment=judgment,
            failed_stage="planner", error=str(exc),
        )

    try:
        response = run_response_generator(state, judgment, plan, tracker=tracker)
    except ResponseGeneratorError as exc:
        return TurnResult(
            state=state, interpretation=interp, judgment=judgment, planner=plan,
            failed_stage="response", error=str(exc),
        )

    return TurnResult(
        state=state, interpretation=interp, judgment=judgment, planner=plan, response=response,
    )
