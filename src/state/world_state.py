"""
WorldState v1 -- the persistent, incrementally-updated model of what
Confidant knows about the user's world, replacing ConversationState.

Implements the "Core Structure" of engine/specs/WorldState_Specification_v1.md
(uploaded 2026-07-05) only. Per explicit scope decision: this is "WorldState
v1, not WorldState Ultimate" -- proving the new data model and merge
semantics, not the full spec in one pass. Deferred to later iterations
(see engine/decisions.md for the full v1/v1.1/v1.2/v1.3 breakdown):
- v1.1: provenance (source/first_seen/last_updated/supporting_evidence),
  turn numbering, stable object IDs
- v1.2: conversation_summary, emotional_history (trend computation)
- v1.3: project graph, cross-links between entities and goals

Design principles carried over from the spec (do not violate when
extending this file):
1. WorldState represents knowledge, not language.
2. WorldState only grows more accurate -- refine, don't replace.
3. Nothing is silently deleted -- mark superseded/resolved/retracted,
   never remove.
4. WorldState minimizes reasoning -- it maintains a model; Judgment draws
   conclusions.
5. Every field has explicit merge semantics (see src/state/builder.py).

KNOWN LIMITATION, same as the old ConversationState: lifecycle only ever
advances in the "Resolved"/"Completed" direction based on signals that
exist today (unknowns resolved by a matching new fact/claim). Goal and
Decision status has no advancement signal yet -- Interpretation doesn't
tell us "user completed this goal" or "user resolved this decision" --
so those stay at their initial status until a future Interpretation field
provides that signal. Not invented here.
"""

from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, Field

FactStatus = Literal["active", "superseded", "retracted"]
ClaimStatus = Literal["active", "superseded", "retracted"]
GoalStatus = Literal["active", "paused", "completed", "abandoned"]
DecisionStatus = Literal["open", "resolved", "expired"]


class Fact(BaseModel):
    content: str
    status: FactStatus = "active"


class Claim(BaseModel):
    content: str
    status: ClaimStatus = "active"


class Goal(BaseModel):
    content: str
    status: GoalStatus = "active"


class Decision(BaseModel):
    """One option the user is explicitly weighing (see
    src/interpretation/schema.py Interpretation.decision_options). Kept
    one-Decision-per-option rather than clustering options under a named
    decision, since Interpretation doesn't title or group them -- matches
    this codebase's established rule of never inventing structure the
    evidence doesn't support."""

    content: str
    status: DecisionStatus = "open"


class Unknown(BaseModel):
    content: str


class Entity(BaseModel):
    name: str
    type: str = "unknown"  # Interpretation doesn't classify entity type yet
    attributes: List[str] = Field(default_factory=list)
    relationships: List[str] = Field(default_factory=list)


class WorldState(BaseModel):
    # Phase 2 (Discover) tracking -- not in the spec's Core Structure
    # table, but carried forward from the old ConversationState: the spec
    # is silent on where "what's the real question" lives, and dropping
    # it would regress behavior Judgment and the inspector both already
    # depend on. Same "never regress on lower confidence" merge rule as
    # before -- see src/state/builder.py.
    surface_complaint: str = ""
    core_question: str = ""
    core_question_confidence: float = 0.0

    # Core Structure
    facts: List[Fact] = Field(default_factory=list)
    claims: List[Claim] = Field(default_factory=list)
    goals: List[Goal] = Field(default_factory=list)
    decisions: List[Decision] = Field(default_factory=list)
    unknowns: List[Unknown] = Field(default_factory=list)
    entities: List[Entity] = Field(default_factory=list)

    # Reasoning/metacognition tier -- the spec's Core Structure doesn't
    # name these explicitly, but src/judgment/engine.py's phase-transition
    # logic depends on assumption/bias counts (Phase 3 Discern success
    # criterion), and the old ConversationState carried them. Kept as
    # plain accumulated strings, not typed objects with their own
    # lifecycle -- the spec doesn't define merge/status rules for this
    # tier. Revisit if/when the spec is extended to cover them.
    assumptions: List[str] = Field(default_factory=list)
    inferences: List[str] = Field(default_factory=list)
    biases: List[str] = Field(default_factory=list)

    clarity_level: float = 0.0

    # Where the conversation is in the Confidant Method.
    phase: str = "prepare"
