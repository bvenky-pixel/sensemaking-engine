"""
Interpretation schema for Confidant's Understanding Layer.

Field names deliberately mirror the vocabulary of "The Confidant Thinking
Method" (see engine/architecture.md and the product constitution) rather
than generic NLP terms. Each field should trace back to a specific line in
the constitution -- if it doesn't, it doesn't belong here. See
engine/decisions.md for the record of that mapping.
"""

from pydantic import BaseModel, Field
from typing import List


class EmotionalSignal(BaseModel):
    emotion: str
    intensity: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)


class Assumption(BaseModel):
    assumption: str
    # Phase 3 tell: is the user treating this as a known fact when it isn't?
    # ("That's actually an interpretation, not a fact.")
    stated_as_fact: bool


class Bias(BaseModel):
    bias: str            # e.g. "sunk cost", "identity protection", "recency"
    evidence: str         # the specific phrasing that suggests it
    confidence: float = Field(ge=0.0, le=1.0)


class Interpretation(BaseModel):
    # --- Phase 1: Prepare the Thinker ---
    # Understand mental state, urgency, and the gravity of the decision
    # before attempting to solve anything.
    urgency: str                     # "low" | "medium" | "high"
    stakes: str                      # what's actually at risk if this goes wrong
    emotional_signals: List[EmotionalSignal]

    # --- Phase 2: Discover the Real Question ---
    # People rarely arrive with the real problem -- move from symptom to
    # the question beneath the question.
    surface_complaint: str           # what the user said the problem is
    core_question: str               # Confidant's current best read of the real question
    core_question_confidence: float = Field(ge=0.0, le=1.0)

    # --- Phase 3: Build Discernment ---
    # Separate facts from interpretations, surface assumptions and biases,
    # distinguish known / believed / unknown.
    facts: List[str]                 # stated as true, verifiable
    assumptions: List[Assumption]
    interpretations: List[str]       # reads on what the facts mean
    unknowns: List[str]              # open questions still unresolved
    biases: List[Bias]

    entities: List[str]              # people/orgs/stakeholders mentioned
    clarity_score: float = Field(ge=0.0, le=1.0)
    requires_clarification: bool
