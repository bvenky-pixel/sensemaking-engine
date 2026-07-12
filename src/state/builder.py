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

import re
from typing import List, Optional, Tuple

from src.interpretation.schema import (
    DecisionEvent,
    EntityAttributeUpdate,
    GoalUpdate,
    Interpretation,
)
from src.judgment.schema import Judgment
from src.state.world_state import (
    Assumption,
    Claim,
    Decision,
    Entity,
    EntityAttribute,
    Fact,
    Goal,
    Inference,
    Provenance,
    Unknown,
    WorldState,
)

# Emotional intensity in Interpretation is 0.0-1.0; the render layer
# multiplies by this for display (matches the Pydantic mirror in
# engine/state_updater.py, kept in sync for the eventual Claude swap).
INTENSITY_SCALE = 10

# Confidence tiers (added 2026-07-12, see engine/decisions.md
# "Understanding layer -- Journey-scoped identity"): KnowledgeItem.confidence
# was a dead placeholder field until now -- these constants populate it
# deterministically by which knowledge-item TYPE an item is, not via a
# new per-item LLM output (no evidence Interpretation can reliably
# produce that). Directly extends this module's own long-standing
# "epistemic tiers" concept (see module docstring above) into an actual
# numeric ordering: Fact/Goal/Decision are directly stated (highest);
# Claim is interpretive (lower); Assumption is the lowest durable tier,
# since Interpretation's `assumptions` field has no per-item signal at
# all to draw from. Unknown/Entity are deliberately left at the base
# `confidence=None` default -- a question or a named party isn't a
# confidence-bearing claim in the same sense, and nothing asked for a
# tier on those. Inference is the one exception to "tier constant, not
# real data" -- see the Inference-specific comment further down, where
# its confidence comes from Interpretation's own calibrated per-item
# value instead.
FACT_TIER_CONFIDENCE = 1.0
GOAL_TIER_CONFIDENCE = 1.0
DECISION_TIER_CONFIDENCE = 1.0
CLAIM_TIER_CONFIDENCE = 0.7
ASSUMPTION_TIER_CONFIDENCE = 0.3

# Inferences below this confidence don't get promoted into state. See
# engine/decisions.md 2026-07-02 "v0.6" for why this is 0.15, not 0.5:
# a 0.5 floor was set when the problem was over-confident fabrication,
# but under proper calibration a genuinely weak-but-real read correctly
# scores 0.2-0.3 -- a higher floor would silently discard exactly the
# honest low-confidence signal the prompt is now taught to produce.
INFERENCE_CONFIDENCE_FLOOR = 0.15

# The WorldState walkthrough (2026-07-05) surfaced a real doubled-annotation
# case: the model sometimes writes its own "(confidence=0.5)" directly into
# an Inference's `reading` text, and this module then appends its own
# canonical one on top, producing "... (confidence=0.5) (confidence=0.50)"
# in rendered state. Strip any model-embedded confidence annotation before
# formatting so only the canonical one (below) ever appears.
_EMBEDDED_CONFIDENCE = re.compile(r"\s*\(confidence\s*=\s*[\d.]+\)", re.IGNORECASE)


def _clean_reading(reading: str) -> str:
    return _EMBEDDED_CONFIDENCE.sub("", reading).strip()


# Word-overlap scoring for unknown resolution, deliberately DUPLICATED
# (not imported) from src/interpretation/engine.py's _word_overlap rather
# than sharing a module -- that file implements the frozen v1.0
# Interpretation layer, and this avoids taking any dependency on / risk to
# frozen code for what's otherwise a one-line algorithm. Same approach,
# same word-set-intersection-ratio mechanics; kept independently
# versionable since the two use cases (grounding a model's own extraction
# against raw user text vs. matching two model outputs against each other
# across turns) may reasonably diverge later.
_WORD_RE = re.compile(r"[a-z']+")


def _word_set(text: str) -> set:
    return set(_WORD_RE.findall(text.lower()))


def _word_overlap(text: str, reference: str) -> float:
    """Fraction of `text`'s words that also appear in `reference`."""
    text_words = _word_set(text)
    if not text_words:
        return 0.0
    return len(text_words & _word_set(reference)) / len(text_words)


