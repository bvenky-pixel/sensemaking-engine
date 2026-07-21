"""
Personal Operating Model engine -- see src/pom/schema.py's module
docstring for the full mechanical-vs-LLM-inferred split and the
Self-Determination-Theory/Narrative-Identity-Theory caveat.

Explicit scope decisions, mirroring src/insight/engine.py's own:
- Runs OFFLINE ONLY (scripts/run_pom_computation.py), never inside a
  live request -- same "operates asynchronously, never inside a live
  conversation turn" boundary Learning and Insight Engine already
  established. Nothing in src/api/server.py computes POM; it only reads
  whatever was last computed offline (see src/api/db.py::get_personal_operating_model).
- Mechanical systems (Belief, Relationship) are pure Python, no LLM call,
  no grounding risk -- they're a verbatim restatement of already-
  extracted, already-trusted WorldState data.
- The LLM-inferred half is ONE call, ONE schema (InferredPOMBatch) --
  same "one call, no hybrid complexity" discipline as Judgment/Planner/
  Insight Engine, not six separate calls for six separate fields.
- Engine-level grounding enforcement, not just prompt wording (mirroring
  src/insight/engine.py's own evidence_session_ids filtering, adapted to
  free-text evidence instead of ids): each evidence string is checked
  for real word overlap against the aggregated content actually sent;
  evidence with none is dropped, and a field whose evidence is entirely
  stripped this way is downgraded to "unclear" (or emptied, for
  free-text fields) rather than left asserting something ungrounded.
"""

from __future__ import annotations

import json
import re
from typing import List, Optional

from pydantic import ValidationError

from src.instrumentation.events import BehavioralEvent
from src.instrumentation.usage import AttemptRecord, UsageTracker, default_tracker
from src.llm.providers import ProviderCallError, call_provider, resolve_provider_chain
from src.pom.prompt import build_messages
from src.pom.schema import (
    BeliefSystem,
    ConfidenceLevel,
    InferredPOMBatch,
    PersonalOperatingModel,
    RelationshipSystem,
)
from src.state.world_state import Entity

TEMPERATURE = 0.15  # low: assessment/classification, not creative generation

_WORD_RE = re.compile(r"[a-z0-9']+")


def _words(text: str) -> set:
    return set(_WORD_RE.findall(text.lower()))


def _is_evidence_grounded(evidence: str, aggregated_content: str) -> bool:
    """Duplicated word-overlap check, same category as
    src/interpretation/engine.py's own _word_overlap/_is_option_grounded
    -- not imported, per this codebase's "small utility functions
    deliberately duplicated across modules" convention. A quote or close
    paraphrase of real content shares real words with it; a fabricated
    evidence string typically does not."""
    ev_words = _words(evidence)
    if not ev_words:
        return False
    return bool(ev_words & _words(aggregated_content))


def _render_entity_text(entity: Entity) -> str:
    """Duplicated from src/understanding/engine.py's own
    _render_entity_text -- same rendering, same "duplicate rather than
    import across engine packages" convention."""
    parts = [f"{attr.attribute} is {attr.value}" for attr in entity.attributes]
    parts += list(entity.relationships)
    return f"{entity.name} -- " + "; ".join(parts) + "."


def compute_belief_system(claims: List[str], assumptions: List[str]) -> BeliefSystem:
    """Mechanical: verbatim, deduplicated Claims + Assumptions content
    across every session. Order-preserving dedup (first occurrence
    wins), not sorted -- matches this codebase's general preference for
    stable, unsurprising ordering over reordering for its own sake."""
    seen = set()
    beliefs = []
    for content in claims + assumptions:
        if content not in seen:
            seen.add(content)
            beliefs.append(content)
    return BeliefSystem(beliefs=beliefs)


def compute_relationship_system(entities: List[Entity]) -> RelationshipSystem:
    """Mechanical: verbatim Entity descriptions across every session.
    Skips an Entity with no attributes/relationships -- same "a bare
    mention adds nothing a Fact doesn't already say" reasoning as
    src/understanding/engine.py's own render loop."""
    relationships = [
        _render_entity_text(e) for e in entities if e.attributes or e.relationships
    ]
    return RelationshipSystem(relationships=relationships)


# First-cut, NOT empirically calibrated -- deliberately duplicated from
# (not imported from) src/learning/engine.py's own MIN_EVIDENCE, same
# "small constants/utilities duplicated across engine packages"
# convention this module already follows for _words/_render_entity_text.
# Chosen so a single reaffirmation or a two-event coincidence can never
# override the LLM's own read; revisit once this runs against real
# usage (backlog #292).
MIN_BEHAVIORAL_EVIDENCE = 3

