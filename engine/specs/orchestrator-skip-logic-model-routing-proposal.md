# Orchestrator Skip-Logic / Model-Routing — Design Proposal

**Status:** DISCUSSION DRAFT (2026-07-19, backlog #238, see
engine/decisions.md "Orchestrator: skip-logic/model-routing provisional
criteria proposed"). Written at the founder's explicit direction --
`src/orchestrator/engine.py`'s own module docstring names two deferred
non-goals ("skip unnecessary computation," "select models as
interaction-level policy"), each deferred for a concrete, still-true
reason (no evidence stages often produce nothing new; no defined
"higher-stakes" criterion anywhere in the codebase). Asked whether to
close both as still-correctly-gated or define provisional criteria now
regardless of the missing evidence -- the founder chose the latter.
This document is that first attempt, for review before anything is
built.

This is a design document, not a schema specification.

No prompt, schema, or code changes are implied by this document.

---

# Executive Summary

The two non-goals turn out to have very different shapes once traced
through the actual pipeline:

- **Skip-logic**, in the literal sense the module docstring's own
  example describes ("skip Judgment if Interpretation produced nothing
  new"), does not appear to be a safe optimization for THIS pipeline's
  shape at all -- see "Why Skip-Logic Doesn't Work As Described" below.
  This document recommends closing it, not provisionally defining it.
- **Model-routing** does have a viable, already-available mechanical
  signal (Interpretation's own `urgency` field) -- but routing to a
  genuinely STRONGER model requires naming a specific target model,
  which is a real cost/approval decision under CLAUDE.md's standing
  policy, not something this document can settle on its own.

---

# Why Skip-Logic Doesn't Work As Described

`src/orchestrator/engine.py::run_turn` is a strict sequential chain:
Interpretation -> WorldState update -> Judgment -> Planner -> Response.
Each later stage consumes the previous stage's committed output, and
**Response is what generates the actual reply the person sees this
turn.** "Skip Judgment if Interpretation produced nothing new," taken
literally, cascades: skipping Judgment means Planner has no Judgment to
plan from, which means Response has nothing to respond from -- the
person sends a message and gets no reply at all. That isn't an
optimization; it's a correctness regression far worse than the latency
it would save.

The only way "skip" could mean something safe is REUSE, not omission --
short-circuiting to the PREVIOUS turn's Judgment/Planner/Response bundle
unchanged when nothing new arrived, so the person still gets *a* reply,
just not a freshly reasoned one. That is a materially different (and
riskier) feature than "skip computation": it means knowingly serving a
stale assessment when the person's latest message might still deserve
fresh attention even if WorldState's structured extraction found
nothing new in it (e.g. "yeah exactly" or a one-word emotional reaction
carries real conversational weight that a structural WorldState diff
would never capture -- Interpretation itself already extracts more than
just knowledge items, and Judgment/Response read more than WorldState's
literal new-item count).

**Recommendation: close skip-logic, don't provisionally define it.**
Not because no evidence exists (the original, weaker reason) but
because the literal mechanism the non-goal describes appears
architecturally unsafe for a pipeline where every stage after
Interpretation exists to produce that turn's actual reply. If a real
version of this is ever worth pursuing, it should be scoped as "turn
reuse under explicit staleness disclosure" -- a different, larger
feature than "skip a stage" -- not something to back into via a
provisional mechanical trigger.

---

# Model-Routing: A Provisional Mechanical Signal

## The available signal

Interpretation already produces `urgency: Literal["low", "medium",
"high"]` every turn, before Judgment/Planner/Response run -- a
genuinely mechanical, already-extracted field, not something requiring
new extraction work. This is the most defensible candidate for a
"higher-stakes turn" trigger: no guessing required, it already exists,
and it's available at exactly the point (after Interpretation, before
the three downstream calls) where a routing decision would need to be
made.

**Provisional, explicitly first-cut criterion**: `interp.urgency ==
"high"` marks a turn as higher-stakes for Judgment/Planner/Response
model selection. Same "honest first guess, not empirically calibrated"
framing as `MIN_EVIDENCE`/`TIER2_RECENCY_WINDOW_TURNS`/every other
uncalibrated threshold in this codebase -- not validated against real
urgency-vs-outcome data, because that data doesn't exist yet.

## What routing on it would actually require

`src/llm/providers.py::_resolve_model_chain(component)` resolves a
model chain purely from the component name (or a global
`OPENROUTER_MODEL` override) -- there is no per-call, per-turn
parameter today. Threading a stakes signal through would mean:

1. `run_turn` (`src/orchestrator/engine.py`) computing `high_stakes =
   interp.urgency == "high"` after Interpretation returns.
2. A new optional parameter (e.g. `model_override: Optional[str]`)
   added to `run_judgment`/`run_planner`/`run_response_generator`,
   threaded down into `call_provider`, bypassing
   `_resolve_model_chain`'s component-name lookup when set.
3. Orchestrator passing that override only when `high_stakes` is true.

This is real, multi-file plumbing (three engine.py files plus
providers.py), not a one-line change -- but it's mechanical, not a
design fork in itself.

## The part this document cannot settle

**What model to route TO.** This project's per-component model chains
(`_DEFAULT_COMPONENT_MODELS`) were deliberately rebalanced toward the
CHEAPEST viable models for each component (`qwen/qwen3-32b`,
`google/gemini-2.5-flash-lite`, `deepseek/deepseek-chat`) -- there is no
"next tier up" already chosen or approved. Naming a stronger target
model is exactly the kind of default-model change CLAUDE.md's standing
policy requires asking about explicitly (non-free-tier models require
fresh permission before being used, even for a conditional per-turn
case, not just as a blanket default). This document deliberately does
NOT propose a specific target model -- that choice, plus its real
per-high-stakes-turn cost, needs its own explicit founder decision
before any of the plumbing above gets built.

---

# What This Does NOT Propose

* Building skip-logic in any form -- see recommendation above.
* A specific target model for the "stronger tier" -- see above.
* Any actual routing behavior change -- `interp.urgency` is not
  currently read by Orchestrator for anything; this document only
  proposes it AS the criterion, contingent on a separate decision about
  what to route to.

---

# Open Questions

## Is `urgency` reliable enough to route real cost decisions on?

`urgency` has never had a dedicated calibration round (unlike
`has_risk_signal`/`has_assumption`/other boolean-gated fields, which
went through several rounds before being trusted). Routing real spend
on an uncalibrated field carries a different risk than routing a UI
affordance would.

## Should "high stakes" also consider Judgment's own signals?

Judgment's `has_risk_signal`/`risk_significance` are richer stakes
signals than Interpretation's `urgency` alone -- but they're only
available AFTER Judgment has already run, so they could inform
Planner/Response's routing but never Judgment's own. A two-tier scheme
(urgency gates Judgment; urgency OR risk_significance gates
Planner/Response) is a plausible refinement, not proposed concretely
here.

## Cost

Routing even a small fraction of turns to a stronger model changes this
project's real per-turn cost profile in a way the current per-component
rebalance was explicitly optimized against. Any target-model decision
should come with an estimate of what fraction of real turns would
plausibly hit `urgency == "high"`, once that's observable from
production data -- which doesn't exist yet.

# Recommendation

Close skip-logic as architecturally unsound in its literal form.
Table model-routing's PLUMBING as scoped-but-not-started (the mechanism
above is buildable on request), contingent on the founder naming a
specific target model and accepting its real cost -- a separate
decision from this document's own scope.
