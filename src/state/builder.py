"""
Merges an Interpretation (one turn's structured meaning) into the running
ConversationState (the accumulated model of the user's thinking).

This must accumulate, not overwrite. The constitution's Method depends on
it: Phase 3's success criterion is the user recognizing an assumption
they raised earlier ("I hadn't realized I was assuming that") -- which
requires that assumption to still be present in state several turns
later, not wiped out by whatever the latest turn happened to say.
"""

from __future__ import annotations

from dataclasses import replace
from typing import List

from src.interpretation.schema import Interpretation

# Emotional intensity in Interpretation is 0.0-1.0; ConversationState
# stores it as an int 0-10 (matches the Pydantic mirror in
# engine/state_updater.py, kept in sync for the eventual Claude swap).
INTENSITY_SCALE = 10


def _merge_unique(existing: List[str], new: List[str]) -> List[str]:
    """Append new items not already present, preserving order."""
    merged = list(existing)
    for item in new:
        if item not in merged:
            merged.append(item)
    return merged


def _reconcile_unknowns(existing: List[str], new_unknowns: List[str], resolved_by: List[str]) -> List[str]:
    """
    Drop any existing unknown that a newly-stated fact appears to resolve
    (simple substring check -- good enough for MVP, revisit if it proves
    too blunt), then merge in genuinely new unknowns.
    """
    still_open = [
        u for u in existing
        if not any(u.lower() in f.lower() or f.lower() in u.lower() for f in resolved_by)
    ]
    return _merge_unique(still_open, new_unknowns)


def update_state(state, interp: Interpretation):
    new_state = replace(state)  # never mutate the caller's state in place

    # --- Phase 1 ---
    new_state.urgency = interp.urgency
    new_state.stakes = interp.stakes or state.stakes
    if interp.emotional_signals:
        top = max(interp.emotional_signals, key=lambda e: e.intensity)
        new_state.emotion = top.emotion
        new_state.emotion_intensity = round(top.intensity * INTENSITY_SCALE)

    # --- Phase 2 ---
    new_state.surface_complaint = interp.surface_complaint or state.surface_complaint
    # Only move core_problem when this turn is at least as confident as
    # what we already had -- otherwise a low-confidence turn could regress
    # a real question we'd already found back to a vague symptom.
    if interp.core_question_confidence >= state.core_problem_confidence:
        new_state.core_problem = interp.core_question
        new_state.core_problem_confidence = interp.core_question_confidence

    # --- Phase 3 ---
    new_state.facts = _merge_unique(state.facts, interp.facts)
    new_state.interpretations = _merge_unique(state.interpretations, interp.interpretations)
    new_state.assumptions = _merge_unique(
        state.assumptions, [a.assumption for a in interp.assumptions]
    )
    new_state.unknowns = _reconcile_unknowns(state.unknowns, interp.unknowns, interp.facts)
    new_state.biases = _merge_unique(state.biases, [b.bias for b in interp.biases])

    new_state.stakeholders = _merge_unique(state.stakeholders, interp.entities)
    new_state.clarity_level = interp.clarity_score

    return new_state
