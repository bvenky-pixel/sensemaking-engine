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
  below). Stable object IDs -- IMPLEMENTED 2026-07-12 (backlog #81/#82,
  see `KnowledgeItem.id` below). `supporting_evidence` on `Provenance`
  itself (a turn-log of every reaffirmation, not just first_seen/
  last_updated) remains deferred -- still no motivating use case;
  see Provenance's own docstring. Judgment's SEPARATE `supporting_evidence`
  field has since migrated from prose quotes to real `KnowledgeItem.id`
  references (2026-07-19, backlog #242, see engine/decisions.md
  "Judgment: supporting_evidence migrated to KnowledgeItem id
  references") -- that migration lives in src/judgment/, not here.
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

DESIGN NOTE (2026-07-05, see engine/decisions.md; RESOLVED 2026-07-19,
backlog #243, see engine/decisions.md "WorldState: read-only Working
Memory / Durable Knowledge groupings added"): WorldState conflates two
different kinds of state under one container:
- Durable Knowledge: Facts, Claims, Goals, Decisions, Unknowns, Entities
  (+ the id-bearing Assumption/Inference/EmotionalSignalItem lists added
  2026-07-12/07-15) -- things actually true (or believed/weighed) about
  the user's world, meant to persist and accumulate across the whole
  relationship.
- Working Memory: surface_complaint/core_question/core_question_confidence,
  assumptions/inferences/biases (the flat string lists), clarity_level,
  phase -- reasoning scaffolding Judgment needs turn-to-turn to track
  where the CONVERSATION currently stands, not facts about the user's
  world.
Originally deferred pending Judgment's actual usage patterns making the
right split obvious, rather than guessed at up front. The founder was
asked directly whether to pursue an actual restructure now, given no
concrete downstream consumer has asked for it and the original
ambiguity (were assumptions/inferences durable or scratchpad?) had
already partially self-resolved through later incremental work (the
id-bearing `_items` counterparts landing in the Durable Knowledge
bucket). **Chose read-only groupings only** -- see
`WorldState.durable_knowledge()`/`working_memory()` below: plain
methods grouping the existing fields for any future reader, not a
restructure of WorldState's own shape. No existing caller, prompt, or
persisted JSON is affected.
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
    Goal, Decision, Unknown, Entity, Assumption, Inference), so the
    Durable Knowledge grouping (see module DESIGN NOTE above,
    `WorldState.durable_knowledge()`) has a single, consistent base to
    work from rather than six-plus ad hoc shapes.

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
    status defaults to "open"; a resolved Unknown now transitions to
    "resolved" in place (fixed 2026-07-19, backlog #246, see
    engine/decisions.md "State builder: Unknown resolution keeps
    history in place" and src/state/builder.py::_reconcile_unknowns) --
    previously discarded outright and promoted into a brand-new Fact
    with no back-link, which Design Principle 3 ("nothing is silently
    deleted") argued against, same parity fix already proven for
    Facts/Claims via `superseded` (backlog #245). src/understanding/
    engine.py's own Tier 1 visibility filter only shows `{"open"}`
    Unknowns, so a resolved one stays correctly hidden from display --
    this only stops discarding provenance/history nothing currently
    reads, it doesn't change what's ever visible.
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
    is plain List[str], no per-item signal exists to use instead. NOT A
    REAL SIGNAL (see validation report Failure Mode #8, engine/decisions.md
    "Tier 1 completeness + has_knowledge_correction calibration"): every
    Assumption gets the identical value regardless of content -- it is
    an epistemic-TIER placement only, not a per-item quality score. Do
    not sort, filter, or rank Assumptions by `.confidence`; see
    ASSUMPTION_TIER_CONFIDENCE's own comment for what a real fix would
    require.
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


EmotionalSignalStatus = Literal["active", "retracted"]


class EmotionalSignalItem(KnowledgeItem):
    """
    Added 2026-07-15 (see engine/decisions.md "Tier 1 completeness +
    has_knowledge_correction calibration" -- validation report Failure
    Mode #4): closes a genuine SCHEMA gap, not a rendering one --
    Interpretation's own EmotionalSignal (emotion/intensity/confidence/
    source, see src/interpretation/schema.py) was computed every turn
    and then discarded before WorldState even existed, unlike every
    other Interpretation output. Deliberately NOT paired with a
    pre-existing flat `List[str]` the way Assumption/Inference are (see
    their docstrings) -- there was no flat `emotional_signals` field to
    preserve compatibility with; this data had no home in WorldState at
    all before now, so it can start directly as a structured type.

    Unlike Fact/Claim/Assumption/Inference (dedup by content, existing
    items never updated in place), this list is keyed by `emotion` and
    UPDATED in place on a repeat (see
    src/state/builder.py::_merge_emotional_signals) -- intensity is
    inherently a live reading that changes turn to turn for the same
    named emotion, not a fact that's simply reaffirmed. Treating a
    same-emotion recurrence as a brand-new entry would reproduce this
    same report's Failure Mode #3 (unbounded near-duplicate
    accumulation) for emotions specifically; treating it as an
    unchanged duplicate would leave a stale intensity on record
    indefinitely. `confidence` is REAL per-item data (Interpretation's
    own calibrated EmotionalSignal.confidence), same treatment as
    Inference.
    """

    emotion: str
    intensity: float = Field(ge=0.0, le=1.0)
    source: Literal["explicit", "inferred"]
    status: EmotionalSignalStatus = "active"


class WorldState(BaseModel):
    # --- Working Memory (see module DESIGN NOTE above, WorldState.working_memory()) ---
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

    # --- Durable Knowledge (Core Structure; see WorldState.durable_knowledge()) ---
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

    # Added 2026-07-15 (see EmotionalSignalItem above and
    # engine/decisions.md "Tier 1 completeness + has_knowledge_correction
    # calibration" -- validation report Failure Mode #4). Excluded from
    # Judgment/Planner/Response's prompts below, same reasoning as
    # assumption_items/inference_items -- this exists for
    # src/understanding/ to render, not as a new signal for the existing
    # pipeline stages to reason over.
    emotional_signal_items: List[EmotionalSignalItem] = Field(default_factory=list)

    # v1.1 (added 2026-07-10, see engine/decisions.md "WorldState
    # provenance -- trajectory prerequisite"): incremented exactly once
    # per turn, solely by src/state/builder.py::update_state -- the single
    # per-turn WorldState mutation entrypoint. 0 for a brand-new session
    # with no turns yet. Nothing else (Orchestrator, the API layer) needs
    # to know about or manage this counter.
    turn_count: int = 0

    # Added 2026-07-22 (direct founder feedback: conversations felt
    # "repetitive... asked the same questions again and again" -- see
    # engine/decisions.md and src/planner/engine.py's own
    # apply_repeated_question_filter): a live 11-turn walkthrough dispatch
    # confirmed Planner's prompt-only mandatory rule against re-selecting
    # a stagnant question was followed inconsistently -- the exact same
    # question string recurred verbatim across several turns regardless.
    # This is pure mechanical bookkeeping (a rolling window of literal
    # questions_to_explore text Planner has already produced), written
    # and read only by src/planner/engine.py/src/orchestrator/engine.py --
    # never reasoned over by any LLM, hence excluded from every prompt
    # below, same treatment as `understanding`.
    recent_planner_questions: List[str] = Field(default_factory=list)

    # Added 2026-07-22 (second live regression on the SAME conversation
    # shape: the founder's own report reads "same issues again reverting
    # back to asking about hardest part when better questions exist,"
    # after the `recent_planner_questions`/generic-difficulty-question
    # filter above had already shipped). Root cause: that filter only
    # ever operated on Planner's OWN candidate list
    # (`planner.questions_to_explore`) -- but Response Generator is not
    # required to lift a candidate verbatim (`src/response/prompt.py`'s
    # own STRUCTURE rule says "phrase it so it reads naturally on its
    # own"), and `recent_planner_questions` is itself excluded from every
    # prompt (see PROMPT_EXCLUDED_FIELDS below) -- so Response had no way
    # to know it had already asked a "what's been the hardest part"
    # question three turns running; it isn't disobeying a rule, it
    # simply never sees its own recent output. This field is the fix:
    # the literal question SENTENCE actually extracted from each turn's
    # real `Response.response_text` (see
    # src/response/engine.py::extract_asked_question), which is what the
    # user actually read, not an upstream approximation of it -- and,
    # unlike `recent_planner_questions`, this one IS deliberately passed
    # to Response Generator (see src/response/prompt.py::build_messages'
    # `recent_questions` parameter) precisely so it can see its own
    # recent phrasing and avoid repeating it. Still excluded from the
    # bulk `model_dump_json` prompt payload below (passed as its own
    # explicit parameter instead, kept short) for the same reason
    # `recent_planner_questions` is -- pure bookkeeping, not something to
    # reason over via the full WorldState dump.
    recent_response_questions: List[str] = Field(default_factory=list)

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

    # Read-only groupings (added 2026-07-19, backlog #243, see
    # engine/decisions.md "WorldState: read-only Working Memory /
    # Durable Knowledge groupings added" -- the founder's own explicit
    # choice, over both closing the item outright and a full restructure)
    # -- give this module's own "Working Memory / Durable Knowledge"
    # TODO above a real, usable shape for any future reader (e.g. an
    # inspector) WITHOUT restructuring WorldState's actual fields: plain
    # methods, not pydantic fields or @computed_field properties, so
    # they're invisible to model_dump_json() and every existing
    # prompt-building call site -- zero behavior change, zero migration
    # cost for already-persisted flat JSON, no new entry needed in
    # PROMPT_EXCLUDED_FIELDS below. `turn_count`/`understanding` are
    # deliberately excluded from both groupings -- they're WorldState's
    # own bookkeeping/rendering layer, not "facts about the user's
    # world" or "conversation-tracking scratchpad."
    def durable_knowledge(self) -> dict:
        """The Durable Knowledge half of this module's own TODO --
        things actually true (or believed/weighed) about the user's
        world, meant to persist and accumulate across the whole
        relationship."""
        return {
            "facts": self.facts,
            "claims": self.claims,
            "goals": self.goals,
            "decisions": self.decisions,
            "unknowns": self.unknowns,
            "entities": self.entities,
            "assumption_items": self.assumption_items,
            "inference_items": self.inference_items,
            "emotional_signal_items": self.emotional_signal_items,
        }

    def working_memory(self) -> dict:
        """The Working Memory half -- reasoning scaffolding Judgment
        needs turn-to-turn to track where the CONVERSATION currently
        stands, not facts about the user's world. `assumptions`/
        `inferences`/`biases` (the flat string lists) stay here, per
        this module's own original TODO framing -- their id-bearing
        `_items` counterparts above are Durable Knowledge instead."""
        return {
            "surface_complaint": self.surface_complaint,
            "core_question": self.core_question,
            "core_question_confidence": self.core_question_confidence,
            "assumptions": self.assumptions,
            "inferences": self.inferences,
            "biases": self.biases,
            "clarity_level": self.clarity_level,
            "phase": self.phase,
        }


# Added 2026-07-12 (see engine/decisions.md "Understanding layer --
# Journey-scoped identity"): src/judgment/engine.py, src/planner/engine.py,
# and src/response/engine.py all dump the FULL WorldState verbatim into
# their prompts (`state.model_dump_json(indent=2)`, no field filtering).
# Left unexcluded, `understanding`/`assumption_items`/`inference_items`/
# `emotional_signal_items` would silently start flowing into all three
# already-calibrated prompts the moment they exist -- pure token waste
# at minimum, and a real behavior-regression risk at worst (a model
# citing/quoting `understanding` text back, or treating
# assumption_items/inference_items/emotional_signal_items as a distinct
# new signal alongside the existing flat assumptions/inferences lists
# they duplicate, or alongside nothing at all for emotional signals,
# which have no pre-existing flat-list counterpart to be consistent
# with). Defined once here, imported by all
# three engines' `model_dump_json(..., exclude=PROMPT_EXCLUDED_FIELDS)`
# call, rather than three independently-maintained copies of the same set.
PROMPT_EXCLUDED_FIELDS = {
    "understanding", "assumption_items", "inference_items", "emotional_signal_items",
    "recent_planner_questions", "recent_response_questions",
}
