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

TODO / DESIGN NOTE (2026-07-05, not implemented -- see engine/decisions.md):
WorldState currently conflates two different kinds of state under one
container:
- Durable Knowledge: Facts, Claims, Goals, Decisions, Unknowns, Entities
  -- things actually true (or believed/weighed) about the user's world,
  meant to persist and accumulate across the whole relationship.
- Working Memory: surface_complaint/core_question/core_question_confidence,
  assumptions/inferences/biases, clarity_level, phase -- reasoning
  scaffolding Judgment needs turn-to-turn to track where the CONVERSATION
  currently stands, not facts about the user's world.
`phase` and the core_question tracking are clearly the latter; assumptions/
inferences/biases are murkier (an assumption surfaced today could turn out
to be durable knowledge about the user, not just conversational
scratchpad) and deliberately NOT force-classified here -- per the "let it
evolve based on what Judgment actually needs" principle, splitting these
into a separate WorkingMemory container is deferred until Judgment's
actual usage patterns make the right split obvious, rather than guessed
at now.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

FactStatus = Literal["active", "superseded", "retracted"]
ClaimStatus = Literal["active", "superseded", "retracted"]
GoalStatus = Literal["active", "paused", "completed", "abandoned"]
DecisionStatus = Literal["open", "resolved", "expired"]
UnknownStatus = Literal["open", "resolved"]
EntityStatus = Literal["active", "retracted"]


class KnowledgeItem(BaseModel):
    """
    Common shape shared by every durable knowledge object (Fact, Claim,
    Goal, Decision, Unknown, Entity), so a future WorkingMemory/Knowledge
    split (see module TODO above) has a single, consistent base to work
    from rather than six ad hoc shapes.

    `status` is required on every subtype (each narrows the Literal and
    default to its own lifecycle). `confidence` and `provenance` are
    placeholders for v1.1 -- see engine/decisions.md -- nothing populates
    them yet, so they stay None rather than a fabricated default.
    """

    status: str
    confidence: Optional[float] = None
    provenance: Optional[dict] = None  # placeholder shape; real Provenance model lands in v1.1


class Fact(KnowledgeItem):
    content: str
    status: FactStatus = "active"


class Claim(KnowledgeItem):
    content: str
    status: ClaimStatus = "active"


class Goal(KnowledgeItem):
    content: str
    status: GoalStatus = "active"


class Decision(KnowledgeItem):
    """One option the user is explicitly weighing (see
    src/interpretation/schema.py Interpretation.decision_options). Kept
    one-Decision-per-option rather than clustering options under a named
    decision, since Interpretation doesn't title or group them -- matches
    this codebase's established rule of never inventing structure the
    evidence doesn't support."""

    content: str
    status: DecisionStatus = "open"


class Unknown(KnowledgeItem):
    """
    status defaults to "open" and the field exists for shape consistency,
    but nothing currently transitions an Unknown to "resolved" in place --
    src/state/builder.py still removes a resolved Unknown and promotes its
    content into Facts, same as before this field existed. Per Design
    Principle 3 ("nothing is silently deleted"), marking resolved and
    retaining would be more consistent with Facts/Claims -- deferred
    rather than changed here, since that's a behavior change beyond what
    was asked (standardizing shape, not merge behavior).
    """

    content: str
    status: UnknownStatus = "open"


class Entity(KnowledgeItem):
    name: str
    type: str = "unknown"  # Interpretation doesn't classify entity type yet
    status: EntityStatus = "active"
    attributes: List[str] = Field(default_factory=list)
    relationships: List[str] = Field(default_factory=list)


class WorldState(BaseModel):
    # --- Working Memory (see module TODO) ---
    # Phase 2 (Discover) tracking -- not in the spec's Core Structure
    # table, but carried forward from the old ConversationState: the spec
    # is silent on where "what's the real question" lives, and dropping
    # it would regress behavior Judgment and the inspector both already
    # depend on. Same "never regress on lower confidence" merge rule as
    # before -- see src/state/builder.py.
    surface_complaint: str = ""
    core_question: str = ""
    core_question_confidence: float = 0.0

    # Reasoning/metacognition tier -- the spec's Core Structure doesn't
    # name these explicitly, but src/judgment/engine.py's phase-transition
    # logic depends on assumption/bias counts (Phase 3 Discern success
    # criterion), and the old ConversationState carried them. Kept as
    # plain accumulated strings, not KnowledgeItem subtypes -- the spec
    # doesn't define merge/status rules for this tier, and it's one of the
    # candidates for the future WorkingMemory split noted above.
    assumptions: List[str] = Field(default_factory=list)
    inferences: List[str] = Field(default_factory=list)
    biases: List[str] = Field(default_factory=list)

    clarity_level: float = 0.0

    # Where the conversation is in the Confidant Method.
    phase: str = "prepare"

    # --- Durable Knowledge (Core Structure) ---
    facts: List[Fact] = Field(default_factory=list)
    claims: List[Claim] = Field(default_factory=list)
    goals: List[Goal] = Field(default_factory=list)
    decisions: List[Decision] = Field(default_factory=list)
    unknowns: List[Unknown] = Field(default_factory=list)
    entities: List[Entity] = Field(default_factory=list)
