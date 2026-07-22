"""
Tests for compute_stagnation_signals (src/judgment/engine.py) -- the
deterministic, non-LLM helper that computes turn-gap arithmetic for
Judgment's stagnation_notes field (see engine/decisions.md "Judgment
trajectory/stagnation assessment"). Same category as
recommend_phase_transition (tests/test_judgment_phase_transition.py):
pure Python, fully unit-testable without a live LLM call. run_judgment()
itself (which calls this and threads the result into the prompt) is not
unit-tested here -- see scripts/run_worldstate_walkthrough.py for
exercising it live.
"""

from __future__ import annotations

from src.judgment.engine import STAGNATION_TURN_THRESHOLD, compute_stagnation_signals
from src.state.world_state import Decision, Goal, Provenance, Unknown, WorldState


def _prov(first_seen: int, last_updated: int) -> Provenance:
    return Provenance(source="interpretation", first_seen=first_seen, last_updated=last_updated)


def test_empty_worldstate_produces_no_signals():
    assert compute_stagnation_signals(WorldState()) == []


def test_stale_active_goal_produces_a_signal():
    state = WorldState(
        turn_count=10,
        goals=[Goal(content="Move to the Product team.", status="active", provenance=_prov(1, 6))],
    )
    signals = compute_stagnation_signals(state)
    assert len(signals) == 1
    assert "Move to the Product team." in signals[0]
    assert "4 turns" in signals[0]


def test_goal_under_threshold_produces_no_signal():
    state = WorldState(
        turn_count=10,
        goals=[Goal(content="Move to the Product team.", status="active", provenance=_prov(8, 8))],
    )
    assert compute_stagnation_signals(state) == []


def test_paused_completed_abandoned_goals_never_flagged_even_if_stale():
    for status in ("paused", "completed", "abandoned"):
        state = WorldState(
            turn_count=10,
            goals=[Goal(content="Old goal.", status=status, provenance=_prov(1, 1))],
        )
        assert compute_stagnation_signals(state) == [], f"status={status} should never be flagged"


def test_stale_open_decision_produces_a_signal():
    state = WorldState(
        turn_count=10,
        decisions=[Decision(content="Apply externally.", status="open", provenance=_prov(1, 7))],
    )
    signals = compute_stagnation_signals(state)
    assert len(signals) == 1
    assert "Apply externally." in signals[0]
    assert "3 turns" in signals[0]


def test_resolved_deferred_expired_decisions_never_flagged_even_if_stale():
    for status in ("resolved", "deferred", "expired"):
        state = WorldState(
            turn_count=10,
            decisions=[Decision(content="Old decision.", status=status, provenance=_prov(1, 1))],
        )
        assert compute_stagnation_signals(state) == [], f"status={status} should never be flagged"


def test_stale_open_unknown_produces_a_signal():
    """Regression test for the "repetitive, going in circles" complaint:
    an Unknown that stays open for many turns is the exact pool Planner
    draws questions_to_explore from -- this needs the same mechanical
    staleness signal a Goal/Decision already gets."""
    state = WorldState(
        turn_count=10,
        unknowns=[Unknown(content="Why hasn't the transfer moved forward?", status="open", provenance=_prov(1, 5))],
    )
    signals = compute_stagnation_signals(state)
    assert len(signals) == 1
    assert "Why hasn't the transfer moved forward?" in signals[0]
    assert "5 turns" in signals[0]


def test_resolved_unknown_never_flagged_even_if_stale():
    state = WorldState(
        turn_count=10,
        unknowns=[Unknown(content="Old unknown.", status="resolved", provenance=_prov(1, 1))],
    )
    assert compute_stagnation_signals(state) == []


def test_item_with_no_provenance_is_skipped_not_treated_as_stagnant():
    state = WorldState(
        turn_count=10,
        goals=[Goal(content="Constructed directly, no provenance.", status="active", provenance=None)],
    )
    assert compute_stagnation_signals(state) == []


def test_custom_threshold_is_respected():
    state = WorldState(
        turn_count=5,
        goals=[Goal(content="Recent-ish goal.", status="active", provenance=_prov(1, 3))],
    )
    assert compute_stagnation_signals(state, threshold=STAGNATION_TURN_THRESHOLD) == []
    signals = compute_stagnation_signals(state, threshold=2)
    assert len(signals) == 1
