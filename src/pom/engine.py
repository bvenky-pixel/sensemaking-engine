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

from src.instrumentation.usage import AttemptRecord, UsageTracker, default_tracker
from src.llm.providers import ProviderCallError, call_provider, resolve_provider_chain
from src.pom.prompt import build_messages
from src.pom.schema import (
    BeliefSystem,
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
    aggregated_content: str, tracker: Optional[UsageTracker] = None,
) -> PersonalOperatingModel:
    """
    Combines the two mechanical systems with the one LLM call's six
    inferred systems into a single PersonalOperatingModel. Callers (see
    scripts/run_pom_computation.py) are responsible for actually reading
    every session's WorldState and building these inputs first -- this
    module has no database dependency of its own, matching every other
    engine package's separation from src/api.
    """
    belief = compute_belief_system(claims, assumptions)
    relationship = compute_relationship_system(entities)
    inferred = run_inferred_pom(aggregated_content, tracker=tracker)

    return PersonalOperatingModel(
        belief=belief, relationship=relationship,
        identity=inferred.identity, motivation=inferred.motivation,
        learning_style=inferred.learning_style, stress=inferred.stress,
        narrative=inferred.narrative, theory_of_mind=inferred.theory_of_mind,
    )
