"""
Understanding Engine, Tier 1 -- see src/understanding/__init__.py for the
package-level design rationale.

Tier 1 is a pure template, zero LLM calls -- same discipline as
src/executor/engine.py::build_clarity_brief, but reads WorldState's raw
Fact/Claim/Goal/Decision content directly rather than Judgment's
synthesized prose, so a statement's wording is byte-stable across turns
unless the underlying WorldState item itself actually changes.

Status filters below are a first-cut, explicitly uncalibrated choice
(same convention as src/state/builder.py's UNKNOWN_RESOLUTION_OVERLAP_THRESHOLD
comment) -- not claimed to be the final word on which statuses belong in
a person-facing Understanding view.
"""

from __future__ import annotations

from typing import List

from src.executor.voice import to_second_person
from src.state.world_state import WorldState
from src.understanding.schema import UnderstandingStatement

_FACT_CLAIM_VISIBLE_STATUSES = {"active"}
_GOAL_VISIBLE_STATUSES = {"active", "paused", "completed"}
_DECISION_VISIBLE_STATUSES = {"open", "deferred", "resolved"}


def build_tier1_statements(state: WorldState) -> List[UnderstandingStatement]:
    """
    Deterministic: calling this twice on an unchanged WorldState produces
    a byte-identical list, including every statement's id -- that
    stability, not richness of content, is Tier 1's entire job. `id` is
    derived from the grounding item's own (now-stable) id, not a fresh
    uuid, specifically so re-rendering doesn't itself introduce the
    wording/identity churn this layer exists to eliminate.
    """
    statements: List[UnderstandingStatement] = []

    for fact in state.facts:
        if fact.status not in _FACT_CLAIM_VISIBLE_STATUSES:
            continue
        statements.append(UnderstandingStatement(
            id=f"tier1:fact:{fact.id}", tier=1, kind="fact",
            text=to_second_person(fact.content), grounding_item_ids=[fact.id],
        ))

    for claim in state.claims:
        if claim.status not in _FACT_CLAIM_VISIBLE_STATUSES:
            continue
        statements.append(UnderstandingStatement(
            id=f"tier1:claim:{claim.id}", tier=1, kind="claim",
            text=to_second_person(claim.content), grounding_item_ids=[claim.id],
        ))

    for goal in state.goals:
        if goal.status not in _GOAL_VISIBLE_STATUSES:
            continue
        statements.append(UnderstandingStatement(
            id=f"tier1:goal:{goal.id}", tier=1, kind="goal",
            text=to_second_person(goal.content), grounding_item_ids=[goal.id],
        ))

    for decision in state.decisions:
        if decision.status not in _DECISION_VISIBLE_STATUSES:
            continue
        statements.append(UnderstandingStatement(
            id=f"tier1:decision:{decision.id}", tier=1, kind="decision",
            text=to_second_person(decision.content), grounding_item_ids=[decision.id],
        ))

    return statements
