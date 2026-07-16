"""
Tests for src/need_state/engine.py::infer_need_state -- Need State
Inference v1 (see engine/decisions.md "Need State Inference"). Pure,
deterministic, no LLM call -- same category as
tests/test_judgment_stagnation.py's compute_stagnation_signals tests,
including the same Provenance-construction helper pattern.
"""

from __future__ import annotations

from src.need_state.engine import infer_need_state
from src.state.world_state import Decision, Goal, Provenance, WorldState


def _prov(first_seen: int, last_updated: int) -> Provenance:
    return Provenance(source="interpretation", first_seen=first_seen, last_updated=last_updated)


def test_empty_worldstate_infers_general():
    assert infer_need_state(WorldState()) == "general"


def test_open_decision_with_no_stagnation_infers_decision():
    state = WorldState(
        turn_count=2,
        decisions=[Decision(content="Take the offer.", status="open", provenance=_prov(1, 2))],
    )
    assert infer_need_state(state) == "decision"


def test_goal_with_no_other_signal_infers_reflection():
    state = WorldState(
        turn_count=2,
        goals=[Goal(content="Move to the Product team.", status="active", provenance=_prov(1, 2))],
    )
    assert infer_need_state(state) == "reflection"


def test_stale_active_goal_infers_accountability():
    state = WorldState(
        turn_count=10,
        goals=[Goal(content="Move to the Product team.", status="active", provenance=_prov(1, 6))],
    )
    assert infer_need_state(state) == "accountability"


def test_stale_open_decision_infers_accountability():
    state = WorldState(
        turn_count=10,
        decisions=[Decision(content="Apply externally.", status="open", provenance=_prov(1, 7))],
    )
    assert infer_need_state(state) == "accountability"


def test_stagnant_goal_beats_a_fresh_open_decision():
    """Priority ordering: a stalled item is a more urgent need than a
    fresh, not-yet-stagnant open decision, even when both are present."""
    state = WorldState(
        turn_count=10,
        goals=[Goal(content="Move to the Product team.", status="active", provenance=_prov(1, 6))],
        decisions=[Decision(content="Apply externally.", status="open", provenance=_prov(9, 9))],
    )
    assert infer_need_state(state) == "accountability"


def test_fresh_open_decision_beats_reflection_when_a_goal_also_exists():
    state = WorldState(
        turn_count=2,
        goals=[Goal(content="Move to the Product team.", status="active", provenance=_prov(1, 2))],
        decisions=[Decision(content="Take the offer.", status="open", provenance=_prov(1, 2))],
    )
    assert infer_need_state(state) == "decision"


def test_paused_goal_never_counts_as_stagnant():
    state = WorldState(
        turn_count=10,
        goals=[Goal(content="Old goal.", status="paused", provenance=_prov(1, 1))],
    )
    assert infer_need_state(state) == "general"


def test_resolved_decision_never_counts_as_open_or_stagnant():
    state = WorldState(
        turn_count=10,
        decisions=[Decision(content="Already decided.", status="resolved", provenance=_prov(1, 1))],
    )
    assert infer_need_state(state) == "general"
