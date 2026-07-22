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

### 1. Explicit micro-feedback -- the Journey End Survey (decided)

**Decided (founder/CPO, 2026-07-22): Journey-close first, not per-turn.**
Direct founder rationale, worth preserving verbatim because it's the
argument, not just the conclusion: "Most teams over-instrument early.
Per-turn feedback creates noise, fatigue, low signal, clutter. And users
often can't evaluate a single turn. What they can evaluate: 'Did this
conversation help me?'" A per-turn reaction affordance (see the earlier
draft of this section) is explicitly NOT being built in this round --
not deferred vaguely, ruled out with a stated reason.

**The Journey End Survey**, extending the existing Journey-close
reflection flow (backlog #207, `Journey.svelte`'s `showReflectionPrompt`)
with three concrete questions, founder-specified:

1. "Did Confidant understand your situation?" -- 1-5
2. "Did this conversation increase clarity?" -- 1-5
3. "Did Confidant surface anything important?" -- Yes/No

**This revises this spec's own earlier "no 1-5 rating, consistent with
this product's no-dashboard-chrome discipline" stance** -- noted
explicitly rather than silently dropped, since it's a real, deliberate
reversal of a position this document itself took. The resolution: the
existing "no score" principle has always meant no score is EVER SHOWN
BACK to the person about their own conversation -- it has never meant
"never collect a number." A 1-5 input collected once, quietly, at
Journey close, and consumed only by the product team (never rendered
back to the user as a metric about themselves) does not violate that
principle -- it's the same category of thing as `UsageTracker`'s cost/
latency numbers, which this product has always collected without ever
surfacing to the end user. The UI presentation still needs to stay
consistent with the reflection prompt's existing quiet, opt-in card
treatment -- three short questions, not a jarring multi-screen survey
modal -- but the NUMERIC input itself is the founder's own explicit,
reasoned call, not an oversight to relitigate.

A person who skips the existing free-text reflection question can still
independently answer (or skip) the Journey End Survey questions --
these are additive to that flow, not a second gate blocking Journey
close.

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
Vent: "the user feels more understood than when they started"). Given
Journey-close-only feedback is now the decided scope (see above), the
natural composition is NOT turn-by-turn -- it's aggregating the
Journey's own sequence of `success_criterion` values as background
context alongside the Journey End Survey's own three answers when this
gets reported (signal type 3), so a product reviewer can see, e.g.,
"this Journey's Planner was consistently aiming for X, and the person's
own end-of-Journey rating was Y" side by side. This spec does not depend
on that field existing to ship signal types 2 and 3 on their own, but
this richer cross-reference does.

---

Non-Goals

- Not a RECURRING survey product. One Journey End Survey per Journey
  close, not periodic "rate us" popups or email surveys -- still
  confined to the product's own existing quiet, natural transition
  point, not a new interruption pattern layered on top of it.
- Not a visible score shown back to the user. The 1-5/Yes-No answers
  the PERSON gives are theirs to give, same as the existing free-text
  reflection question -- but nothing computed FROM those answers (an
  aggregate "understanding quality" trend, a per-mode breakdown) is ever
  rendered back to them as a metric about their own conversation or
  themselves. That report is product-team-facing only, the same way
  `UsageTracker`'s cost/latency numbers are.
- Not a replacement for judgment. These signals inform product
  decisions; they don't automatically gate anything (e.g. this spec
  does NOT propose auto-tuning prompts based on feedback scores -- that
  would be a much larger, separate, and currently unscoped capability).

---

Open Questions

1. **Does a person's feedback here feed the Personal Operating Model or
   Learning** (e.g. "this person tends to find Explore mode more useful
   than Vent") -- a real, valuable connection, but one that expands this
   spec's scope into POM/Learning territory rather than staying a pure
   measurement spec. Recommend treating as a clearly-labeled FUTURE
   consideration, not in this round.
2. **Retention/privacy scope.** Given this product's existing privacy
   discipline (export-all, delete-all, per-account scoping enforced
   everywhere else), the Journey End Survey's answers need the same
   treatment from day one, not bolted on later -- confirm this is
   understood as a requirement, not an open question, before
   implementation.

---

Rollout

1. Extend the Journey-close reflection flow (backlog #207) with the
   three-question Journey End Survey (two 1-5 questions, one Yes/No) --
   smallest possible surface, reuses an already-shipped, already-proven
   UX pattern.
2. Add the four mechanical proxy computations as a new, small module,
   same "deterministic, non-LLM, pure WorldState arithmetic" pattern as
   `compute_stagnation_signals` -- no new LLM calls, no new cost.
3. Add the aggregate report, mirroring `usage-report.yml`'s existing
   shape exactly, cross-referencing Journey End Survey answers against
   the mechanical proxies (e.g. does a low "did this increase clarity"
   score correlate with a high repetition rate?) -- the first real test
   of whether the mechanical proxies are honest stand-ins for the
   explicit signal.
4. Only after Priority 4 ships `success_criterion`: add the richer
   cross-reference described above (per-Journey `success_criterion`
   sequence alongside that Journey's own End Survey answers).
