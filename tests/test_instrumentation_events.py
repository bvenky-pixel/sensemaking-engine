"""
Tests for diff_behavioral_events (src/instrumentation/events.py) -- the
diff-based behavioral-event detector Phase 1 Learning's Memory Store is
built on (see engine/specs/architecture-roadmap-v1.md). Same category as
tests/test_judgment_stagnation.py: pure Python, fully unit-testable.

The reaffirmation test below is the one a plan review specifically
caught as a real correctness risk in an earlier, rejected design
(threading a recorder through src/state/builder.py's mutation
functions, which assign `.status` unconditionally on every matching
update/event -- even when the status doesn't actually change). Diffing
WorldState before/after avoids that failure mode by construction; this
test confirms it.
"""

from __future__ import annotations

from src.instrumentation.events import diff_behavioral_events, is_events_enabled
from src.state.world_state import Decision, Goal, WorldState


def test_events_disabled_by_default(monkeypatch):
    monkeypatch.delenv("CONFIDANT_RECORD_EVENTS", raising=False)
    assert is_events_enabled() is False


def test_events_enabled_when_flag_set(monkeypatch):
    monkeypatch.setenv("CONFIDANT_RECORD_EVENTS", "1")
    assert is_events_enabled() is True


def test_no_change_produces_no_events():
    state = WorldState(goals=[Goal(content="Move to the Product team.", status="active")])
    assert diff_behavioral_events(state, state, session_id="s1", turn=1) == []


def test_reaffirmed_status_produces_zero_events():
    """A Decision reaffirmed at the same status across turns (Interpretation
    is stateless, so this can happen) must never be recorded as a
    transition -- this is the exact overcounting bug a plan review caught
    in the rejected recorder-threading design."""
    old_state = WorldState(decisions=[Decision(content="Take the new offer", status="deferred")])
    new_state = WorldState(decisions=[Decision(content="Take the new offer", status="deferred")])
    assert diff_behavioral_events(old_state, new_state, session_id="s1", turn=2) == []


def test_real_goal_status_change_produces_one_event():
    old_state = WorldState(goals=[Goal(content="Move to the Product team.", status="active")])
    new_state = WorldState(goals=[Goal(content="Move to the Product team.", status="abandoned")])
    events = diff_behavioral_events(old_state, new_state, session_id="s1", turn=3)
    assert len(events) == 1
    assert events[0].event_type == "goal_status_changed"
    assert events[0].old_status == "active"
    assert events[0].new_status == "abandoned"
    assert events[0].session_id == "s1"
    assert events[0].turn == 3


def test_real_decision_status_change_produces_one_event():
    old_state = WorldState(decisions=[Decision(content="Take the new offer", status="open")])
    new_state = WorldState(decisions=[Decision(content="Take the new offer", status="resolved")])
    events = diff_behavioral_events(old_state, new_state, session_id="s1", turn=4)
    assert len(events) == 1
    assert events[0].event_type == "decision_status_changed"
    assert events[0].old_status == "open"
    assert events[0].new_status == "resolved"


def test_newly_created_item_produces_no_event():
    """An item present only in new_state (created this turn) has no old
    counterpart to diff against -- creation is not a status transition."""
    old_state = WorldState()
    new_state = WorldState(goals=[Goal(content="A brand new goal.", status="active")])
    assert diff_behavioral_events(old_state, new_state, session_id="s1", turn=1) == []


def test_content_matching_is_case_and_whitespace_insensitive():
    """Matches _merge_content_items's own dedup key (content.strip().lower())."""
    old_state = WorldState(goals=[Goal(content="  Move to the Product team.  ", status="active")])
    new_state = WorldState(goals=[Goal(content="move to the product team.", status="completed")])
    events = diff_behavioral_events(old_state, new_state, session_id="s1", turn=5)
    assert len(events) == 1
    assert events[0].new_status == "completed"


def test_multiple_changes_in_one_turn_produce_multiple_events():
    old_state = WorldState(
        goals=[Goal(content="Goal A", status="active")],
        decisions=[Decision(content="Decision A", status="open")],
    )
    new_state = WorldState(
        goals=[Goal(content="Goal A", status="completed")],
        decisions=[Decision(content="Decision A", status="resolved")],
    )
    events = diff_behavioral_events(old_state, new_state, session_id="s1", turn=6)
    assert len(events) == 2
    event_types = {e.event_type for e in events}
    assert event_types == {"goal_status_changed", "decision_status_changed"}
