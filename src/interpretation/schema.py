"""
Interpretation schema for Confidant's Understanding Layer.

v0.9: implements engine/specs/interpretation-spec-v0.9.md, frozen before
this file was written (schema-first process -- see decisions.md 2026-07-02
"v0.9 Interpretation Specification frozen"). Do not add fields here
without updating that spec first.

GOVERNING LAWS (stated in full in the spec doc):
1. Sparse by default -- an empty field is correct, not a gap.
2. Evidence before inference -- never blur observed/asserted/implied/inferred.
3. Typed over prompted -- structural fixes over more prompt wording, once
   a prompt-only fix has already been tried and failed to hold.
4. Every field must justify its existence -- no downstream consumer, no field.
5. Interpret, don't advise -- this layer never generates a response.

Epistemic hierarchy (Phase 3 -- Discern):
    Evidence
      -> Observed Facts    (user explicitly stated -- meta-level: what was said)
      -> Claims             (propositional content the user asserts as true)
      -> Goals               (what the user is trying to achieve)
      -> Decision Options   (choices the user is explicitly weighing -- not beliefs)
    Reasoning
      -> Assumptions        (unstated beliefs the user is implicitly relying on)
      -> Inferences          (model's read, always with confidence)
    Missing Information
      -> Unknowns            (gaps in the situation as stated, not brainstormed next steps)
    Metacognition
      -> Biases                (deliberately rare)
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Literal
import re


def _normalize_unit_interval(v):
    """
    Small models default to a 0-10 confidence/intensity scale out of habit
    despite instructions and a 0.0-1.0 schema constraint. Ollama's
    schema-constrained grammar (format=model_json_schema()) enforces type
    and structure, but NOT numeric ge/le bounds -- so a bare "6" sails
    through the grammar and only fails at Pydantic validation. Rather than
    reject the whole turn over what's clearly a scale mistake, rescale it
    here. Values already in [0, 1] pass through unchanged.
    """
    if isinstance(v, (int, float)) and v > 1:
        return v / 10
    return v


_POSSESSIVE_PREFIX = re.compile(
    r"^(your|my|his|her|their|our|the)\s+", flags=re.IGNORECASE
)


def _strip_possessive(entity: str) -> str:
    """
    "your boss" -> "boss", "The company" -> "company". The entity is the
    role/person, not the grammatical form the user happened to use to
    refer to them.
    """
    return _POSSESSIVE_PREFIX.sub("", entity.strip())


# First/second-person pronouns are never a valid entity on their own --
# "you" showing up in entities is a category error (the user isn't a
# stakeholder in their own conversation).
_PRONOUN_ENTITIES = {"you", "i", "me", "user", "myself", "yourself"}

# A speculative reading that reaches for an UNSTATED cause or motive
# ("might be hesitant due to lack of resources") is inherently thin
# evidence, no matter how fluent it sounds. Confidence calibration
# guidance in the prompt has been repeatedly ignored across several
# rounds (see engine/decisions.md 2026-07-02 "v0.7"), so this is now
# enforced structurally as a backstop, not just requested.
_HEDGE_WORDS = re.compile(
    r"\b(might|may|could|possibly|possible|perhaps|maybe|likely|probably)\b",
    flags=re.IGNORECASE,
)
_HEDGED_CONFIDENCE_CAP = 0.4


class EmotionalSignal(BaseModel):
    """
    v0.9: added `source`. NOTE: a `subject` field (who is experiencing the
    emotion) was proposed during spec design and explicitly REMOVED after
    failing its own "what breaks if this disappears" test -- nothing
    consumes it, no multi-agent reasoning exists yet. Scope is the user's
    own emotions only. Reintroduce `subject` only when that changes.
    """
    emotion: str
    intensity: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    source: Literal["explicit", "inferred"]

    @field_validator("intensity", "confidence", mode="before")
    @classmethod
    def _rescale(cls, v):
        return _normalize_unit_interval(v)


class Bias(BaseModel):
    bias: str            # e.g. "sunk cost", "identity protection", "recency"
    evidence: str         # the specific phrasing that suggests it
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("confidence", mode="before")
    @classmethod
    def _rescale(cls, v):
        return _normalize_unit_interval(v)


class Inference(BaseModel):
    """
    An inference is never certain by definition -- it's the model's read
    on what the evidence means, not the evidence itself. Every one
    carries a confidence so Judgment can decide how much weight to give
    it, rather than Interpretation silently deciding that on Judgment's
    behalf. An inference must never be a suggested action or behavior
    change -- that's Planner's job, not Interpretation's (see prompt.py).
    """
    reading: str
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("confidence", mode="before")
    @classmethod
    def _rescale(cls, v):
        return _normalize_unit_interval(v)

    @model_validator(mode="after")
    def _cap_hedged_confidence(self):
        if _HEDGE_WORDS.search(self.reading) and self.confidence > _HEDGED_CONFIDENCE_CAP:
            self.confidence = _HEDGED_CONFIDENCE_CAP
        return self


# v0.9: stakes -> impact_domains. Free string had an 80% (4/5) corruption
# rate in real testing -- the model used it as an escape hatch for
# therapist-voice prose, once a full 10-point advice list. Closed enum
# makes that structurally impossible rather than just discouraged.
ImpactDomain = Literal[
    "personal", "professional", "financial", "health", "legal", "safety", "other"
]


# v1.1 (see engine/decisions.md and engine/specs/interpretation-spec-v1.1.md):
# closes the "Goal/Decision lifecycle" and "Entity attribute enrichment"
# gaps confirmed by the 2026-07-05 WorldState state-evolution suite and
# left explicitly declined at the time ("the State Builder must not
# compensate for a missing semantic signal with a heuristic" --
# engine/decisions.md). These fields are the real upstream signal that
# principle called for.
#
# Resolves interpretation-v1.1-proposal.md's two open questions: Option A
# (Interpretation stays stateless; targets are best-effort
# paraphrases/quotes, matched downstream by src/state/builder.py's
# existing word-overlap mechanism) over Option B (giving Interpretation
# read access to WorldState) -- Option A is adoptable without a pipeline
# restructure. goal_updates/decision_events are ADDITIVE alongside
# `goals`/`decision_options`, not a replacement -- a freshly-stated goal
# with no existing match is just new, same as today.
#
# `GoalUpdateStatus` deliberately DUPLICATES world_state.GoalStatus rather
# than importing it -- same reasoning as builder.py's duplicated
# _word_overlap: Interpretation and WorldState are separate frozen
# layers, and this avoids a cross-package dependency for one Literal that
# may reasonably diverge later.
GoalUpdateStatus = Literal["active", "paused", "completed", "abandoned"]
DecisionEventType = Literal["proposed", "chosen", "rejected", "deferred"]


class GoalUpdate(BaseModel):
    """
    Signals a lifecycle transition on an EXISTING goal -- never a new
    goal (a freshly-stated goal with no prior match belongs in `goals`
    instead). `goal` is a best-effort paraphrase/quote of the goal this
    refers to; matched against WorldState.goals downstream by content
    similarity, not by a stable ID (WorldState has none yet -- see
    world_state.py module docstring, deferred to v1.1 provenance work).
    """

    goal: str
    status: GoalUpdateStatus


class DecisionEvent(BaseModel):
    """
    Signals something that happened to an EXISTING decision option
    (chosen/rejected/deferred) -- never a new option (that's
    `decision_options`' job, kept strictly extractive). `option` is a
    best-effort paraphrase/quote, matched downstream the same way as
    GoalUpdate.goal.
    """

    option: str
    event: DecisionEventType


class EntityAttributeUpdate(BaseModel):
    """
    A structured attribute learned about an entity already named in
    `entities` (or named here for the first time in the same turn).
    Additive alongside the flat `entities: List[str]`, which stays for
    plain mentions with no new attribute information.
    """

    entity: str
    attribute: str
    value: str


class Interpretation(BaseModel):
    # --- Phase 1: Prepare the Thinker ---
    urgency: Literal["low", "medium", "high"]   # v0.9: real Literal, was unenforced str
    impact_domains: List[ImpactDomain]          # v0.9: renamed from `stakes`, multi-label
    emotional_signals: List[EmotionalSignal]

    # --- Phase 2: Discover the Real Question ---
    surface_complaint: str           # concise restatement -- see prompt.py, not a word-count rule
    core_question: str               # Confidant's current best read of the real question
    core_question_confidence: float = Field(ge=0.0, le=1.0)

    # --- Phase 3: Build Discernment (epistemic tiers, see module docstring) ---
    observed_facts: List[str]        # meta-level: what was explicitly said/observed
    claims: List[str]                # propositional content the user asserts as true
    goals: List[str]                 # what the user is trying to achieve
    decision_options: List[str]      # choices the user is explicitly weighing -- not beliefs

    # v1.2 (see engine/decisions.md and interpretation-spec-v0.9.md's
    # REOPENED `assumptions` entry): mandatory reasoning field, added after
    # a prompt-only fix for `assumptions` under-population (A04, "Hidden
    # assumptions") failed to hold on re-test against the real pipeline.
    # Forces the model to explicitly state whether the user's own framing
    # embeds an unstated belief before finalizing `assumptions`, rather
    # than letting that check be silently skipped -- "typed over prompted"
    # (governing law 3) applied to a generative gap, not a validation gap.
    assumption_check: str
    assumptions: List[str]           # unstated beliefs implied but not directly said
    inferences: List[Inference]      # model's reads, each with confidence
    unknowns: List[str]              # gaps in the situation as stated -- not brainstormed next steps
    biases: List[Bias]               # deliberately rare -- see prompt.py calibration guidance

    entities: List[str]              # people/orgs/stakeholders mentioned (never the user themself)
    clarity_score: float = Field(ge=0.0, le=1.0)
    requires_clarification: bool

    # --- v1.1: lifecycle/enrichment signals, see comment above Interpretation ---
    goal_updates: List[GoalUpdate] = Field(default_factory=list)
    decision_events: List[DecisionEvent] = Field(default_factory=list)
    entity_attribute_updates: List[EntityAttributeUpdate] = Field(default_factory=list)

    @field_validator("core_question_confidence", "clarity_score", mode="before")
    @classmethod
    def _rescale(cls, v):
        return _normalize_unit_interval(v)

    @model_validator(mode="after")
    def _clean_up_cross_field_issues(self):
        # Identical evidence text across multiple biases is a structural
        # tell that the model composed one summary sentence and reused it,
        # rather than pointing at distinct phrases for each bias -- see
        # engine/decisions.md 2026-07-02 "bias evidence fabrication". Keep
        # only the first bias per unique evidence string.
        seen_evidence = set()
        deduped_biases = []
        for b in self.biases:
            key = b.evidence.strip().lower()
            if key not in seen_evidence:
                seen_evidence.add(key)
                deduped_biases.append(b)
        self.biases = deduped_biases

        self.entities = [
            _strip_possessive(e) for e in self.entities
            if e.strip().lower() not in _PRONOUN_ENTITIES
        ]

        return self
