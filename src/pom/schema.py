"""
Personal Operating Model (POM) schema -- the vision doc's Layer 4 (see
engine/specs/architecture-roadmap-v1.md, engine/decisions.md "Personal
Operating Model"). Of the vision's nine POM systems, one (Behavioral
Pattern System) already shipped as Layer 2 Learning
(src/learning/engine.py). This module covers the other eight.

**Formulation confirmed by the founder (2026-07-19, backlog #291,
see engine/decisions.md)**: the founder's original vision documents
(`Confidant_Personal_Operation_Model.docx` and friends) were never
committed to this repository -- they were shared earlier in this
project's history as uploaded context, not committed files. The exact
operationalization of Motivation/Narrative below uses the STANDARD,
textbook versions of the two named frameworks (Self-Determination
Theory's autonomy/competence/relatedness; Narrative Identity Theory's
redemption/contamination sequences). Asked the founder directly whether
this matches their original intent for these two systems -- confirmed
yes, no changes needed.

The user explicitly chose to build all eight systems now, overriding
this project's own default caution (recommended scoping to just Belief
+ Relationship, the two that reduce to existing structured data with no
invented scoring) -- see engine/decisions.md "Personal Operating Model"
for that conversation. Six of the eight (Identity, Motivation, Learning
Style, Stress, Narrative, Theory of Mind) genuinely require inventing a
scored/interpreted model with no evidence yet to calibrate it against --
that risk is accepted here, explicitly, at the user's own direction, not
silently.

Split, same discipline as everywhere else in this codebase (never invent
a mechanism where a cheaper, already-trusted one exists):

MECHANICAL (no LLM call, pure aggregation of already-extracted,
already-trusted WorldState data, across every session):
- Belief -- Claims + Assumptions, verbatim.
- Relationship -- Entities, verbatim.

LLM-INFERRED (one call, one schema -- same "one call, no hybrid
complexity" discipline as Judgment/Planner/Insight Engine; genuinely
interpretive, cannot be reduced to a formula):
- Identity, Motivation, Learning Style, Stress, Narrative, Theory of
  Mind.

Every LLM-inferred field uses a coarse, closed scale (e.g. "low"/
"moderate"/"high"/"unclear") rather than a float -- a numeric score
(e.g. 0.63) would imply a precision this data cannot support, since
nothing here has been calibrated against ground truth the way, say,
Judgment's confidence field at least has some real usage behind it.
Every field also carries its own grounding evidence, same discipline as
Judgment's supporting_evidence / Insight's evidence_session_ids: never
trust a score without being able to see what it was based on.
"""

from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, Field

# Caps how many of this account's own sessions feed POM's aggregation
# (src/api/db.py::get_aggregated_knowledge_for_pom) -- most-recently-
# updated sessions win. Added 2026-07-19, backlog #272: POM's aggregation
# was uncapped (all-history) until now, on the reasoning that a standing
# profile benefits from every session, not a recency-capped sample; the
# founder explicitly chose to cap it instead now that POM is per-account
# (see engine/decisions.md "POM: recency cap added to aggregation"),
# overriding that original reasoning. Deliberately duplicated from (not
# imported from) src/insight/schema.py's own MAX_SESSIONS_FOR_INSIGHT,
# same "small constants duplicated across engine packages" convention
# this module's own MIN_BEHAVIORAL_EVIDENCE precedent (src/pom/engine.py)
# already follows -- same value, but POM and Insight Engine may want to
# tune this independently later, and nothing here couples them. Honest
# first guess, not empirically calibrated (see backlog #292).
MAX_SESSIONS_FOR_POM = 30

# --- Mechanical systems (no LLM call) ---


class BeliefSystem(BaseModel):
    """Aggregated Claims + Assumptions, verbatim, across every session --
    a plain restatement of what's already been extracted, not a new
    interpretation. `beliefs` is deduplicated but otherwise unmodified
    content text."""

    beliefs: List[str] = Field(default_factory=list)


class RelationshipSystem(BaseModel):
    """Aggregated Entity descriptions, verbatim, across every session --
    same "restate, don't reinterpret" discipline as BeliefSystem above."""

    relationships: List[str] = Field(default_factory=list)


