"""
Behavioral event detection -- Phase 1 of Learning's reopening (see
engine/specs/architecture-roadmap-v1.md and src/learning/__init__.py's
former stub docstring, which named the exact reopening path this module
begins: "at minimum a persistence layer for Instrumentation data across
runs"). This is that persistence layer's source of data.

DIFF-BASED, NOT RECORDER-THREADED. An earlier version of this design
threaded an EventRecorder through src/state/builder.py's mutation
functions, mirroring UsageTracker's inline-recording pattern. A plan
review caught a real correctness bug in that approach: _apply_goal_updates,
_apply_decision_events, and apply_judgment_resolutions all assign
`.status` unconditionally whenever a matching update/event/resolution
appears -- they never check whether the new status differs from the old
one. Interpretation is stateless per turn, so a Decision the user is
still deferring can plausibly re-emit the same event turn after turn;
recording at the mutation line as originally designed would have
recorded N events for one real transition, inflating exactly the
evidence a min_evidence floor is supposed to protect against. Diffing
WorldState before/after instead means an event only ever exists for a
genuine `old.status != new.status` delta, by construction -- and needs
zero changes to builder.py's mutation functions.

Goals and Decisions have no stable object IDs yet (see world_state.py's
own module docstring: "matching still goes by content/word-overlap").
Matching "the same" item across old_state/new_state therefore uses the
identical dedup key _merge_content_items already uses elsewhere in this
codebase (content.strip().lower()) -- valid because content itself is
never mutated in place for an existing item; only status/provenance
change (see _merge_content_items's own docstring: "Existing items are
returned unchanged").
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import List, Literal

from pydantic import BaseModel

from src.state.world_state import WorldState

BehavioralEventType = Literal["goal_status_changed", "decision_status_changed"]


def is_events_enabled() -> bool:
    """
    Off by default, mirroring src/instrumentation/usage.py's
    is_tracking_enabled() -- but checked at the PERSISTENCE boundary
    (src/api/db.py::save_events), not here, since diff_behavioral_events
    itself stays a pure function with no environment dependency.
    Deliberately NOT defaulted on anywhere yet, including the deployed
    Fly.io environment: trust-and-privacy-ux-v1.md's Principle 6
    (amended for this feature) requires a real disclosure surface and
    deletion path before real behavioral data should accumulate in
    production, and neither exists yet (see that principle's own "what
    Phase 1 actually ships" admission). Turning this on in production is
    a deliberate product/privacy decision, not an engineering default --
    see engine/decisions.md.
    """
    return os.environ.get("CONFIDANT_RECORD_EVENTS", "").strip().lower() in ("1", "true", "yes")


class BehavioralEvent(BaseModel):
    """
    One observed, factual status transition -- observation only, no
    interpretation, same non-goal Instrumentation already holds elsewhere
    ("It observes; it does not evaluate or act" --
    engine/specs/system-architecture-v2-specification.md). `event_type`
    is deliberately just two generic values with the real transition in
    old_status/new_status, rather than inventing values like
    "goal_resolved" -- GoalStatus has no "resolved" concept
    (Literal["active","paused","completed","abandoned"]); only
    DecisionStatus does (Literal["open","resolved","deferred","expired"]).
    """

    event_type: BehavioralEventType
    session_id: str
    turn: int
    detail: str  # the Goal/Decision's own content, for a human-readable event
    old_status: str
    new_status: str
    timestamp: str


def _content_key(content: str) -> str:
    return content.strip().lower()


def diff_behavioral_events(
    old_state: WorldState, new_state: WorldState, session_id: str, turn: int
) -> List[BehavioralEvent]:
    """
    Pure function, no side effects, no persistence -- same category as
    src/judgment/engine.py's compute_stagnation_signals. Compares
    old_state.goals/decisions against new_state.goals/decisions by
    content key, emitting an event only where a matched item's status
    actually differs. An item present only in new_state (freshly created
    this turn) has no old counterpart to diff against and is correctly
    skipped -- creation is not a status transition.
    """
    events: List[BehavioralEvent] = []
    timestamp = datetime.now(timezone.utc).isoformat()

    old_goals_by_key = {_content_key(g.content): g for g in old_state.goals}
    for goal in new_state.goals:
        old_goal = old_goals_by_key.get(_content_key(goal.content))
        if old_goal is not None and old_goal.status != goal.status:
            events.append(
                BehavioralEvent(
                    event_type="goal_status_changed",
                    session_id=session_id,
                    turn=turn,
                    detail=goal.content,
                    old_status=old_goal.status,
                    new_status=goal.status,
                    timestamp=timestamp,
                )
            )

    old_decisions_by_key = {_content_key(d.content): d for d in old_state.decisions}
    for decision in new_state.decisions:
        old_decision = old_decisions_by_key.get(_content_key(decision.content))
        if old_decision is not None and old_decision.status != decision.status:
            events.append(
                BehavioralEvent(
                    event_type="decision_status_changed",
                    session_id=session_id,
                    turn=turn,
                    detail=decision.content,
                    old_status=old_decision.status,
                    new_status=decision.status,
                    timestamp=timestamp,
                )
            )

    return events
