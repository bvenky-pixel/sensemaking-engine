"""
Merges an Interpretation (one turn's structured meaning) into the running
WorldState (the accumulated model of the user's world) -- see
src/state/world_state.py for the v1 scope decision and known limitations.

This must accumulate, not overwrite. The constitution's Method depends on
it: Phase 3's success criterion is the user recognizing an assumption
they raised earlier ("I hadn't realized I was assuming that") -- which
requires that assumption to still be present in state several turns
later, not wiped out by whatever the latest turn happened to say.

Epistemic tiers (observed_facts / claims / assumptions / inferences /
unknowns / biases) are preserved as separate fields all the way through
to WorldState -- see src/interpretation/schema.py and engine/decisions.md
for why collapsing them was the root cause of advice and world-knowledge
leaking into state in an earlier version.
"""

from __future__ import annotations

from typing import List, Tuple

from src.interpretation.schema import Interpretation
from src.state.world_state import (
    Claim,
    Decision,
    Entity,
    Fact,
    Goal,
    Unknown,
    WorldState,
)

# Emotional intensity in Interpretation is 0.0-1.0; the render layer
# multiplies by this for display (matches the Pydantic mirror in
# engine/state_updater.py, kept in sync for the eventual Claude swap).
INTENSITY_SCALE = 10

# Inferences below this confidence don't get promoted into state. See
# engine/decisions.md 2026-07-02 "v0.6" for why this is 0.15, not 0.5:
# a 0.5 floor was set when the problem was over-confident fabrication,
# but under proper calibration a genuinely weak-but-real read correctly
# scores 0.2-0.3 -- a higher floor would silently discard exactly the
# honest low-confidence signal the prompt is now taught to produce.
INFERENCE_CONFIDENCE_FLOOR = 0.15

def _merge_unique(existing: List[str], new: List[str]) -> List[str]:
    """Append new items not already present, preserving order."""
    merged = list(existing)
    for item in new:
        if item not in merged:
            merged.append(item)
    return merged


def _merge_content_items(existing: list, new_contents: List[str], model_cls) -> list:
    """
    Generic merge for the typed Fact/Claim/Goal/Decision/Unknown tiers:
    dedup by content (case-insensitive), append genuinely new items as a
    fresh instance of model_cls with its default status. Existing items
    are returned unchanged -- status transitions are handled by whichever
    caller has the signal for them (see _reconcile_unknowns below for the
    one transition Interpretation actually gives us evidence for).
    """
    result = list(existing)
    seen = {item.content.strip().lower() for item in result}
    for content in new_contents:
        key = content.strip().lower()
        if key not in seen:
            result.append(model_cls(content=content))
            seen.add(key)
    return result


def _reconcile_unknowns(
    existing: List[Unknown], new_unknowns: List[str], resolved_by: List[str]
) -> Tuple[List[Unknown], List[str]]:
    """
    Drop any existing unknown that a newly-stated fact/claim appears to
    resolve (simple substring check -- good enough for v1, revisit if it
    proves too blunt), then merge in genuinely new unknowns. Returns the
    updated unknowns list plus the content of any unknowns resolved this
    turn, so the caller can promote them into Facts.

    TODO (see Unknown's status field in src/state/world_state.py): this
    removes a resolved unknown outright rather than marking its status
    "resolved" and retaining it -- Design Principle 3 ("nothing is
    silently deleted") would argue for the latter, matching Facts/Claims.
    Not changed here since that's a merge-behavior change beyond this
    round's ask (standardizing shape), not a shape change.
    """
    still_open = []
    resolved_contents = []
    for u in existing:
        if any(u.content.lower() in f.lower() or f.lower() in u.content.lower() for f in resolved_by):
            resolved_contents.append(u.content)
        else:
            still_open.append(u)

    merged = _merge_content_items(still_open, new_unknowns, Unknown)
    return merged, resolved_contents


def _merge_entities(existing: List[Entity], new_names: List[str]) -> List[Entity]:
    """Enrich existing entities by name (case-insensitive), never duplicate."""
    result = list(existing)
    by_name = {e.name.strip().lower(): e for e in result}
    for name in new_names:
        key = name.strip().lower()
        if key not in by_name:
            entity = Entity(name=name)
            result.append(entity)
            by_name[key] = entity
        # Enrichment (attributes/relationships) has no data source yet --
        # see src/state/world_state.py module docstring.
    return result


def update_state(state: WorldState, interp: Interpretation) -> WorldState:
    new_state = state.model_copy(deep=True)  # never mutate the caller's state

    # --- Phase 2 ---
    new_state.surface_complaint = interp.surface_complaint or state.surface_complaint
    # Only move core_question when this turn is at least as confident as
    # what we already had -- otherwise a low-confidence turn could regress
    # a real question we'd already found back to a vague symptom.
    if interp.core_question_confidence >= state.core_question_confidence:
        new_state.core_question = interp.core_question
        new_state.core_question_confidence = interp.core_question_confidence

    # --- Phase 3: epistemic tiers, kept separate, never flattened ---
    new_state.facts = _merge_content_items(state.facts, interp.observed_facts, Fact)
    new_state.claims = _merge_content_items(state.claims, interp.claims, Claim)
    new_state.goals = _merge_content_items(state.goals, interp.goals, Goal)
    new_state.decisions = _merge_content_items(state.decisions, interp.decision_options, Decision)
    new_state.assumptions = _merge_unique(state.assumptions, interp.assumptions)

    kept_inferences = [
        f"{inf.reading} (confidence={inf.confidence:.2f})"
        for inf in interp.inferences
        if inf.confidence >= INFERENCE_CONFIDENCE_FLOOR
    ]
    new_state.inferences = _merge_unique(state.inferences, kept_inferences)

    updated_unknowns, resolved = _reconcile_unknowns(
        state.unknowns, interp.unknowns, interp.observed_facts + interp.claims
    )
    new_state.unknowns = updated_unknowns
    if resolved:
        # Resolved unknowns become facts (spec: "Unknowns -- Remove only
        # when answered. Resolved unknowns become facts.").
        new_state.facts = _merge_content_items(new_state.facts, resolved, Fact)

    new_state.biases = _merge_unique(state.biases, [b.bias for b in interp.biases])
    new_state.entities = _merge_entities(state.entities, interp.entities)
    new_state.clarity_level = interp.clarity_score

    return new_state
