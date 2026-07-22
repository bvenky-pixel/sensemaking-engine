Confidant Clarity Brief Specification v1

Status: SPEC ONLY. Nothing in this document has been implemented.
Written from the founder/CPO product-direction memo "Make Understanding
Visible, Not Just Better" (2026-07-22, Priority 1), grounded against the
actual current implementation (`src/executor/schema.py`,
`src/executor/engine.py::build_clarity_brief`,
`frontend/app/src/components/Understanding.svelte`). Same discipline as
every other Sensemaking Engine / System Architecture spec: implementation
only after this is confirmed.

---

Purpose

Confidant's core thesis, restated in the product-direction memo:

"A conversation should create an increasingly accurate model of a
person's situation over time."

The Clarity Brief is the one artifact whose entire job is to make that
thesis checkable by the person it's about. Today it functions as a
summary -- a reasonable digest of the current turn's key facts. This
spec evolves it into a living model: something a person should be able
to read, at any point in a Journey, and understand their own situation
*without rereading the conversation that produced it* -- and something
that gets more valuable, not just longer, the more a Journey grows.

---

Relationship to what already exists

This is the most important thing this spec has to resolve, because the
app already has three adjacent-but-distinct concepts and conflating them
would be a real design mistake:

1. **Clarity Brief** (`src/executor/schema.py::ClarityBrief`) -- today:
   `situation`, `key_insights`, `current_direction`, `remaining_unknowns`,
   `decisions`. Deterministic template mapping from WorldState/Judgment/
   Planner, no LLM call of its own (Executor's whole design premise --
   see `system-architecture-v2-specification.md`'s Executor section).
2. **Tier 1** (`src/understanding/engine.py::build_tier1_statements`) --
   a raw, unranked, per-item render of WorldState (one statement per
   Fact/Claim/Goal/Decision/Unknown/Entity/Assumption/Inference).
   Deliberately NOT surfaced in the frontend today (see
   `Understanding.svelte`'s own docstring: "a raw, unranked, per-item
   render of WorldState that substantially duplicates what
   situation/key_insights/decisions/remaining_unknowns already show").
3. **Tier 2** (`src/understanding/tier2_engine.py`) -- LLM-synthesized
   statements connecting two or more Tier 1 candidates into something
   neither states alone. Conditional (most turns skip the LLM call),
   rendered today as its own "Putting it together" card.

**Decision this spec makes**: the evolved Clarity Brief ABSORBS Tier 2
conceptually as its "Emerging patterns" section (see below) -- one
artifact, not two adjacent panels that both claim to be "the current
understanding." Tier 1 stays exactly where it is: a debug/completeness
layer, never surfaced to the person, for the same reason already on
record (duplicates what the Brief's own curated sections already show,
with none of the curation). This spec does not touch Tier 1.

---

Non-Goals

- This is not a rewrite of Judgment or Planner. Every new section below
  is either (a) a direct Executor-level mapping from fields Judgment
  ALREADY produces, or (b) one new, narrowly-scoped Judgment field
  (`competing_priorities` -- see below). It is not a license to
  restructure Judgment's existing fields.
- This is not a transcript. The Brief never quotes raw conversation
  text; every section stays a synthesis, same as today.
- This is not a dashboard. No scores, no percentages, no progress bars
  (consistent with `frontend/specs/product-experience-v1.md`'s existing
  "no dashboard chrome" principle) -- prose sections, same voice
  treatment already established in `Understanding.svelte` ("the orb's
  own consciousness," italic voice, gradient-dot bullets).
- This spec does not resolve Priority 3 (measuring whether the Brief is
  actually perceived as useful) -- that's its own spec
  (`understanding-feedback-signals-specification-v1.md`). This spec's
  job is producing a better artifact; measuring its effect is separate.

---

The Eight Sections

| # | Section | Source | Status |
|---|---|---|---|
| 1 | Current situation | `Judgment.situation_assessment` (fallback: `primary_problem`) | Exists today as `situation` (currently sourced from `WorldState.surface_complaint`, a near-verbatim echo of the last message -- see `_SITUATION_ECHO_THRESHOLD` suppression). **Change**: resource this section from `Judgment.situation_assessment`, the field explicitly designed to be "the overarching frame, not a third way of saying primary_problem" -- a real improvement over echoing the last message, not just a rename. |
| 2 | Active decisions | `WorldState.decisions` filtered to `{"open", "deferred"}` | Exists today (`decisions`, just fixed 2026-07-22 to exclude resolved/expired -- see `engine/decisions.md` "Screen overhaul + repetition fix"). No further change needed. |
| 3 | Known facts | `WorldState.facts`, capped and recency-ordered | **New Executor-level mapping, no Judgment change.** Deliberately NOT a Judgment field -- Judgment's own governing law is "produces conclusions, not memory... never restate WorldState verbatim" (see `judgment-specification-v2.md`), so a plain facts listing belongs at the Executor's deterministic-template layer, same as `decisions` already does, not as a new Judgment responsibility. Cap at the N most recently-updated `status="active"` Facts (N is an Open Question below) so this section doesn't grow unboundedly across a long Journey. |
| 4 | Important unknowns | `Judgment.open_unknowns` | Exists today as `remaining_unknowns`. No change needed. |
| 5 | Competing priorities | **New**: `Judgment.competing_priorities: List[str]` | Genuinely new. Not the same as `contradictions` (factual conflict -- two things that cannot both be true) or `secondary_issues` (a real but lower-priority issue). This is tension BETWEEN two things that are both true and both matter: two active Goals pulling in different directions, or a Goal and a Decision in tension. Must name both sides and be grounded in specific WorldState/Judgment content, same grounding discipline as `contradictions`/`risks`. Worked example: Goals = ["Move to the Product team", "Protect the current team relationship with Sarah"] -> `competing_priorities: ["Pushing harder for the Product team move risks straining the relationship with Sarah that the user also wants to protect."]` |
| 6 | Contradictions | `Judgment.contradictions` + `Judgment.contradiction_significance` | **Field exists, currently NEVER reaches the Brief.** Confirmed via `build_clarity_brief`'s own field mapping and its own test (`test_build_clarity_brief_never_touches_judgment_key_blockers_or_active_decisions` establishes the discipline that unmapped fields must not leak in -- `contradictions` is simply not in the map at all today). This is the single highest-leverage, lowest-risk addition in this whole spec: real backend capability, already computed every turn, already grounded, currently invisible. |
| 7 | Emerging patterns | `WorldState.understanding.tier2` (Tier 2 synthesis statements) | Reframe, not new build (see "Relationship to what already exists" above) -- same content, presented as a Brief section instead of an adjacent card. |
| 8 | What changed recently | New diff logic, comparing this Brief to the previous one | Partially exists: `frontend/app/src/lib/deepeningClarity.js::noteDeepeningClarity` already diffs previous vs. current brief into ONE note. This section generalizes that into a real, possibly-multi-item section (e.g. "A new contradiction surfaced: ...", "The decision between X and Y has been resolved: X", "3 turns of no movement on Y -- still true"). Whether this diffing lives in the frontend (as today) or moves server-side for consistency across clients is an Open Question below. |

---

Length and the collapse principle

Direct tension the spec must name explicitly: this is the SAME artifact
the founder complained was "long and intimidating after a few rounds of
conversation" one week before writing the "living model" memo (see
`engine/decisions.md` "Screen overhaul + repetition fix"). Adding four
new sections without addressing this would reintroduce the exact
problem just fixed.

**Resolution**: the full eight-section Brief lives entirely behind the
existing collapse-by-default toggle ("Show what we understand so far"),
already shipped this round. Nothing in this spec argues for making the
Brief default-visible again. Within the expanded view, sections stay
sparse-by-default (an empty section renders nothing, same discipline as
today) so a short Journey's Brief stays short -- length should scale
with what's actually known, not with turn count for its own sake.

One exception worth considering for a DEFAULT-VISIBLE surface (not
gated behind the toggle): section 8 ("what changed recently") is
specifically the one thing worth seeing without expanding anything,
mirroring how `deepeningClarityNote` already renders as a standalone
`.callout` today. This is an Open Question, not a decision, below.

---

Open Questions (for founder/CPO sign-off before implementation)

1. **"Known facts" cap.** How many facts, and ordered how (most
   recently updated vs. most-referenced-in-Judgment's-own-fields)? No
   evidence yet; propose starting at 5 and calibrating from a live
   dispatch, same "first-cut, uncalibrated" discipline as every other
   threshold in this codebase.
2. **Where does "what changed" diffing live?** Frontend (as today,
   simple, but re-derives from scratch differently per client) vs.
   backend (new, requires persisting the previous Brief or its diff-
   relevant fields, but is the single source of truth across any future
   client). Recommend backend, given this spec's own "one Journey, one
   understanding" principle -- but this is a real architecture call, not
   a style preference.
3. **Does "what changed recently" get a default-visible slot**, or does
   it live inside the collapsed section like everything else? Direct
   product-feel decision, not an engineering one.
4. **Does Tier 2's existing conditional-recompute gating (`
   should_recompute_tier2`, most turns skip the LLM call) still make
   sense once Tier 2 becomes an actual Brief section** rather than an
   optional adjacent card? If "emerging patterns" is now a first-class
   section people expect to check, an emptier-than-expected section on
   most turns may read as a gap rather than "nothing new to say" --
   worth a product call on whether the conditional cadence needs
   revisiting once usage data exists.
5. **Naming.** Is "Clarity Brief" still the right name once it's this
   much richer, or does the product warrant a new name for the "living
   model" framing specifically? Not an engineering question.

---

Rollout

1. Add `Judgment.competing_priorities` (schema + prompt + a worked
   example, same pattern as every other Judgment field this codebase
   has added incrementally).
2. Extend `build_clarity_brief`'s mapping: `situation_assessment` re-
   source, `contradictions`, `competing_priorities`, capped `facts`,
   `tier2` folded in as "emerging patterns."
3. Extend `ClarityBriefResponse` (API) and `Understanding.svelte`
   (frontend) to render the new sections, same card treatment already
   established (settled vs. open visual distinction).
4. Live-dispatch verify against the existing 11-turn walkthrough
   transcript (`scripts/run_worldstate_walkthrough.py`) before shipping
   -- same "prove it against real conversation data" discipline as the
   repetition fix.
5. Decide the "what changed" architecture question (Open Question 2)
   before, not during, implementation -- it changes where the work
   happens.
