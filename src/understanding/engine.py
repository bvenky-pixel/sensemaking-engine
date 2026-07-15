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
from src.state.world_state import Entity, WorldState
from src.understanding.schema import UnderstandingStatement

_FACT_CLAIM_VISIBLE_STATUSES = {"active"}
_GOAL_VISIBLE_STATUSES = {"active", "paused", "completed"}
_DECISION_VISIBLE_STATUSES = {"open", "deferred", "resolved"}
# Unknown.status is never actually "resolved" in practice -- builder.py
# deletes a resolved Unknown and promotes its content into a Fact instead
# of marking it resolved in place (see Unknown's own docstring in
# world_state.py). Filtering defensively anyway, same discipline as
# every other loop here.
_UNKNOWN_VISIBLE_STATUSES = {"open"}
# Nothing sets Entity/Assumption/Inference status to "retracted" today --
# same "filter defensively for a state nothing currently produces" reasoning.
_ENTITY_VISIBLE_STATUSES = {"active"}
_ASSUMPTION_VISIBLE_STATUSES = {"active"}
_INFERENCE_VISIBLE_STATUSES = {"active"}


def _render_entity_text(entity: Entity) -> str:
    """
    Entity has no single content string to pass through to_second_person
    (unlike every other KnowledgeItem subtype) -- name/attributes/
    relationships instead. Only ever called when there's at least one
    attribute or relationship (see the skip condition in
    build_tier1_statements below): a bare mention with nothing else to
    say would just redundantly restate what a Fact already says (real
    captured data shows Entity(name="friend") with no attributes
    alongside a separate Fact "You have a friend." -- Entity only earns
    a Tier 1 line once it carries structured information a Fact sentence
    doesn't already capture).
    """
    parts = [f"{attr.attribute} is {attr.value}" for attr in entity.attributes]
    parts += list(entity.relationships)
    return f"{entity.name} -- " + "; ".join(parts) + "."


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
        # decision.content is a bare noun-phrase label (e.g. "House",
        # "MBA" -- see Interpretation's decision_options docstring and
        # real captured data in experiments/confidant-validation/log.md
        # case D01), not a sentence -- to_second_person is a documented
        # no-op on text with no "user"/"they" token, so a bare passthrough
        # rendered as an isolated single-word bullet. Wrapped in a
        # template instead; to_second_person still runs first in case
        # content ever does contain a "user" token. Deliberately NOT
        # status-differentiated (e.g. a different sentence for
        # "resolved"): DecisionResolution/DecisionEvent both collapse
        # "chosen" and "rejected" into the same "resolved" status value
        # (see _DECISION_EVENT_TO_STATUS in src/state/builder.py), so a
        # resolved Decision's actual outcome isn't recoverable from
        # status alone -- a confident "You've decided on X" phrasing
        # would risk asserting the wrong outcome for a rejected option.
        statements.append(UnderstandingStatement(
            id=f"tier1:decision:{decision.id}", tier=1, kind="decision",
            text=f"You're weighing {to_second_person(decision.content)} as an option.",
            grounding_item_ids=[decision.id],
        ))

    for unknown in state.unknowns:
        if unknown.status not in _UNKNOWN_VISIBLE_STATUSES:
            continue
        statements.append(UnderstandingStatement(
            id=f"tier1:uncertainty:{unknown.id}", tier=1, kind="uncertainty",
            text=to_second_person(unknown.content), grounding_item_ids=[unknown.id],
        ))

    for entity in state.entities:
        if entity.status not in _ENTITY_VISIBLE_STATUSES:
            continue
        if not entity.attributes and not entity.relationships:
            continue
        statements.append(UnderstandingStatement(
            id=f"tier1:entity:{entity.id}", tier=1, kind="entity",
            text=_render_entity_text(entity), grounding_item_ids=[entity.id],
        ))

    for assumption in state.assumption_items:
        if assumption.status not in _ASSUMPTION_VISIBLE_STATUSES:
            continue
        statements.append(UnderstandingStatement(
            id=f"tier1:assumption:{assumption.id}", tier=1, kind="assumption",
            text=to_second_person(assumption.content), grounding_item_ids=[assumption.id],
        ))

    for inference in state.inference_items:
        if inference.status not in _INFERENCE_VISIBLE_STATUSES:
            continue
        statements.append(UnderstandingStatement(
            id=f"tier1:inference:{inference.id}", tier=1, kind="inference",
            text=to_second_person(inference.content), grounding_item_ids=[inference.id],
        ))

    return statements
