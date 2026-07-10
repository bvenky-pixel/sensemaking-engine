# Interpretation Specification — v1.1 (additive to v0.9)

**Status:** FROZEN — approved 2026-07-09. Promotes
`engine/specs/interpretation-v1.1-proposal.md` (discussion draft, added
2026-07-05, explicitly "NOT FROZEN, NOT IMPLEMENTED") to a real spec,
resolving its two open questions. Implemented directly alongside this
freeze (schema + prompt + State Builder merge), per the same
schema-first discipline v0.9 established — this document exists so the
decision is written down in the same format as every prior version, not
because prompt/code came first.

**Predecessor:** v0.9 (`interpretation-spec-v0.9.md`) — this document is
purely additive. No v0.9 field changes, removes, or renames.

**Why now:** the 2026-07-05 WorldState state-evolution suite confirmed
three gaps the State Builder was explicitly told NOT to paper over with
heuristics (`engine/decisions.md`): Goal/Decision lifecycle advancement
and Entity attribute enrichment. All three needed a real signal from
Interpretation — this document is that signal, for two of the three
(Goal/Decision lifecycle, Entity attribute enrichment). The 2026-07-09
30-test `gpt-4o-mini` validation run (`experiments/confidant-validation/log.md`)
reconfirmed the same evidence-backed need and this is now scoped
alongside that round's other fixes.

**Note on the third confirmed-declined gap (Fact contradiction/supersede
at the WorldState layer):** NOT addressed by this document. That gap is
handled differently — Judgment's existing `contradictions` field
(`judgment-specification-v2.md`) already owns "detect a conflict"; this
round strengthened its prompt (see `engine/decisions.md`) rather than
adding a new Interpretation signal. Actually marking a Fact `superseded`
in WorldState would require a write-back path from Judgment into
WorldState that doesn't exist today (Judgment only reads WorldState,
and `update_state` already ran earlier in the same turn) — a distinct,
bigger architectural question, explicitly out of scope here.

---

## Resolved open questions (from `interpretation-v1.1-proposal.md`)

### Option A vs. Option B → **Option A**

Interpretation stays stateless per turn (`build_messages(user_text)`
still takes only the raw message, no WorldState view). Every field below
identifies its target with a best-effort paraphrase/quote, matched
against existing WorldState content downstream by
`src/state/builder.py`'s existing word-overlap mechanism (the same one
`_reconcile_unknowns` already uses for unknown resolution), not a stable
ID (WorldState has none yet — deferred to a future provenance round per
`world_state.py`'s module docstring).

Reasoning: Option B (giving Interpretation read access to open
Goals/Decisions/Entities) is architecturally cleaner but is a materially
bigger change — larger prompts, more cost/turn, and Interpretation stops
being a pure function of one message. Option A is adoptable without
restructuring the pipeline, and narrows the existing string-matching
problem from "does this event exist at all" (which Interpretation now
owns) to "which stored item does this refer to" (a bounded, mechanical
lookup) — the same category of tradeoff already accepted when unknown
resolution moved from exact-substring to word-overlap matching.
**Revisit Option B only if Option A's match quality proves inadequate in
real use**, not preemptively.

### Goal Updates: additive vs. replace `goals` → **additive**

`goals: List[str]` (v0.9) stays pure extraction — a freshly-stated goal
with no existing match is simply new. `goal_updates` (this document) is
a separate field for transitions on an existing goal. Avoids a breaking
change to Interpretation's output shape for the uncertain benefit of
collapsing the two.

---

## New fields

### `goal_updates`

1. **Purpose:** signal a lifecycle transition on a goal already tracked
   in WorldState — the gap that left a stated goal `active` forever even
   after the user described completing, pausing, or abandoning it.
2. **Definition:** a list of `{goal, status}` pairs. `goal` is a
   best-effort paraphrase/quote of the existing goal this refers to
   (never a newly-stated goal — that belongs in `goals`). `status` is
   only included when the user's own words describe the goal's fate;
   never inferred from elapsed time or a merely-plausible-sounding
   co-occurring fact.
3. **Type:** `List[GoalUpdate]`, `GoalUpdate = {goal: str, status: Literal["active","paused","completed","abandoned"]}`.
4. **Allowed values:** `status` reuses the same four values as
   WorldState's `GoalStatus` (duplicated as a Literal in
   `src/interpretation/schema.py`, not imported — see that file's
   comment for why: same reasoning as `builder.py`'s duplicated
   `_word_overlap`, keeping Interpretation and WorldState independently
   versionable).