# event_type -> (subject label, success new_status values, struggle new_status values).
# A Goal/Decision that's still active/paused/open/deferred is in progress,
# not yet a follow-through signal either way, and is deliberately excluded
# from both counts.
_FOLLOW_THROUGH_STATUSES = {
    "decision_status_changed": ("decisions", {"resolved"}, {"deferred", "expired"}),
    "goal_status_changed": ("goals", {"completed"}, {"abandoned"}),
}


def compute_behavioral_competence(
    events: List[BehavioralEvent], min_evidence: int = MIN_BEHAVIORAL_EVIDENCE,
) -> Optional[tuple]:
    """
    Mechanical alternative to the LLM's own motivation.competence read --
    real goal/decision follow-through outcomes are more trustworthy than
    text-based inference, same "mechanical, already-trusted data wins"
    treatment compute_belief_system/compute_relationship_system already
    get (see module docstring). Pools Goal completion and Decision
    resolution together -- both speak to the same "did they see it
    through" construct competence is meant to capture.

    Returns None -- meaning "not enough evidence yet, leave the LLM's
    own read in place" -- when fewer than min_evidence follow-through
    events (combined) exist. Confirmed with the founder (2026-07-19,
    backlog #208): once the floor is met, this OVERRIDES the LLM's
    competence value and its evidence, rather than merely supplementing
    it as another line of text for the LLM to weigh.

    Bucketing thresholds (>= 2/3 success -> "high", <= 1/3 -> "low",
    else "moderate") are a first-cut, NOT empirically calibrated -- same
    honest-uncalibrated-threshold style as MIN_BEHAVIORAL_EVIDENCE
    itself.
    """
    successes: dict = {}
    struggles: dict = {}
    for event in events:
        labels = _FOLLOW_THROUGH_STATUSES.get(event.event_type)
        if labels is None:
            continue
        _, success_statuses, struggle_statuses = labels
        if event.new_status in success_statuses:
            successes[event.event_type] = successes.get(event.event_type, 0) + 1
        elif event.new_status in struggle_statuses:
            struggles[event.event_type] = struggles.get(event.event_type, 0) + 1

    total_success = sum(successes.values())
    total = total_success + sum(struggles.values())
    if total < min_evidence:
        return None

    ratio = total_success / total
    level: ConfidenceLevel = "high" if ratio >= 2 / 3 else "low" if ratio <= 1 / 3 else "moderate"

    evidence = []
    for event_type, (subject, _, _) in _FOLLOW_THROUGH_STATUSES.items():
        subtotal_success = successes.get(event_type, 0)
        subtotal = subtotal_success + struggles.get(event_type, 0)
        if subtotal:
            verb = "resolved" if event_type == "decision_status_changed" else "completed"
            stalled = "deferred/expired" if event_type == "decision_status_changed" else "abandoned"
            evidence.append(f"{subtotal_success} of {subtotal} {subject} were {verb} rather than {stalled}.")

    return level, evidence


class POMEngineError(Exception):
    """Raised when no configured provider could produce a valid InferredPOMBatch."""

    def __init__(self, message: str, raw_output: Optional[str] = None):
        super().__init__(message)
        self.raw_output = raw_output


def _ground_batch(batch: InferredPOMBatch, aggregated_content: str) -> InferredPOMBatch:
    """Filters every evidence list to entries with real word overlap
    against what was actually sent, then downgrades a field whose
    evidence was entirely stripped this way -- see module docstring."""
    identity = batch.identity.model_copy()
    identity.evidence = [e for e in identity.evidence if _is_evidence_grounded(e, aggregated_content)]
    if not identity.evidence:
        identity.self_concept = ""

    motivation = batch.motivation.model_copy()
    for dim in ("autonomy", "competence", "relatedness"):
        ev_field = f"{dim}_evidence"
        grounded = [e for e in getattr(motivation, ev_field) if _is_evidence_grounded(e, aggregated_content)]
        setattr(motivation, ev_field, grounded)
        if not grounded:
            setattr(motivation, dim, "unclear")

    learning_style = batch.learning_style.model_copy()
    learning_style.evidence = [e for e in learning_style.evidence if _is_evidence_grounded(e, aggregated_content)]
    if not learning_style.evidence:
        learning_style.style = ""

    stress = batch.stress.model_copy()
    stress.evidence = [e for e in stress.evidence if _is_evidence_grounded(e, aggregated_content)]
    if not stress.evidence:
        stress.level = "unclear"

    narrative = batch.narrative.model_copy()
    narrative.evidence = [e for e in narrative.evidence if _is_evidence_grounded(e, aggregated_content)]
    if not narrative.evidence:
        narrative.arc = "unclear"
        narrative.summary = ""

    theory_of_mind = batch.theory_of_mind.model_copy()
    grounded_entries = []
    for entry in theory_of_mind.entries:
        grounded_evidence = [e for e in entry.evidence if _is_evidence_grounded(e, aggregated_content)]
        if grounded_evidence:
            grounded_entries.append(entry.model_copy(update={"evidence": grounded_evidence}))
    theory_of_mind.entries = grounded_entries

    return InferredPOMBatch(
        identity=identity, motivation=motivation, learning_style=learning_style,
        stress=stress, narrative=narrative, theory_of_mind=theory_of_mind,
    )


