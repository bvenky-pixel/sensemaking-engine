"""
WorldState v1 -- the persistent, incrementally-updated model of what
Confidant knows about the user's world, replacing ConversationState.

Implements the "Core Structure" of engine/specs/WorldState_Specification_v1.md
(uploaded 2026-07-05) only. Per explicit scope decision: this is "WorldState
v1, not WorldState Ultimate" -- proving the new data model and merge
semantics, not the full spec in one pass. Deferred to later iterations
(see engine/decisions.md for the full v1/v1.1/v1.2/v1.3 breakdown):
- v1.1: provenance (source/first_seen/last_updated) and turn numbering --
  IMPLEMENTED 2026-07-10 (see engine/decisions.md "WorldState provenance
  -- trajectory prerequisite"; Provenance class + WorldState.turn_count
  below). `supporting_evidence` and stable object IDs remain deferred --
  no motivating use case yet for the former, and nothing in this round
  depends on the latter (matching still goes by content/word-overlap).
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

KNOWN LIMITATION, updated 2026-07-09 (see engine/decisions.md and
engine/specs/interpretation-spec-v1.1.md): Goal and Decision status
advancement now HAS a signal -- Interpretation's `goal_updates` and
`decision_events` fields (v1.1) -- consumed by
src/state/builder.py's `_apply_goal_updates`/`_apply_decision_events`.
This closes the gap described below for the cases those fields cover
(explicit lifecycle statements); it does not add any inference the
Interpretation layer doesn't itself provide -- an unmatched update is
dropped, never guessed at downstream. Original note, preserved for
history: lifecycle previously only ever advanced in the "Resolved"/
"Completed" direction based on unknowns resolved by a matching new
fact/claim; Goal and Decision status had no advancement signal at all
before this round.

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

import uuid
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

# Imports specifically from the schema submodule, not the understanding
# package root -- see src/understanding/__init__.py's own comment on why
# (avoids a circular import through src/understanding/engine.py, which
# needs WorldState itself).
from src.understanding.schema import UnderstandingState

FactStatus = Literal["active", "superseded", "retracted"]
ClaimStatus = Literal["active", "superseded", "retracted"]
GoalStatus = Literal["active", "paused", "completed", "abandoned"]
DecisionStatus = Literal["open", "resolved", "deferred", "expired"]
UnknownStatus = Literal["open", "resolved"]
EntityStatus = Literal["active", "retracted"]


class Provenance(BaseModel):
    """
    v1.1 (added 2026-07-10, see engine/decisions.md "WorldState provenance
    -- trajectory prerequisite"): when a knowledge item was first created
    and when its status last actually changed, both as turn numbers (see
    WorldState.turn_count). `source` names which layer created the item --
    "interpretation" for everything update_state creates, or "judgment"
    for a new Fact/Claim created by a "superseded" knowledge correction
    (added 2026-07-12, see engine/decisions.md "Fact/Claim correction and
    near-duplicate consolidation" -- src/state/builder.py::apply_knowledge_corrections
    is the one other place besides Interpretation that ever creates a new
    KnowledgeItem).

    Deliberately excludes `supporting_evidence` (a list of every turn that
    touched the item) from the original WorldState-spec-v1.md worked
    example -- that would require bookkeeping on every reaffirmation, not
    just creation/status-change, a bigger behavior change with no current
    motivating use case. Add it later if trajectory work actually needs it.
    """

    source: str
    first_seen: int
    last_updated: int


class KnowledgeItem(BaseModel):
    """
    Common shape shared by every durable knowledge object (Fact, Claim,
    Goal, Decision, Unknown, Entity, Assumption, Inference), so a future
    WorkingMemory/Knowledge split (see module TODO above) has a single,
    consistent base to work from rather than six-plus ad hoc shapes.

    `status` is required on every subtype (each narrows the Literal and
    default to its own lifecycle). `provenance` is populated by
    src/state/builder.py at creation and at every status transition (see
    Provenance above).

    `id` (added 2026-07-12, see engine/decisions.md "Understanding layer
    -- Journey-scoped identity"): stable across turns for as long as the
    item itself persists -- previously there was NO stable identity on
    these objects at all (matching went entirely by content/word-overlap
    heuristics in src/state/builder.py, explicitly named as a deferred
    gap in three separate places in this codebase). `default_factory`
    keeps every pre-existing session's `model_validate_json` safe (no
    ValidationError on a JSON blob with no "id" key), but means an
    already-persisted item gets a DIFFERENT id on every deserialization
    until it's next written back -- see scripts/backfill_knowledge_item_ids.py,
    a required one-time migration for already-deployed sessions, not an
    optional cleanup. Deliberately does NOT replace or change
    src/state/builder.py's existing exact-match/word-overlap matching --
    Interpretation stays stateless (never reads WorldState, see
    src/interpretation/schema.py's GoalUpdate docstring), so its
    GoalUpdate/DecisionEvent output will always be paraphrase text, never
    a literal id reference. `id` is purely additive metadata for
    downstream consumers (src/understanding/) to cite, not a matching
    mechanism.

    `confidence` (populated 2026-07-12, previously a dead placeholder --
    nothing ever assigned it): a deterministic persistence TIER derived
    from which KnowledgeItem subtype an item is, not a new per-item LLM
    output -- see src/state/builder.py's FACT_TIER_CONFIDENCE and
    siblings. The one exception is Inference, which gets a REAL per-item
    value from Interpretation's own Inference.confidence (already a
    calibrated LLM output, already gated by builder.py's
    INFERENCE_CONFIDENCE_FLOOR) rather than a flat constant.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: str
    confidence: Optional[float] = None
    provenance: Optional[Provenance] = None


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


class EntityAttribute(BaseModel):
    """
    A single known attribute of an Entity (e.g. attribute="role",
    value="Head of Product"). v1.1 (see engine/decisions.md and
    engine/specs/interpretation-spec-v1.1.md): Entity.attributes was a
    flat List[str] with no data source; Interpretation's
    entity_attribute_updates now supplies real (attribute, value) pairs,
    so the field is restructured to actually hold them rather than stay
    permanently empty.
    """

    attribute: str
    value: str


class Entity(KnowledgeItem):
    name: str
    type: str = "unknown"  # Interpretation doesn't classify entity type yet
    status: EntityStatus = "active"
    attributes: List[EntityAttribute] = Field(default_factory=list)
    relationships: List[str] = Field(default_factory=list)


AssumptionStatus = Literal["active", "retracted"]
InferenceStatus = Literal["active", "retracted"]


class Assumption(KnowledgeItem):
    """
    Added 2026-07-12 (see engine/decisions.md "Understanding layer --
    Journey-scoped identity") -- an id-bearing, groundable counterpart to
    the existing flat WorldState.assumptions: List[str]. Deliberately
    ADDITIVE, not a replacement: the flat list stays exactly as it is
    today (same population logic, same consumer -- src/judgment/engine.py's
    phase-transition logic reads len(state.assumptions)), because an
    in-place type change on that existing field would break
    model_validate_json on every pre-existing session (old JSON has plain
    strings where a structured object would now be expected -- a type
    mismatch has no safe default the way an additive field does). This
    type exists purely so src/understanding/ has something with a stable
    id to cite; nothing here changes what Judgment/Planner/Response see.
    confidence is populated with the flat ASSUMPTION_TIER_CONFIDENCE
    constant (src/state/builder.py) -- Interpretation's assumptions field
    is plain List[str], no per-item signal exists to use instead.
    """

    content: str
    status: AssumptionStatus = "active"


class Inference(KnowledgeItem):
    """
    Added 2026-07-12, same reasoning and same additive relationship to
    WorldState.inferences: List[str] as Assumption above. Unlike
    Assumption, confidence here is REAL per-item data, not a flat
    constant -- src/interpretation/schema.py's own Inference.confidence
    is already a calibrated LLM output (already gated by
    src/state/builder.py's INFERENCE_CONFIDENCE_FLOOR), populated
    directly from it. `content` is the cleaned reading only (no embedded
    "(confidence=X)" suffix, since confidence is now a structured field)
    -- NOT required to be byte-identical to the corresponding flat-list
    string, which keeps its own suffix as before.
    """

    content: str
    status: InferenceStatus = "active"


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

    # Added 2026-07-12 (see Assumption/Inference above and
    # engine/decisions.md "Understanding layer -- Journey-scoped
    # identity"): id-bearing, groundable counterparts to the flat
    # assumptions/inferences string lists above, which stay untouched.
    # Deliberately excluded from Judgment/Planner/Response's prompts
    # (see the `exclude=` set at each of their model_dump_json call
    # sites) -- these exist for src/understanding/ to consume, not as a
    # new signal for the existing pipeline stages.
    assumption_items: List[Assumption] = Field(default_factory=list)
    inference_items: List[Inference] = Field(default_factory=list)

    # v1.1 (added 2026-07-10, see engine/decisions.md "WorldState
    # provenance -- trajectory prerequisite"): incremented exactly once
    # per turn, solely by src/state/builder.py::update_state -- the single
    # per-turn WorldState mutation entrypoint. 0 for a brand-new session
    # with no turns yet. Nothing else (Orchestrator, the API layer) needs
    # to know about or manage this counter.
    turn_count: int = 0

    # Added 2026-07-12 (see engine/decisions.md "Understanding layer --
    # Journey-scoped identity"): the stable, human-readable layer
    # rendered from this WorldState -- see src/understanding/. An empty
    # default is correct (not harmful the way a fresh random `id` above
    # would be) for a pre-existing session that hasn't had Tier 1
    # computed yet; it populates on that session's very next turn, no
    # backfill needed. Deliberately excluded from Judgment/Planner/
    # Response's prompts, same reasoning as assumption_items/inference_items
    # above -- this is a rendering of already-decided content, not a new
    # input for those stages to reason over.
    understanding: UnderstandingState = Field(default_factory=UnderstandingState)


# Added 2026-07-12 (see engine/decisions.md "Understanding layer --
# Journey-scoped identity"): src/judgment/engine.py, src/planner/engine.py,
# and src/response/engine.py all dump the FULL WorldState verbatim into
# their prompts (`state.model_dump_json(indent=2)`, no field filtering).
# Left unexcluded, `understanding`/`assumption_items`/`inference_items`
# would silently start flowing into all three already-calibrated prompts
# the moment they exist -- pure token waste at minimum, and a real
# behavior-regression risk at worst (a model citing/quoting
# `understanding` text back, or treating assumption_items/inference_items
# as a distinct new signal alongside the existing flat assumptions/
# inferences lists they duplicate). Defined once here, imported by all
# three engines' `model_dump_json(..., exclude=PROMPT_EXCLUDED_FIELDS)`
# call, rather than three independently-maintained copies of the same set.
PROMPT_EXCLUDED_FIELDS = {"understanding", "assumption_items", "inference_items"}