# First-cut threshold, NOT empirically calibrated the way Interpretation's
# own thresholds were (those went through live n=10/n=20 testing -- see
# engine/decisions.md). Checked in both directions so either a broad
# unknown resolved by a specific fact, or a specific unknown resolved by a
# broad fact, can fire. Revisit once real conversations show whether 0.5
# is too strict or too loose -- this replaces a strictly worse mechanism
# (exact substring containment), it isn't claimed to solve the deeper
# semantic-gap cases (see engine/decisions.md "Confirmed gap 2" -- those
# are explicitly out of scope for this layer, not something this threshold
# is meant to catch).
UNKNOWN_RESOLUTION_OVERLAP_THRESHOLD = 0.5


def _is_resolved_by(unknown_content: str, candidate: str) -> bool:
    return (
        _word_overlap(unknown_content, candidate) >= UNKNOWN_RESOLUTION_OVERLAP_THRESHOLD
        or _word_overlap(candidate, unknown_content) >= UNKNOWN_RESOLUTION_OVERLAP_THRESHOLD
    )


def _merge_unique(existing: List[str], new: List[str]) -> List[str]:
    """Append new items not already present, preserving order."""
    merged = list(existing)
    for item in new:
        if item not in merged:
            merged.append(item)
    return merged


def _merge_content_items(
    existing: list,
    new_contents: List[str],
    model_cls,
    turn: int,
    confidence: Optional[float] = None,
    case_insensitive: bool = True,
) -> list:
    """
    Generic merge for the typed Fact/Claim/Goal/Decision/Unknown/
    Assumption/Inference tiers: dedup by content, append genuinely new
    items as a fresh instance of model_cls with its default status.
    Existing items are returned unchanged -- status transitions are
    handled by whichever caller has the signal for them (see
    _reconcile_unknowns below for the one transition Interpretation
    actually gives us evidence for).

    `turn` (added 2026-07-10, see engine/decisions.md "WorldState
    provenance -- trajectory prerequisite") stamps every newly created
    item with Provenance(first_seen=last_updated=turn) -- always
    "interpretation" as source, since that's the only thing that ever
    creates a new KnowledgeItem. A reaffirmed-but-unchanged existing item
    is still returned untouched, same as before this field existed --
    dedup happens before this loop even sees it.

    `confidence` (added 2026-07-12): stamps every newly created item with
    this fixed tier value (see FACT_TIER_CONFIDENCE and siblings above).
    None (the default) leaves KnowledgeItem.confidence at its own base
    default -- used for Unknown, which isn't a confidence-bearing claim.

    `case_insensitive` (added 2026-07-12): defaults to True, preserving
    this function's original dedup behavior exactly for its five
    pre-existing callers (Fact/Claim/Goal/Decision/Unknown). Set to False
    for assumption_items/inference_items so their membership can't
    silently diverge from the existing flat assumptions/inferences string
    lists, which dedup via _merge_unique's exact-match semantics, not
    this function's case-insensitive default.
    """
    result = list(existing)
    key_fn = (lambda c: c.strip().lower()) if case_insensitive else (lambda c: c.strip())
    seen = {key_fn(item.content) for item in result}
    for content in new_contents:
        key = key_fn(content)
        if key not in seen:
            result.append(
                model_cls(
                    content=content,
                    confidence=confidence,
                    provenance=Provenance(source="interpretation", first_seen=turn, last_updated=turn),
                )
            )
            seen.add(key)
    return result


# v1.1 (see engine/decisions.md and engine/specs/interpretation-spec-v1.1.md):
# consumes Interpretation's goal_updates/decision_events/
# entity_attribute_updates -- the real upstream signal the standing
# principle ("the State Builder must not compensate for a missing
# semantic signal with a heuristic") called for. Matching a `GoalUpdate`/
# `DecisionEvent` target to an existing stored item still uses text
# similarity (WorldState has no stable object IDs yet -- deferred to
# v1.1 provenance work per world_state.py's module docstring), so this
# is a narrower, more mechanical lookup than the fabrication these
# functions replace, not a claim of full semantic matching. An update
# with no sufficiently-similar existing item is dropped, never used to
# fabricate a new one -- goal_updates/decision_events are exclusively for
# transitions on something already tracked.

# DecisionEvent.event -> DecisionStatus. "proposed" isn't mapped: a
# proposed option is what `decision_options` already covers (a fresh
# extraction), so a "proposed" event on an existing option is a no-op
# here. "deferred" now maps to its own real DecisionStatus (added
# 2026-07-10, see engine/decisions.md) -- the 10-turn WorldState
# walkthrough surfaced a real "wait and see" resolution that is neither
# "resolved" (the user hasn't ruled anything out permanently) nor
# correctly left "open" (the user did just act on it this turn) --
# closing the gap this dict's own prior comment had already flagged as
# deliberately incomplete.
_DECISION_EVENT_TO_STATUS = {
    "chosen": "resolved",
    "rejected": "resolved",
    "deferred": "deferred",
}


