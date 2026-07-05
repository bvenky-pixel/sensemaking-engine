"""
Confidant condition for the Judgment v2 evaluation: the real pipeline
(Interpretation -> State Builder -> WorldState -> Judgment), unmodified --
this module adds no new logic, it just drives the existing production
functions turn-by-turn and returns the FINAL Judgment for comparison
against the baselines in src/evaluation/baselines.py.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from src.instrumentation.usage import UsageTracker, default_tracker
from src.interpretation.engine import run_interpretation
from src.judgment.engine import recommend_phase_transition, run_judgment
from src.judgment.schema import Judgment
from src.state.builder import update_state
from src.state.world_state import WorldState


def run_confidant(transcript: List[str], tracker: Optional[UsageTracker] = None) -> Tuple[Judgment, str]:
    """Runs every turn through Interpretation + State Builder, then calls
    Judgment ONCE on the final WorldState (not per-turn) -- the smoke test
    only compares final-conversation assessments across conditions, see
    engine/decisions.md. Returns (Judgment, source_text) -- source_text is
    the final WorldState serialized to JSON, matching the shape
    src/evaluation/baselines.py's runners return so
    src/evaluation/metrics.py can treat all three conditions uniformly."""
    tracker = tracker or default_tracker
    state = WorldState()

    for message in transcript:
        interp = run_interpretation(message, tracker=tracker)
        state = update_state(state, interp)
        next_phase = recommend_phase_transition(state)
        if next_phase:
            state.phase = next_phase

    judgment = run_judgment(state, tracker=tracker)
    return judgment, state.model_dump_json()
