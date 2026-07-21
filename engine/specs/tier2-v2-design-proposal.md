# Tier 2 v2 — Design Proposal

**Status:** DISCUSSION DRAFT (2026-07-19, backlog #248, see
engine/decisions.md "Understanding: Tier 2 v2 design proposal drafted").
Written at the founder's explicit direction, after research confirmed
`engine/specs/understanding-specification-v1.md`'s own reference to
"declarative-uncertainty and values-level synthesis" (Open Question #4)
named two phrases with no concrete definition anywhere in this
codebase -- not a scoped feature, just a name. This document is the
first attempt at giving those two phrases a real, concrete shape, for
review before anything is built.

This is a design document, not a schema specification.

No prompt, schema, or code changes are implied by this document.

---

# Executive Summary

Tier 2 v1 (`src/understanding/tier2_engine.py`) already does one kind of
cross-candidate synthesis: connecting two or more Tier 1 candidates into
a single `kind="synthesis"` statement that describes a SITUATION --
never a trait, label, or diagnosis of the person (`tier2_prompt.py`'s
own law 5). This is deliberately restrained: most turns produce zero
Tier 2 statements, and the one kind that exists stays close to the
evidence.

Tier 2 v2 asks whether there's a genuinely DIFFERENT kind of synthesis
worth adding, beyond situational connection -- specifically, two ideas
floated (but never defined) when backlog #248 was created:

1. **Declarative uncertainty** -- naming the SHAPE of what remains
   unknown, across several candidates, as a stated fact rather than a
   restated question.
2. **Values-level synthesis** -- naming a TENSION between two things
   the person appears to be weighing, when their own words already
   name both sides.

Both are proposed as narrow EXTENSIONS of the existing single Tier 2
LLM call (same prompt, same schema, new `kind` values) -- not a new
LLM call, new engine, or new call site. Whether either is worth
building at all is the open question this document exists to surface,
not answer.

---

# Why This Needs Definition Before It Needs Code

Tier 2 v1's own hardest-won discipline (see `tier2_prompt.py`'s laws)
is restraint: an empty `tier2` list is the common, correct case, and
law 5 exists specifically to stop Tier 2 from ever characterizing the
person ("independent," "avoidant," "values stability") rather than
describing their situation. "Values-level synthesis" is the more
dangerous of the two ideas named here precisely because it sits right
next to that line -- a values-level statement that INVENTS a value the
person never stated (e.g. inferring "you value autonomy" from behavior
alone) is exactly the kind of trait-labeling law 5 was written to
prevent. Any version of this built without a concrete guard against
that risk would regress a principle this project has already paid
real design cost to establish.

---

# Proposed Definition 1 — Declarative Uncertainty

## Purpose

Tier 1 already renders every open `Unknown` as its own question-shaped
statement (`kind="uncertainty"`, e.g. "Has the user discussed this move
with their manager?"). When several such Unknowns (or an Unknown plus
an open Decision/Goal) share a common root, today's Tier 1 shows them
as separate, disconnected questions. Tier 2 v1's existing `synthesis`
kind CAN connect them, but its own law 3 ("describe the situation, not
the individual facts") pulls toward a situational sentence, not
specifically toward naming the unresolved core.

Declarative uncertainty would be a Tier 2 statement that names the
SPECIFIC boundary of what's still unknown, as a stated fact, when two
or more Unknown/open-thread candidates share it -- distinct from
restating each question, and distinct from a general situational
observation.

## Worked Example

Candidates:

* Unknown: "Has the user discussed this move with their manager?"
* Unknown: "Does the user have another offer lined up?"
* Decision (open): "Take the new role"

Existing Tier 2 `synthesis` might produce:

> You're weighing a new role without having raised it with your manager yet.

Proposed `declarative_uncertainty` would instead produce:

> Whether this decision is even yours to make freely -- versus one your manager or another offer could still change -- isn't settled yet.

The difference: `synthesis` describes the situation; `declarative_uncertainty`
names the SPECIFIC thing that remains unresolved, as its own claim, not
folded into a situational sentence.

## Proposed Guard

Same grounding discipline as every existing Tier 2 statement
(`MIN_GROUNDING_ITEMS`, engine-level `grounding_item_ids` filtering) --
a `declarative_uncertainty` statement must cite at least two real
candidate ids, at least one of which is an Unknown or open thread item.
Never phrased as a question (that's what Tier 1's own `uncertainty` kind
already does) -- always a declarative sentence naming the boundary of
what's unknown.

---

# Proposed Definition 2 — Values-Level Synthesis

## Purpose

Connect two or more candidates (typically goals, decisions, or
assumptions) into an observation about a TENSION the person appears to
be weighing -- e.g., between stability and change, obligation and
autonomy -- when their own words already name both sides.

## Worked Example

Candidates:

* Goal: "Move into product management"
* Assumption: "Leaving my current team would disappoint my manager"

Proposed `values_synthesis`:

> Moving forward on this means weighing what you want against not letting your manager down.

## The Hard Constraint

**A `values_synthesis` statement may only ever connect two things the
person's OWN candidate text already states** -- it may never introduce
an abstract value word ("autonomy," "security," "loyalty") that doesn't
already appear, in substance, in the cited candidates themselves. This
is the direct, concrete guard against violating law 5: this is
NAMING A TENSION BETWEEN TWO STATED THINGS, never DIAGNOSING WHAT THE
PERSON VALUES AS A TRAIT. "You seem to value stability" (a trait
label) is disallowed under this constraint; "wanting to move forward
here means setting aside not disappointing your manager" (a tension
between two things they already said) is not.