def _apply_goal_updates(goals: List[Goal], updates: List[GoalUpdate], turn: int) -> List[Goal]:
    """
    Transition an existing Goal's status when a GoalUpdate's `goal` text
    sufficiently overlaps an existing goal's content (same bidirectional
    word-overlap check as unknown resolution). No match -> dropped, never
    used to fabricate a new Goal (that's `goals: List[str]`'s job).

    `turn` (added 2026-07-10, see engine/decisions.md "WorldState
    provenance -- trajectory prerequisite") bumps the matched Goal's
    provenance.last_updated -- first_seen/source are left untouched, since
    this is a status change on an existing item, not a new one.
    """
    result = list(goals)
    for update in updates:
        for g in result:
            if _is_resolved_by(update.goal, g.content) or _is_resolved_by(g.content, update.goal):
                g.status = update.status
                if g.provenance is not None:
                    g.provenance.last_updated = turn
                break
    return result


def _apply_decision_events(
    decisions: List[Decision], events: List[DecisionEvent], turn: int
) -> List[Decision]:
    """Same matching mechanism as _apply_goal_updates, for Decisions --
    including the same provenance.last_updated bump on a matched item."""
    result = list(decisions)
    for event in events:
        new_status = _DECISION_EVENT_TO_STATUS.get(event.event)
        if new_status is None:
            continue
        for d in result:
            if _is_resolved_by(event.option, d.content) or _is_resolved_by(d.content, event.option):
                d.status = new_status
                if d.provenance is not None:
                    d.provenance.last_updated = turn
                break
    return result


def apply_judgment_resolutions(state: WorldState, judgment: Judgment) -> WorldState:
    """
    Applies Judgment.decision_resolutions to WorldState.decisions --
    added 2026-07-10 (see engine/decisions.md "decision lifecycle, round
    3") after Interpretation's own decision_events (even with its
    boolean-gate escalation) proved structurally unable to fix this:
    Interpretation is a stateless, single-message function that never
    sees WorldState, so it can only guess at a previous turn's exact
    decision_option text, never reliably reproduce it. Judgment reads
    the full WorldState verbatim every turn, so `option` here should
    almost always be an exact (or near-exact) match -- still routed
    through the same `_is_resolved_by` word-overlap check as
    `_apply_decision_events` for consistency and light tolerance to
    quoting variation, not because a fuzzy match is expected to be doing
    much work here.

    Called by the orchestrator AFTER `run_judgment` returns (Judgment
    itself only ever reads WorldState, per its own design principles --
    this function is what turns Judgment's read-only assessment into the
    one exception: a write-back), so this turn's Planner/Response see
    the corrected status, and so does every later turn's WorldState.

    Stamps provenance.last_updated using state.turn_count (added 2026-07-10,
    see engine/decisions.md "WorldState provenance -- trajectory
    prerequisite") -- already incremented earlier this same turn by
    update_state, so this does NOT increment it again; exactly one
    increment per turn, owned solely by update_state.
    """
    new_state = state.model_copy(deep=True)  # never mutate the caller's state
    for resolution in judgment.decision_resolutions:
        for d in new_state.decisions:
            if _is_resolved_by(resolution.option, d.content) or _is_resolved_by(d.content, resolution.option):
                d.status = resolution.status
                if d.provenance is not None:
                    d.provenance.last_updated = new_state.turn_count
                break
    return new_state


