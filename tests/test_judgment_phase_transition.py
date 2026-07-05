"""
Tests for recommend_phase_transition (src/judgment/engine.py) -- the one
piece of Judgment v2 that's deterministic and testable without a live LLM
call. run_judgment() itself is an LLM call and isn't unit-tested here;
see scripts/run_worldstate_walkthrough.py for exercising it live.

recommend_phase_transition is explicitly legacy-compatibility only (see
engine/decisions.md) -- these tests pin its current behavior, ported
unchanged from Judgment v1's logic onto WorldState fields.
"""

from __future__ import annotations

from src.judgment.engine import recommend_phase_transition
from src.state.world_state import WorldState


def test_no_transition_from_empty_prepare_state():
    state = WorldState()
    assert recommend_phase_transition(state) is None


def test_prepare_to_discover_once_surface_complaint_present():
    state = WorldState(surface_complaint="User is unsure about a transfer.")
    assert recommend_phase_transition(state) == "discover"


def test_discover_to_discern_once_core_question_confidence_crosses_threshold():
    state = WorldState(phase="discover", core_question_confidence=0.6)
    assert recommend_phase_transition(state) == "discern"

    state = WorldState(phase="discover", core_question_confidence=0.59)
    assert recommend_phase_transition(state) is None


def test_discern_stays_once_assumption_or_bias_signal_present():
    state = WorldState(phase="discern", assumptions=["User believes X."])
    assert recommend_phase_transition(state) == "discern"

    state = WorldState(phase="discern", biases=["sunk cost"])
    assert recommend_phase_transition(state) == "discern"

    state = WorldState(phase="discern")
    assert recommend_phase_transition(state) is None
