"""
Learning v1 -- Phase 1's real implementation (see
engine/specs/architecture-roadmap-v1.md, src/learning/engine.py). The
previous version of this file was a canary confirming the reserved-slot
stub still raised NotImplementedError -- that canary's job was to force
a deliberate decision before anyone wired in real logic. This is that
deliberate decision, recorded as real coverage instead.

Pure, deterministic, no mocking -- same style as
tests/test_judgment_stagnation.py.
"""

from __future__ import annotations

from src.instrumentation.events import BehavioralEvent
from src.learning.engine import compute_behavioral_patterns


def _event(event_type="decision_status_changed", new_status="deferred", detail="Take the offer"):
    return BehavioralEvent(
        event_type=event_type,
        session_id="s1",
        turn=1,
        detail=detail,
        old_status="open",
        new_status=new_status,
        timestamp="2026-07-11T00:00:00+00:00",
    )


def test_no_events_produces_no_patterns():
    assert compute_behavioral_patterns([]) == []


def test_evidence_below_floor_produces_no_pattern():
    events = [_event() for _ in range(2)]
    assert compute_behavioral_patterns(events, min_evidence=3) == []


def test_evidence_at_floor_produces_a_pattern():
    events = [_event() for _ in range(3)]
    patterns = compute_behavioral_patterns(events, min_evidence=3)
    assert len(patterns) == 1
    assert patterns[0].pattern_type == "decision_status_changed"
    assert patterns[0].evidence_count == 3
    assert "deferred" in patterns[0].detail


def test_different_event_type_and_status_groups_are_counted_separately():
    events = (
        [_event(event_type="decision_status_changed", new_status="deferred") for _ in range(3)]
        + [_event(event_type="decision_status_changed", new_status="resolved") for _ in range(3)]
        + [_event(event_type="goal_status_changed", new_status="abandoned") for _ in range(3)]
    )
    patterns = compute_behavioral_patterns(events, min_evidence=3)
    assert len(patterns) == 3
    pattern_types_and_statuses = {(p.pattern_type, p.evidence_count) for p in patterns}
    assert pattern_types_and_statuses == {
        ("decision_status_changed", 3),
        ("goal_status_changed", 3),
    }


def test_goal_pattern_detail_does_not_invent_resolved_vocabulary():
    """GoalStatus has no 'resolved' concept -- only DecisionStatus does.
    Confirms the pattern detail for a goal event only ever references
    real GoalStatus values, never invents one."""
    events = [_event(event_type="goal_status_changed", new_status="abandoned") for _ in range(3)]
    patterns = compute_behavioral_patterns(events, min_evidence=3)
    assert len(patterns) == 1
    assert "goals" in patterns[0].detail
    assert "abandoned" in patterns[0].detail
