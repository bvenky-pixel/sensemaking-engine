# Interpretation v1.1 — Design Proposal (NOT FROZEN, NOT IMPLEMENTED)

**Status:** DISCUSSION DRAFT. This is deliberately not written in the full
per-field spec format of `interpretation-spec-v0.9.md` (Purpose/Definition/
Type/Allowed values/Examples/Validation rule/Downstream consumer) — that
format is for a spec about to be implemented. This document exists to reach
a decision on shape before anything is written that formally, in the same
schema-first / migration-doc / prompt process every prior Interpretation
change has gone through.

**Why now:** WorldState v1's state-evolution tests and the 10-turn live
walkthrough (see `engine/decisions.md` 2026-07-05 entries) confirmed three
gaps that the State Builder was explicitly told NOT to paper over with
heuristics: contradiction detection, Goal/Decision lifecycle advancement,
and Entity attribute enrichment. All three need a real signal from
Interpretation. This document proposes what that signal should look like.

---

## The one architectural fact that changes the scope of this proposal

**Interpretation is currently stateless per turn.** `build_messages(user_text)`
in `src/interpretation/prompt.py` takes only the raw user message — it has
no view into the accumulated `WorldState` (no existing Goals, Decisions,
Unknowns, or Entities). This matters because every concept below
("this goal is now completed," "this decision replaces that one," "this
entity has a new attribute") is inherently a statement about something
**already tracked** — and without object IDs (deferred to WorldState v1.1
per the original WorldState v1 entry in `decisions.md`) or some view into
what's already known, Interpretation can only refer back to an existing
item by re-describing it in text.

That leaves two real options, and the choice affects every field proposed
below:

**Option A — keep Interpretation stateless.** New typed fields can assert
*that* something changed and *roughly what it refers to* (a best paraphrase
or quote), but matching that reference to a specific existing `Fact`/`Goal`/
`Decision`/`Entity` still happens downstream, via text similarity. This is a
lighter change (no pipeline restructuring) but doesn't fully eliminate
string-matching — it relocates it from "does this event exist at all"
(the part Interpretation should own) to "which stored item does this event
apply to" (a narrower, more mechanical lookup problem, but still not free
of ambiguity).

**Option B — give Interpretation limited state awareness.** Pass a compact
list of currently-open Goals/Decisions/Entities (content strings only, no
full WorldState) into the prompt as additional context, so the model can
quote an existing item back verbatim when referring to it — turning the
downstream match into the same exact-content lookup the State Builder
already does for ordinary accumulation, rather than a fuzzy one. This is
architecturally cleaner (Interpretation, which actually has language
understanding, does the "is this the same thing" judgment instead of a
string-matching function doing it implicitly) but is a bigger change: larger
prompts, more tokens/cost per turn, and Interpretation stops being a pure
function of a single message.

**This is the central open question this proposal surfaces.** The three
typed concepts below are written to work under Option A (so they're
adoptable without a pipeline change), but are more architecturally sound
under Option B. Recommend deciding this before writing the real spec,
since it changes the shape of all three fields (a `target` field that's a
best-effort paraphrase under Option A becomes closer to a real reference
under Option B).

---

## Proposed typed concepts

### 1. Decision Events

**Purpose:** let Interpretation signal that an existing decision option was
chosen, rejected, or deferred — the exact gap that left `"Apply externally"`
sitting `open` forever in the walkthrough even after turn 10's actual
decision to wait.

**Shape (illustrative, not final):**
```
DecisionEvent:
    option: str            # paraphrase/quote of the decision option this refers to
    event: Literal["proposed", "chosen", "rejected", "deferred"]
```
Additive alongside the existing `decision_options: List[str]` (which stays
extractive-only, per the frozen "STRICTLY EXTRACTIVE" rule) — `decision_options`
covers "here's a new option now on the table," `decision_events` covers
"here's what happened to an option already on the table."

### 2. Goal Updates

**Purpose:** let Interpretation signal a lifecycle transition on an existing
goal — the gap that left "Build Confidant" `active` forever even after
"I launched the MVP."

**Shape (illustrative, not final):**
```
GoalUpdate:
    goal: str               # paraphrase/quote of the goal this refers to
    status: Literal["active", "paused", "completed", "abandoned"]
```
Note this maps directly onto `GoalStatus`, already defined in
`src/state/world_state.py` — **no WorldState schema change needed**, only
(in a future round) a State Builder merge update to consume it.

**Open question:** should this replace the existing `goals: List[str]`
field, or stay additive like Decision Events above? A freshly-stated goal
is arguably just a `GoalUpdate` with `status="active"` and no prior match —
replacing would remove a redundant field, but is a breaking change to
Interpretation's output shape. Flagging rather than deciding here.

### 3. Entity Attribute Updates

**Purpose:** let Interpretation emit a structured attribute about an entity
— the gap that left Sarah's entity record empty even after "she's being
promoted to Head of Product."

**Shape (illustrative, not final):**
```
EntityAttributeUpdate:
    entity: str             # entity name, matches Entity.name
    attribute: str          # e.g. "role"
    value: str              # e.g. "Head of Product"
```
Additive alongside the existing flat `entities: List[str]` (kept for plain
mentions with no new attribute info). Maps onto `Entity.attributes`,
already defined in `src/state/world_state.py` as `List[str]` — would need
that field's type reconsidered in a future WorldState round (unchanged in
this proposal, per instruction not to touch the WorldState schema now).

### 4. A generalized "Knowledge Update Operation" instead of three fields?

**Recommendation: no — keep three distinct typed fields, not one
generalized operation.** Reasoning, grounded in this project's own already-
learned lesson (see `decisions.md`'s epistemic-tier history: a single
`facts` bucket collapsed observed/asserted/implied/inferred content into one
representation, and splitting it into five explicit tiers was the fix, not
a rule added to keep them apart):

- A generalized op (`{target_tier, target, operation, payload}`) forces a
  Decision "chosen" event, a Goal "paused" transition, and an Entity
  attribute change into one shape despite having genuinely different
  payloads and semantics. That's the same flattening mistake in a new
  location.
- Distinct, narrowly-named fields are easier for a lightweight model to
  populate reliably (a focused field with a focused prompt instruction beats
  a polymorphic field needing a discriminator plus conditional payload) and
  easier to validate with Pydantic (no loose dict payload, no runtime shape
  dispatch).
- The one place a shared concept legitimately helps — how a "target" gets
  matched to an existing stored item — isn't really about the operation
  type at all, it's the Option A/B question above. Solving that once
  (however it's resolved) benefits all three fields without needing them to
  share a schema.

---

## Summary of decisions still needed before this becomes a real spec

1. **Option A (stateless Interpretation, text-matched targets) vs. Option B
   (Interpretation sees current open Goals/Decisions/Entities as context)** —
   the single biggest fork; affects every field's real shape and the
   pipeline itself, not just the schema.
2. **Goal Updates: replace `goals: List[str]` or stay additive** alongside
   it?
3. Whether `decision_options` and the new `decision_events` are both
   needed, or whether a single richer `Decision` structure could serve
   both roles once this gets to the actual schema-first spec stage.

No code, prompt, or schema changes are proposed or implied by this
document. Per the same process every prior Interpretation version has
gone through: this discussion draft, then (if approved) a frozen spec,
then a migration document, then prompt/code — in that order.