def _reconcile_unknowns(
    existing: List[Unknown], new_unknowns: List[str], resolved_by: List[str], turn: int
) -> Tuple[List[Unknown], List[str]]:
    """
    Drop any existing unknown that a newly-stated fact/claim appears to
    resolve (word-overlap check, see _is_resolved_by -- replaces the
    original exact-substring check, which the 2026-07-05 WorldState
    walkthrough confirmed missed realistic paraphrasing), then merge in
    genuinely new unknowns. Returns the updated unknowns list plus the
    content of any unknowns resolved this turn, so the caller can promote
    them into Facts.

    This is still a lexical heuristic, not real semantic resolution --
    deep semantic gaps (a question and its answer sharing no content
    words) are explicitly out of scope for this layer per engine/decisions.md
    "Confirmed gap 2": that needs a real signal from a richer Interpretation
    schema or from Judgment, not a better string-matching trick here.

    TODO (see Unknown's status field in src/state/world_state.py): this
    removes a resolved unknown outright rather than marking its status
    "resolved" and retaining it -- Design Principle 3 ("nothing is
    silently deleted") would argue for the latter, matching Facts/Claims.
    Not changed here since that's a merge-behavior change beyond this
    round's ask, not a shape change.
    """
    still_open = []
    resolved_contents = []
    for u in existing:
        if any(_is_resolved_by(u.content, f) for f in resolved_by):
            resolved_contents.append(u.content)
        else:
            still_open.append(u)

    merged = _merge_content_items(still_open, new_unknowns, Unknown, turn)
    return merged, resolved_contents


def _merge_entities(
    existing: List[Entity],
    new_names: List[str],
    attribute_updates: List[EntityAttributeUpdate],
    turn: int,
) -> List[Entity]:
    """
    Enrich existing entities by name (case-insensitive), never duplicate.

    v1.1: attribute_updates now gives this function a real data source
    for Entity.attributes (previously always []). An update for an entity
    matched by name gets its attribute set (replacing any prior value for
    that same attribute key -- Design Principle 2, "refine, don't
    replace," applied at the attribute level: the entity record isn't
    replaced, just this one attribute's current value). An update whose
    entity was never separately mentioned in `new_names` still creates
    the entity -- the attribute statement itself is evidence the entity
    exists, not a reason to drop it.

    `turn` (added 2026-07-10, see engine/decisions.md "WorldState
    provenance -- trajectory prerequisite") stamps every newly created
    Entity the same way _merge_content_items does. Enriching an EXISTING
    entity's attributes does NOT bump last_updated -- out of scope this
    round (trajectory only cares about Goal/Decision status transitions,
    per the approved plan; entities aren't part of that).
    """
    result = list(existing)
    by_name = {e.name.strip().lower(): e for e in result}
    for name in new_names:
        key = name.strip().lower()
        if key not in by_name:
            entity = Entity(
                name=name,
                provenance=Provenance(source="interpretation", first_seen=turn, last_updated=turn),
            )
            result.append(entity)
            by_name[key] = entity

    for update in attribute_updates:
        key = update.entity.strip().lower()
        entity = by_name.get(key)
        if entity is None:
            entity = Entity(
                name=update.entity,
                provenance=Provenance(source="interpretation", first_seen=turn, last_updated=turn),
            )
            result.append(entity)
            by_name[key] = entity
        for existing_attr in entity.attributes:
            if existing_attr.attribute.strip().lower() == update.attribute.strip().lower():
                existing_attr.value = update.value
                break
        else:
            entity.attributes.append(
                EntityAttribute(attribute=update.attribute, value=update.value)
            )

    return result