def run_inferred_pom(aggregated_content: str, tracker: Optional[UsageTracker] = None) -> InferredPOMBatch:
    """
    Calls an LLM to infer the six interpretive POM systems from
    `aggregated_content` (see src/api/db.py::get_aggregated_knowledge_for_pom).
    Tries each configured provider in order, same as every other engine
    in this codebase. Raises POMEngineError if every provider fails.

    Returns an empty-default InferredPOMBatch, not an error, when
    aggregated_content is empty -- there is nothing to ground an
    inference in yet (e.g. before any session exists), so this
    short-circuits before spending an LLM call on it.
    """
    if not aggregated_content.strip():
        return InferredPOMBatch()

    system_prompt, messages = build_messages(aggregated_content)
    schema = InferredPOMBatch.model_json_schema()
    tracker = tracker or default_tracker

    failures: List[str] = []
    for provider_name in resolve_provider_chain():
        try:
            raw = call_provider(
                provider_name, system_prompt, messages, schema, TEMPERATURE,
                component="POM", tracker=tracker,
            )
        except ProviderCallError as exc:
            failures.append(f"{provider_name}: {exc}")
            tracker.record_outcome(AttemptRecord(
                component="POM", provider=provider_name,
                outcome="provider_call_error", detail=str(exc),
            ))
            continue

        raw = raw.replace("```json", "").replace("```", "").strip()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            failures.append(f"{provider_name}: model output was not valid JSON: {exc}")
            tracker.record_outcome(AttemptRecord(
                component="POM", provider=provider_name,
                outcome="invalid_json", detail=str(exc),
            ))
            continue

        try:
            result = InferredPOMBatch(**data)
        except ValidationError as exc:
            failures.append(f"{provider_name}: model output failed schema validation: {exc}")
            tracker.record_outcome(AttemptRecord(
                component="POM", provider=provider_name,
                outcome="schema_validation_failed", detail=str(exc),
            ))
            continue

        tracker.record_outcome(AttemptRecord(
            component="POM", provider=provider_name, outcome="success",
        ))
        return _ground_batch(result, aggregated_content)

    raise POMEngineError("All configured LLM providers failed: " + "; ".join(failures))


def compute_personal_operating_model(
    claims: List[str], assumptions: List[str], entities: List[Entity],
    aggregated_content: str, events: List[BehavioralEvent],
    tracker: Optional[UsageTracker] = None,
) -> PersonalOperatingModel:
    """
    Combines the two mechanical systems with the one LLM call's six
    inferred systems into a single PersonalOperatingModel. Callers (see
    scripts/run_pom_computation.py) are responsible for actually reading
    every session's WorldState and building these inputs first -- this
    module has no database dependency of its own, matching every other
    engine package's separation from src/api.

    `events` (this account's own behavioral_events, see
    src.api.db.get_events_for_user) feeds compute_behavioral_competence:
    when there's enough goal/decision follow-through evidence, its
    mechanical read OVERRIDES motivation.competence and its evidence
    (backlog #208) -- otherwise the LLM's own inference for competence
    stands untouched, same as every other Motivation dimension.
    """
    belief = compute_belief_system(claims, assumptions)
    relationship = compute_relationship_system(entities)
    inferred = run_inferred_pom(aggregated_content, tracker=tracker)

    motivation = inferred.motivation
    behavioral_competence = compute_behavioral_competence(events)
    if behavioral_competence is not None:
        level, evidence = behavioral_competence
        motivation = motivation.model_copy(update={"competence": level, "competence_evidence": evidence})

    return PersonalOperatingModel(
        belief=belief, relationship=relationship,
        identity=inferred.identity, motivation=motivation,
        learning_style=inferred.learning_style, stress=inferred.stress,
        narrative=inferred.narrative, theory_of_mind=inferred.theory_of_mind,
    )
