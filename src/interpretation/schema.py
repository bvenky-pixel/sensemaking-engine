"""
Interpretation schema for Confidant's Understanding Layer.

Field names deliberately mirror the vocabulary of "The Confidant Thinking
Method" (see engine/architecture.md and the product constitution) rather
than generic NLP terms. Each field should trace back to a specific line in
the constitution -- if it doesn't, it doesn't belong here. See
engine/decisions.md for the record of that mapping.

Phase 3 fields follow an epistemic hierarchy (see engine/decisions.md,
2026-07-02 "epistemic tiers", "intent tier", "decision options tier"): a
user statement, a user's motivation, a decision under consideration, and
a model inference are never the same kind of thing, and this schema
refuses to flatten them into one representation.

    Evidence
      -> Observed Facts    (user explicitly stated -- meta-level: what was said)
      -> Claims             (propositional content the user asserts as true)
      -> Goals               (what the user is trying to achieve)
      -> Decision Options   (choices the user is explicitly weighing -- not beliefs)
    Reasoning
      -> Assumptions        (unstated beliefs the user is implicitly relying on)
      -> Inferences          (model's read, always with confidence)
    Missing Information
      -> Unknowns            (open questions preventing understanding)
    Metacognition
      -> Biases                (deliberately rare -- see calibration guidance below)

GOVERNING LAW (v0.7): The Interpretation Layer is sparse by default. A
good Interpretation object is not the one with the most information --
it's the one with the least unjustified information. Every tier starts
empty; it gets populated only when the evidence earns it. See
engine/decisions.md, "sparse by default", for the full rationale.
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List
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
# NOTE (v0.8): the 5-run calibration test found "possibly" (adverb) does
# not match "it's possible that..." (adjective) -- this was the single
# biggest source of remaining 0.8-confidence speculative inferences.
# Added "possible" as its own token.
_HEDGE_WORDS = re.compile(
    r"\b(might|may|could|possibly|possible|perhaps|maybe|likely|probably)\b",
    flags=re.IGNORECASE,
)
_HEDGED_CONFIDENCE_CAP = 0.4


class EmotionalSignal(BaseModel):
    emotion: str
    intensity: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)

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
        # Structural backstop: if the reading itself uses hedge language
        # ("might", "may", "could"...), that's the model's own admission
        # of uncertainty -- confidence should already be low. Prompt-only
        # calibration guidance has not reliably held (see
        # engine/decisions.md 2026-07-02 "v0.7"), so cap it here too.
        if _HEDGE_WORDS.search(self.reading) and self.confidence > _HEDGED_CONFIDENCE_CAP:
            self.confidence = _HEDGED_CONFIDENCE_CAP
        return self


class Interpretation(BaseModel):
    # --- Phase 1: Prepare the Thinker ---
    urgency: str                     # "low" | "medium" | "high"
    stakes: str                      # what's actually at risk if this goes wrong
    emotional_signals: List[EmotionalSignal]

    # --- Phase 2: Discover the Real Question ---
    surface_complaint: str           # what the user said the problem is
    core_question: str               # Confidant's current best read of the real question
    core_question_confidence: float = Field(ge=0.0, le=1.0)

    # --- Phase 3: Build Discernment (epistemic tiers, see module docstring) ---
    observed_facts: List[str]        # meta-level: what was explicitly said/observed
    claims: List[str]                # propositional content the user asserts as true
    goals: List[str]                 # what the user is trying to achieve
    decision_options: List[str]      # choices the user is explicitly weighing -- not beliefs
    assumptions: List[str]           # unstated beliefs implied but not directly said
    inferences: List[Inference]      # model's reads, each with confidence
    unknowns: List[str]              # specific open questions, not broad/existential ones
    biases: List[Bias]               # deliberately rare -- see prompt.py calibration guidance

    entities: List[str]              # people/orgs/stakeholders mentioned (never the user themself)
    clarity_score: float = Field(ge=0.0, le=1.0)
    requires_clarification: bool

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
        # only the first (highest-confidence-ordered, since we don't
        # reorder) bias per unique evidence string.
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