This constraint is the single most important thing a founder review
of this document should scrutinize -- if it can't be enforced reliably
by an LLM (prompt wording is not a hard guarantee the way engine-level
grounding filtering is), this definition may not be safely buildable
at all, and should be rejected rather than shipped with a weak guard.

---

# What This Does NOT Propose

* A new LLM call, new engine module, or new call site -- both proposed
  kinds would extend Tier 2 v1's existing single call
  (`run_tier2_synthesis`), same schema (`Tier2Batch`), same
  `should_recompute_tier2` gating (narrowed 2026-07-19 by backlog #295 --
  see engine/decisions.md -- to thread-item status changes; these new
  kinds don't change what triggers recomputation, only what a
  recomputation can produce).
* Frontend changes -- `Understanding.svelte` currently renders all of
  `tier2` under one flat list with no kind differentiation; whether a
  person should see these as visually distinct from `synthesis`
  statements is a separate, unresolved UX question this document
  doesn't answer.
* A commitment to build either kind -- see Open Questions below.

---

# Open Questions

## Should either of these actually be built?

Tier 2 v1 has not yet had a dedicated calibration round measuring
whether its EXISTING `synthesis` kind is even hitting the right
frequency/quality bar in production (see backlog #290's own live
calibration, which fixed an over-synthesis problem). Adding two more
kinds before that existing kind is well-understood risks compounding
an uncalibrated system rather than fixing one.

## Is `values_synthesis`'s hard constraint enforceable?

Prompt wording is not a hard guarantee. Unlike grounding
(`grounding_item_ids` filtered against real candidate ids, mechanically
enforced), there is no equivalent mechanical check today for "did this
statement invent a value word not present in the cited candidates."
One option: a post-hoc lexical check (does the statement's language
overlap with the cited candidates' own text above some threshold) --
itself a new, uncalibrated mechanism. This needs real design work
before implementation, not just a prompt law.

## One new kind, or two?

`declarative_uncertainty` is the lower-risk of the two (no values-label
risk, closer to Tier 1's existing `uncertainty` kind's own spirit).
`values_synthesis` is higher-risk and higher-reward. These could be
approved/rejected independently rather than as a package.

## Cost

Both extend the existing single Tier 2 call rather than adding a new
one, so no new LLM call is introduced -- but a richer prompt (more laws,
more worked examples) plus a wider schema (`Literal["synthesis",
"declarative_uncertainty", "values_synthesis"]`) is a real, if small,
per-call cost increase, worth weighing against CLAUDE.md's free-tier
rate-limit discussion even without a new call.

---

# Success Criteria

If built, either kind should:

* Preserve Tier 2 v1's existing rarity (most turns still produce
  nothing) -- these are additional POSSIBLE outputs of the same gated
  call, not a reason to recompute more often.
* Never require its own new grounding mechanism weaker than the
  existing `MIN_GROUNDING_ITEMS` filter.
* For `values_synthesis` specifically: never produce a statement a
  careful reviewer would describe as "labeling what kind of person I
  am" rather than "naming a tension I already described in my own
  words."

# Recommendation

Given the open enforceability question for `values_synthesis` and the
lack of a calibration round for Tier 2 v1's existing kind, this
document recommends: review `declarative_uncertainty` as a candidate
for a future round (lower risk, clearer worked definition), and treat
`values_synthesis` as needing further design work on its enforcement
mechanism before it's buildable at all -- not a rejection, but not
ready either.