5. **Examples:**
   GOOD: user who said "I want to build Confidant" earlier later says "I
   launched the MVP" → `goal_updates=[{goal: "build Confidant", status: "completed"}]`.
   BAD: inferring `status="completed"` just because several turns have
   passed with no further mention — no textual evidence, no update.
6. **Validation rule:** none at the Interpretation schema level (a
   `GoalUpdate` naming a goal with no match is legal Interpretation
   output). Enforced downstream: `src/state/builder.py`'s
   `_apply_goal_updates` drops any update whose `goal` text doesn't
   sufficiently word-overlap an existing Goal — never fabricates a new
   Goal from an unmatched update.
7. **Downstream consumer:** `src/state/builder.py::_apply_goal_updates`,
   which transitions the matching `WorldState.Goal.status` in place.

### `decision_events`

1. **Purpose:** signal something that happened to a decision option
   already tracked in WorldState (chosen, rejected, deferred) — the gap
   that left a named option `open` forever even after the user
   effectively decided.
2. **Definition:** a list of `{option, event}` pairs. `option` is a
   best-effort paraphrase/quote of the existing option (never a newly-
   named option — that belongs in `decision_options`, kept strictly
   extractive per v0.9).
3. **Type:** `List[DecisionEvent]`, `DecisionEvent = {option: str, event: Literal["proposed","chosen","rejected","deferred"]}`.
4. **Allowed values:** `event` includes `"proposed"` for Interpretation's
   own honesty (an option being newly floated, distinct from a
   transition) even though the merge layer currently no-ops on it (see
   Validation rule) — `decision_options` already covers proposing a new
   option.
5. **Examples:**
   GOOD: two options stated ("wait" / "apply externally"), later turn
   says "I've decided to wait" → `decision_events=[{option: "wait", event: "chosen"}, {option: "apply externally", event: "rejected"}]`
   (the second entry only if the evidence actually supports treating the
   other option as ruled out, not merely unmentioned).
   ASYMMETRIC CASE (2026-07-10, see engine/decisions.md): when only ONE
   side of a decision was ever extracted as its own `decision_option`
   (the other side — often the status quo — was never separately
   named), `option` MUST still anchor to the side that already exists,
   never a fresh label for whichever side just "won." Only "apply
   externally" ever named → user says "I've decided to wait until Q3" →
   `decision_events=[{option: "apply externally", event: "deferred"}]`,
   NOT `{option: "wait until Q3", event: "chosen"}` (the latter cannot be
   matched to anything in `decision_options` by
   `src/state/builder.py::_apply_decision_events`'s word-overlap check,
   so the event is silently dropped — confirmed via the 10-turn
   WorldState walkthrough before this fix).