def update_state(state: WorldState, interp: Interpretation) -> WorldState:
    new_state = state.model_copy(deep=True)  # never mutate the caller's state

    # v1.1 (added 2026-07-10, see engine/decisions.md "WorldState
    # provenance -- trajectory prerequisite"): exactly one increment per
    # turn, owned solely here -- update_state is the single per-turn
    # WorldState mutation entrypoint, unconditionally called every turn by
    # the Orchestrator. Every provenance stamp this turn (below, and later
    # in apply_judgment_resolutions) uses this same value.
    new_state.turn_count = state.turn_count + 1
    turn = new_state.turn_count

    # --- Phase 2 ---
    new_state.surface_complaint = interp.surface_complaint or state.surface_complaint
    # Only move core_question when this turn is at least as confident as
    # what we already had -- otherwise a low-confidence turn could regress
    # a real question we'd already found back to a vague symptom.
    if interp.core_question_confidence >= state.core_question_confidence:
        new_state.core_question = interp.core_question
        new_state.core_question_confidence = interp.core_question_confidence

    # --- Phase 3: epistemic tiers, kept separate, never flattened ---
    #
    # BUG FIX (found during Phase 1 Learning implementation, see
    # engine/decisions.md): every _merge_content_items/_merge_entities call
    # below previously sourced its `existing` argument from `state.X` (the
    # caller's ORIGINAL, pre-deep-copy lists) instead of `new_state.X` (the
    # deep copy made at the top of this function specifically so the
    # caller's state would never be mutated). _merge_content_items's
    # "existing items are returned unchanged" only copies the LIST, not
    # each item inside it -- so the Goal/Decision/Entity objects placed
    # into new_state.goals/decisions/entities were literally the same
    # objects still referenced by the caller's original `state`. Every
    # in-place status mutation downstream (_apply_goal_updates,
    # _apply_decision_events, _merge_entities' attribute refinement) then
    # silently corrupted the caller's own state object -- invisible until
    # now because no previous caller ever kept a separate reference to the
    # pre-turn state to notice. Sourcing from new_state.X (already an
    # independent deep copy) instead of state.X fixes this without
    # changing any merge/dedup semantics.
    new_state.facts = _merge_content_items(
        new_state.facts, interp.observed_facts, Fact, turn, confidence=FACT_TIER_CONFIDENCE
    )
    new_state.claims = _merge_content_items(
        new_state.claims, interp.claims, Claim, turn, confidence=CLAIM_TIER_CONFIDENCE
    )
    new_state.goals = _merge_content_items(
        new_state.goals, interp.goals, Goal, turn, confidence=GOAL_TIER_CONFIDENCE
    )
    new_state.goals = _apply_goal_updates(new_state.goals, interp.goal_updates, turn)
    new_state.decisions = _merge_content_items(
        new_state.decisions, interp.decision_options, Decision, turn, confidence=DECISION_TIER_CONFIDENCE
    )
    new_state.decisions = _apply_decision_events(new_state.decisions, interp.decision_events, turn)
    new_state.assumptions = _merge_unique(state.assumptions, interp.assumptions)

    # Added 2026-07-12, see engine/decisions.md "Understanding layer --
    # Journey-scoped identity": an id-bearing, groundable counterpart to
    # the flat assumptions list just above -- deliberately additive, not
    # a replacement (see Assumption's own docstring in world_state.py).
    # case_insensitive=False mirrors _merge_unique's exact-match dedup
    # exactly, so this list's membership never silently diverges from the
    # flat assumptions list's.
    new_state.assumption_items = _merge_content_items(
        new_state.assumption_items, interp.assumptions, Assumption, turn,
        confidence=ASSUMPTION_TIER_CONFIDENCE, case_insensitive=False,
    )

    kept_inferences = [
        f"{_clean_reading(inf.reading)} (confidence={inf.confidence:.2f})"
        for inf in interp.inferences
        if inf.confidence >= INFERENCE_CONFIDENCE_FLOOR
    ]
    new_state.inferences = _merge_unique(state.inferences, kept_inferences)

    # Same pattern as assumption_items above, for inferences -- but with
    # REAL per-item confidence (Interpretation's own calibrated
    # Inference.confidence), not a flat tier constant, since that signal
    # actually exists here. content is the cleaned reading only (no
    # embedded "(confidence=X)" suffix -- confidence is now a structured
    # field) so it intentionally is NOT byte-identical to the
    # corresponding kept_inferences string, which keeps its own suffix.
    kept_inference_objs = [inf for inf in interp.inferences if inf.confidence >= INFERENCE_CONFIDENCE_FLOOR]
    existing_inference_keys = {i.content.strip() for i in new_state.inference_items}
    for inf in kept_inference_objs:
        cleaned = _clean_reading(inf.reading)
        key = cleaned.strip()
        if key not in existing_inference_keys:
            new_state.inference_items.append(
                Inference(
                    content=cleaned,
                    confidence=inf.confidence,
                    provenance=Provenance(source="interpretation", first_seen=turn, last_updated=turn),
                )
            )
            existing_inference_keys.add(key)

    updated_unknowns, resolved = _reconcile_unknowns(
        new_state.unknowns, interp.unknowns, interp.observed_facts + interp.claims, turn
    )
    new_state.unknowns = updated_unknowns
    if resolved:
        # Resolved unknowns become facts (spec: "Unknowns -- Remove only
        # when answered. Resolved unknowns become facts.").
        new_state.facts = _merge_content_items(
            new_state.facts, resolved, Fact, turn, confidence=FACT_TIER_CONFIDENCE
        )

    new_state.biases = _merge_unique(state.biases, [b.bias for b in interp.biases])
    new_state.entities = _merge_entities(
        new_state.entities, interp.entities, interp.entity_attribute_updates, turn
    )
    new_state.clarity_level = interp.clarity_score

    return new_state
