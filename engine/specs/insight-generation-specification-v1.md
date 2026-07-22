Confidant Insight Generation Specification v1

Status: SPEC ONLY. Nothing in this document has been implemented.
Written from the founder/CPO product-direction memo "Make Understanding
Visible, Not Just Better" (2026-07-22, Priority 2), grounded against the
actual current implementation (`src/judgment/`, `src/insight/`,
`src/learning/`). Same discipline as every other spec in this set:
implementation only after this is confirmed.

---

Purpose

From the product-direction memo: "We need moments where users feel the
model understands something they have not explicitly stated." Every
insight must be traceable to evidence, never asserted from inference
alone.

This spec's primary job is NOT to invent five new detection mechanisms
from scratch -- it's to correctly sort the five example insight types
in the memo (contradiction detection, goal stall detection, recurring
avoidance patterns, decision-making tendencies, repeated tradeoff
patterns) into the TWO fundamentally different tiers this codebase
already has, because conflating them would violate an invariant this
codebase has enforced deliberately since Judgment v2 shipped:

> Judgment reasons over ONE Journey's WorldState only. It has no memory
> of any other Journey. A claim like "you tend to avoid conflict" is not
> something any single conversation's evidence can honestly support --
> that requires a PATTERN across multiple Journeys, which is Insight
> Engine / Learning's job, not Judgment's.

---

The Two Tiers

### Tier A -- Per-conversation, real-time (Judgment's existing job)

| Insight type | Status |
|---|---|
| Contradiction detection | **Already built.** `Judgment.contradictions` + `contradiction_significance`, computed every turn, grounded via `supporting_evidence`. Gap is visibility, not detection -- see `clarity-brief-specification-v1.md` section 6. |
| Goal stall detection | **Already built, extended this week.** `compute_stagnation_signals` (mechanical, turn-gap arithmetic) now covers Goals, Decisions, AND Unknowns (see `engine/decisions.md` "Screen overhaul + repetition fix"); `Judgment.stagnation_notes` is the synthesized, filtered-for-significance version. |

Nothing to build here. Both example insight types the memo names as
"per-conversation" already exist, are already evidence-grounded
(`supporting_evidence`, mechanical signal computation), and their only
real gap is that they don't reach the Clarity Brief yet -- addressed in
that spec, not this one.

### Tier B -- Cross-session, offline (Insight Engine / Learning's job)

| Insight type | Status |
|---|---|
| Recurring avoidance patterns | Closest existing analog: `src/learning/` already detects recurring behavioral patterns from `behavioral_events`, gated behind `MIN_EVIDENCE` (currently being calibrated -- task #213, in progress). "Avoidance" is not a currently-named pattern CATEGORY in Learning's vocabulary; this spec proposes adding it as one. |
| Decision-making tendencies | New pattern category for Learning, same mechanism, same evidence-gating -- not a new engine. |
| Repeated tradeoff patterns | New pattern category for Learning OR Insight Engine's cross-session themes (`src/insight/schema.py::Theme`, `MIN_EVIDENCE_SESSIONS = 2`) -- whichever already tracks decision/tradeoff-shaped content is the right home; this spec does not yet resolve which (see Open Questions). |

**Nothing in Tier B requires a new detection mechanism.** Learning
already has: a `behavioral_events` stream, a `MIN_EVIDENCE`-style
gate before a pattern is reported, and a live frontend surface (You
tab). Insight Engine already has: cross-session `Theme`s, each requiring
`MIN_EVIDENCE_SESSIONS = 2` and citing real `evidence_session_ids`. The
work here is adding new named pattern CATEGORIES to whichever of these
two already-evidence-disciplined systems is the right fit -- not
building new plumbing.

---

The Grounding Invariant (carried forward, not new)

"Every insight should be traceable to conversation history" is already
a hard, enforced discipline in this codebase, not a new requirement:

- Judgment's `supporting_evidence` cites real WorldState item ids,
  filtered post-hoc against ids that actually exist (never trusts the
  model's own citations uncritically -- see `run_judgment`'s own
  grounding filter).
- Insight Engine's `Theme.evidence_session_ids` is the same discipline,
  one level up (session ids instead of item ids), with the SAME
  `MIN_EVIDENCE_SESSIONS` floor below which a theme is dropped, not
  reported weakly.
- Learning's `MIN_EVIDENCE` gate is the same discipline again, at its
  own layer.

This spec's only obligation regarding grounding is: any NEW pattern
category (avoidance, decision-making tendency, repeated tradeoff) must
be held to the SAME bar already enforced for existing categories --
never a lower bar just because the category is new and might otherwise
struggle to clear it.

---

Non-Goals

- Not a personality test. No trait scores, no "you are 70% avoidant."
  An insight is a specific, evidenced observation about a specific
  recurring situation, not a permanent character label -- consistent
  with POM's own existing discipline ("never a diagnosis," see
  `personal-operating-model-specification-v1.md`).
- Not a reason to lower any existing evidence floor. If a genuinely
  interesting-sounding pattern can't clear `MIN_EVIDENCE`/
  `MIN_EVIDENCE_SESSIONS`, the correct behavior is silence, same as
  today -- "most candidate sets have no genuine connection" is already
  the default assumption Tier 2 synthesis and Insight Engine both
  operate under, and new pattern categories inherit that same
  skepticism.
- Not a new real-time (per-turn) system for the Tier B insight types.
  Cross-session claims are only ever honest on cross-session evidence,
  which structurally requires the existing offline computation model
  (`workflow_dispatch`-only today, per backlog #268), not a live-turn
  addition.

---

Open Questions

1. **Where does "repeated tradeoff patterns" live** -- Learning
   (behavioral, "how do you tend to approach tradeoffs") or Insight
   Engine (thematic, "this tradeoff shape keeps recurring across
   Journeys")? These are genuinely different framings of similar
   content; needs a founder call, not an engineering default.
2. **Surfacing location.** Tier A insights (contradictions, stalls)
   surface in the Clarity Brief (per that spec). Where do Tier B
   insights surface -- the You tab (alongside POM/behavioral patterns,
   where Learning already lives), a new dedicated surface, or a
   conversational callback INTO a live Journey (POM already has a
   precedent for this -- backlog #210, "Insight-triggered conversational
   callback")? Likely "it depends on the pattern type," but worth an
   explicit decision per category rather than defaulting all of them to
   one surface.
3. **Cadence.** Tier B computation is `workflow_dispatch`-only today
   (backlog #268, deliberate, not yet revisited). New pattern categories
   don't change that constraint on their own, but if Priority 2 is meant
   to feel like a live product capability rather than an occasional
   backfill, this spec's rollout should be sequenced alongside whatever
   resolves #268, not independently of it.

---

Rollout

1. Confirm Tier A requires no new backend work (true today) -- fold its
   visibility gap entirely into the Clarity Brief spec's rollout.
2. Resolve Open Question 1 (Learning vs. Insight Engine home for
   tradeoff patterns) before writing any new pattern-category code.
3. Add "avoidance," "decision-making tendency," and (per Q1's answer)
   "repeated tradeoff" as named categories to whichever system owns
   them, same `MIN_EVIDENCE`-gated, evidence-cited shape every existing
   category already has -- no schema redesign, an additive change.
4. Live-dispatch calibrate the new categories against real multi-
   Journey data, same discipline as every existing Learning/Insight
   Engine calibration round (tasks #289, #292, #293).