6. **Validation rule:** `has_decision_event: bool`, `decision_event_option:
   str`, `decision_event_type: Literal["","chosen","rejected","deferred"]`
   (added 2026-07-10, see engine/decisions.md "decision lifecycle
   boolean-gate"). Even with the asymmetric-case prompt fix above, two
   live samples of the exact same walkthrough turn showed the model
   either inventing an unmatchable option label or emitting no
   `decision_events` entry at all — the identical silent-omission shape
   `has_assumption`/`has_risk_signal` were built to fix, so the same
   lever was applied here. Unlike those two fields, a single free-text
   reasoning field can't be mechanically relocated into `decision_events`
   on repair (an event needs a specific EXISTING option AND an event
   type, not just a sentence) — so instead of prose, the anchor is asked
   for directly as two small structured fields. `Interpretation`'s
   `model_validator` reconstructs a `DecisionEvent` from
   `decision_event_option`/`decision_event_type` if `has_decision_event`
   is true and `decision_events` is still empty — a mechanical
   relocation of already-structured fields, not a parse of free text.
   Downstream, `src/state/builder.py::_apply_decision_events` maps
   `"chosen"`/`"rejected"` to `WorldState.DecisionStatus = "resolved"`
   (an option no longer being actively weighed, whether it was picked or
   ruled out — matching `Decision`'s own docstring reading of
   `"resolved"`). `"proposed"` is a no-op on status (`decision_options`
   already covers it). `"deferred"` maps to its own real
   `DecisionStatus = "deferred"` (added 2026-07-10, closing exactly the
   gap this entry originally flagged as deliberately left for a future
   round, once real usage — the walkthrough's "wait and see" case —
   showed it was needed).
7. **Downstream consumer:** `src/state/builder.py::_apply_decision_events`.

### `entity_attribute_updates`

1. **Purpose:** give `Entity.attributes` (defined in `world_state.py`
   since WorldState v1, always empty until now) a real data source — the
   gap that left an entity's record empty even after the user stated a
   specific new fact about them (a role, a relationship).
2. **Definition:** a list of `{entity, attribute, value}` triples. Only
   included when the user directly states a specific attribute — never
   inferred. `entity` should match the name used in `entities` when the
   entity is also plainly mentioned that turn, but doesn't have to be —
   the attribute statement itself is evidence the entity exists.
3. **Type:** `List[EntityAttributeUpdate]`, `EntityAttributeUpdate = {entity: str, attribute: str, value: str}`.
4. **Allowed values:** free-text `attribute`/`value` — no closed enum
   (unlike `impact_domains`), since roles/relationships/statuses are open-
   ended and a closed set would force real information into "other."
   Revisit only if free-text proves as corruption-prone as the old
   `stakes` field did (v0.9 history) — no evidence of that yet.
5. **Examples:**
   GOOD: "My manager Sarah is being promoted to Head of Product." →
   `entity_attribute_updates=[{entity: "Sarah", attribute: "role", value: "Head of Product"}]`.
   BAD: inventing a role for an entity who was only ever named, never
   described.
6. **Validation rule:** none at the schema level. Downstream,
   `src/state/builder.py::_merge_entities` sets/replaces the matching
   attribute key on the entity (creating the entity if it wasn't
   separately mentioned) — a second update to the same attribute key
   replaces the value in place (Design Principle 2, "refine, don't
   replace," applied per-attribute) rather than appending a duplicate.
7. **Downstream consumer:** `src/state/builder.py::_merge_entities`;
   `WorldState.Entity.attributes` (restructured from `List[str]` to
   `List[EntityAttribute]` in `world_state.py` to actually hold these).

---

## Summary table

| Field | Decision | Confidence this closes the gap |
|---|---|---|
| `goal_updates` | New, additive alongside `goals` | High for the explicit-statement case this was designed for; does not claim to catch inferred/implicit transitions |
| `decision_events` | New, additive alongside `decision_options` | Revisited 2026-07-10 twice: `"deferred"` now maps to a real `DecisionStatus`; prompt anchoring rule added, then escalated to a boolean-gate (`has_decision_event`/`decision_event_option`/`decision_event_type` + auto-repair) after the anchoring-only prompt fix still left two live samples either inventing an unmatchable label or emitting no event at all |
| `entity_attribute_updates` | New, additive alongside `entities`; `Entity.attributes` restructured to hold it | High for the explicit-statement case; matching remains text-based, not ID-based, until WorldState gains stable object IDs |

**Status**: These three fields are FROZEN as of this entry, implemented
alongside the freeze per the discipline established at v0.9 ("no
implementation before the spec is written" — though in this case, spec
and implementation land in the same round, since this document mainly
formalizes decisions already validated in
`tests/test_world_state_evolution.py`). Any further change requires
reopening this process the same way.
