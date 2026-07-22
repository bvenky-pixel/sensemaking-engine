Confidant Understanding Feedback Signals Specification v1

Status: SPEC ONLY. Nothing in this document has been implemented.
Written from the founder/CPO product-direction memo "Make Understanding
Visible, Not Just Better" (2026-07-22, Priority 3), grounded against the
actual current implementation (`src/instrumentation/`,
`frontend/app/src/screens/Journey.svelte`'s reflection-prompt flow,
backlog #207). Same discipline as every other spec in this set:
implementation only after this is confirmed.

---

Purpose

From the product-direction memo: "Conversation length is not a proxy for
understanding." We need direct signals for three specific questions:

1. Did Confidant understand the situation?
2. Did Confidant surface something useful?
3. Did Confidant help create clarity?

This is a genuinely new product capability -- unlike Priorities 1 and 2,
there is no existing mechanism doing most of this work today. This spec
is smaller in code surface than the other three, but it is the one this
codebase has the least existing muscle memory for, since everything
built so far measures MODEL compliance (does Judgment correctly populate
a field) rather than USER-perceived value.

---

Three Signal Types

### 1. Explicit micro-feedback (new)

The only existing precedent is the Journey-close reflection question
(backlog #207, `Journey.svelte`'s `showReflectionPrompt` flow) -- an
opt-in, free-text "anything about this conversation you'd want to
remember or reflect on?" at the moment a person leaves a Journey. That
flow already proves the RIGHT pattern for this product: quiet, opt-in,
appears at a natural transition point, never a modal interrupting a live
exchange.

**Proposal**: extend that same moment (Journey close), not invent a new
interruption elsewhere, with a second, equally quiet, equally optional
question specifically about understanding -- e.g. "Did this conversation
help you see your situation more clearly?" with a small set of real
answers (not a 1-5 star rating -- consistent with this product's
existing "no dashboard chrome, no score" discipline). A person who skips
the existing reflection question skips this too; this is additive to
that flow, not a second gate.

A second, more granular option worth naming even though it's a bigger
product decision: a light per-response reaction (something in the
spirit of the existing real choice-button pattern already used for
`Response.options`) letting a person mark a SPECIFIC turn as "that
helped" or "that's not quite right," closer to where the misunderstanding
or the useful moment actually happened rather than only at Journey close.
This is more instrumentation surface (needs its own storage, its own
API shape) and more UI surface (a new affordance on every turn) than the
Journey-close extension -- see Open Questions.

### 2. Mechanical proxy signals (new, but cheap -- pure WorldState arithmetic)

Not a substitute for explicit signal, but a real, always-on, zero-friction
leading indicator, in the same spirit as `compute_stagnation_signals`
(deterministic, non-LLM, already-proven pattern in this codebase):

- **Unknown resolution rate**: fraction of Unknowns that transition
  `open -> resolved` within a Journey (mechanical -- `Unknown.status`
  transitions are already tracked, see backlog #246).
- **Contradiction resolution rate**: fraction of flagged contradictions
  that lead to an actual `knowledge_correction` (already tracked --
  `has_knowledge_correction`/`knowledge_corrections`).
- **Decision resolution rate**: fraction of open Decisions that reach
  `resolved`/`deferred` rather than staying open indefinitely (already
  tracked -- `has_decision_resolution`/`decision_resolutions`).
- **Repetition rate** (a DIRECT, ironic, but genuinely useful proxy given
  this week's own fix): how often `apply_repeated_question_filter`
  actually had to drop something. A Journey where this fires often is
  mechanically evidence of exactly the "going in circles" feeling the
  founder's original complaint named -- this metric already has real
  code computing it as of this week; it just isn't logged/aggregated
  yet.

None of these require asking the user anything. All of them are
computable today, retroactively, from data already being produced.

### 3. Aggregate reporting (new, Instrumentation-layer)

Both signal types need to roll up somewhere a human can actually look at
them over time -- the same role `src/instrumentation/usage.py`'s
`UsageTracker`/`print_turn_summary`/usage-report workflow already plays
for cost/latency/reliability. Proposal: a parallel "understanding
quality" report, same shape (per-component and aggregate breakdowns,
`workflow_dispatch`-triggered like `usage-report.yml`), not a live
dashboard -- consistent with this product having no internal admin
dashboard today.

---

The Priority 4 Connection

This spec and `counseling-modes-frameworks-specification-v1.md` are
designed to compose: that spec proposes a new Planner field,
`success_criterion`, populated according to the active mode's own
definition of success (e.g. Strategize: "the decision becomes easier";
Vent: "the user feels more understood than when they started"). Once
that field exists, signal type 1 (explicit feedback) can be asked IN
THOSE TERMS turn-by-turn rather than only as a generic end-of-Journey
question -- "did this get you closer to [whatever this turn's own
stated success_criterion was]?" -- which is a sharper, mode-aware
question than a generic one. This spec does not depend on that field
existing to ship signal types 2 and 3, but signal type 1's most
interesting version does.

---

Non-Goals

- Not an NPS survey product. No periodic "rate us" popups, no email
  surveys, nothing outside the product's own existing quiet moments.
- Not a visible score shown back to the user. "Understanding quality"
  is a product-team-facing metric, the same way `UsageTracker`'s cost/
  latency numbers are -- never a number a user sees about their own
  conversation.
- Not a replacement for judgment. These signals inform product
  decisions; they don't automatically gate anything (e.g. this spec
  does NOT propose auto-tuning prompts based on feedback scores -- that
  would be a much larger, separate, and currently unscoped capability).

---

Open Questions

1. **Per-turn reaction vs. Journey-close-only.** Per-turn is more
   granular and catches the exact moment something worked or didn't,
   but is real new UI surface on every single response, in a product
   whose whole visual philosophy has been restraint (no icons, minimal
   chrome). Journey-close-only is cheap and proven (extends #207) but
   coarse -- a great turn 3 and a bad turn 9 average out to "fine."
   Recommend starting Journey-close-only and revisiting per-turn only if
   the coarse signal proves too noisy to act on.
2. **Does a person's feedback here feed the Personal Operating Model or
   Learning** (e.g. "this person tends to find Explore mode more useful
   than Vent") -- a real, valuable connection, but one that expands this
   spec's scope into POM/Learning territory rather than staying a pure
   measurement spec. Recommend treating as a clearly-labeled FUTURE
   consideration, not in this round.
3. **Retention/privacy scope.** Given this product's existing privacy
   discipline (export-all, delete-all, per-account scoping enforced
   everywhere else), explicit feedback text needs the same treatment
   from day one, not bolted on later -- confirm this is understood as a
   requirement, not an open question, before implementation.

---

Rollout

1. Extend the Journey-close reflection flow (backlog #207) with the
   second, understanding-specific question -- smallest possible surface,
   reuses an already-shipped, already-proven UX pattern.
2. Add the four mechanical proxy computations as a new, small module,
   same "deterministic, non-LLM, pure WorldState arithmetic" pattern as
   `compute_stagnation_signals` -- no new LLM calls, no new cost.
3. Add the aggregate report, mirroring `usage-report.yml`'s existing
   shape exactly.
4. Only after Priority 4 ships `success_criterion`: revisit signal type
   1 to ask the mode-aware version of the question.