# --- LLM-inferred systems (one call, shared schema below) ---

ConfidenceLevel = Literal["low", "moderate", "high", "unclear"]


class IdentitySystem(BaseModel):
    self_concept: str = ""
    evidence: List[str] = Field(default_factory=list)


class MotivationSystem(BaseModel):
    """Self-Determination Theory's three core dimensions (Deci & Ryan) --
    the standard textbook formulation, confirmed by the founder as
    matching their intent (see this module's own docstring above,
    backlog #291)."""

    autonomy: ConfidenceLevel = "unclear"
    autonomy_evidence: List[str] = Field(default_factory=list)
    competence: ConfidenceLevel = "unclear"
    competence_evidence: List[str] = Field(default_factory=list)
    relatedness: ConfidenceLevel = "unclear"
    relatedness_evidence: List[str] = Field(default_factory=list)


class LearningStyleSystem(BaseModel):
    style: str = ""
    evidence: List[str] = Field(default_factory=list)


class StressSystem(BaseModel):
    level: ConfidenceLevel = "unclear"
    evidence: List[str] = Field(default_factory=list)


NarrativeArc = Literal["redemptive", "contamination", "stable", "unclear"]


class NarrativeSystem(BaseModel):
    """Narrative Identity Theory's two classic sequence types (McAdams) --
    same founder-confirmed formulation as MotivationSystem (backlog #291)."""

    arc: NarrativeArc = "unclear"
    summary: str = ""
    evidence: List[str] = Field(default_factory=list)


class TheoryOfMindEntry(BaseModel):
    entity_name: str
    inferred_perspective: str
    evidence: List[str] = Field(default_factory=list)


class TheoryOfMindSystem(BaseModel):
    entries: List[TheoryOfMindEntry] = Field(default_factory=list)


class InferredPOMBatch(BaseModel):
    """The LLM call's own output shape -- one call, one schema, exactly
    the six systems that genuinely require interpretation. See
    src/pom/engine.py::run_inferred_pom."""

    identity: IdentitySystem = Field(default_factory=IdentitySystem)
    motivation: MotivationSystem = Field(default_factory=MotivationSystem)
    learning_style: LearningStyleSystem = Field(default_factory=LearningStyleSystem)
    stress: StressSystem = Field(default_factory=StressSystem)
    narrative: NarrativeSystem = Field(default_factory=NarrativeSystem)
    theory_of_mind: TheoryOfMindSystem = Field(default_factory=TheoryOfMindSystem)


class PersonalOperatingModel(BaseModel):
    """The full, eight-system POM -- mechanical systems computed in
    Python, the other six from one LLM call (InferredPOMBatch), combined
    here into one object. See src/pom/engine.py::compute_personal_operating_model.

    `computed_at` (added 2026-07-19, backlog #271, see engine/decisions.md
    "Learning/POM: surface computed_at staleness signal"): defaults to
    "" -- src/pom/engine.py never sets this itself (same as every other
    field here, it has no notion of when it's being persisted); the real
    timestamp is stored in the `personal_operating_model` table's own
    `computed_at` column (already written by
    src/api/db.py::replace_personal_operating_model on every offline
    computation) and attached back onto this model by
    src/api/db.py::get_personal_operating_model after parsing the stored
    JSON blob, so the frontend can show when this was last computed
    rather than presenting it as always-current. Defaulted rather than
    required so no existing construction site (tests, engine code) needs
    to change, same precedent as Judgment v3's four new fields."""

    belief: BeliefSystem = Field(default_factory=BeliefSystem)
    relationship: RelationshipSystem = Field(default_factory=RelationshipSystem)
    identity: IdentitySystem = Field(default_factory=IdentitySystem)
    motivation: MotivationSystem = Field(default_factory=MotivationSystem)
    learning_style: LearningStyleSystem = Field(default_factory=LearningStyleSystem)
    stress: StressSystem = Field(default_factory=StressSystem)
    narrative: NarrativeSystem = Field(default_factory=NarrativeSystem)
    theory_of_mind: TheoryOfMindSystem = Field(default_factory=TheoryOfMindSystem)
    computed_at: str = ""
