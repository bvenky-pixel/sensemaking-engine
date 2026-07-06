Confidant System Architecture v2 Specification

Status: SPEC ONLY. Nothing in this document has been implemented.
Written from the original System Architecture v2 proposal plus
`engine/specs/system-architecture-v2-review.md`'s review and its
post-review correction (all five review points agreed). Same discipline
as every Sensemaking Engine component: spec first, implementation only
after this is confirmed.

---

Purpose

The System Architecture exists to operate, observe, improve, and
externalize the Sensemaking Engine.

Unlike the Sensemaking Engine, the System Architecture does not reason
about the user's world.

It reasons about the operation of Confidant itself.

---

Relationship to the Sensemaking Engine

The Sensemaking Engine (v1, frozen) is:

Interpretation → WorldState → Judgment → Planner → Response Generator

It answers one question: given everything the user has shared, what is
the most faithful understanding of their situation, and how should that
understanding be expressed. Every process in it reasons about the user's
world.

The System Architecture is four processes:

1. Orchestrator
2. Instrumentation
3. Learning
4. Executor

None of these four processes reasons about the user's world. Each
reasons about how Confidant itself is running, performing, improving, or
producing artifacts. This boundary is absolute: if a proposed
responsibility requires judging what something MEANS to the user's
situation, it belongs to the Sensemaking Engine, not here, no matter
which of the four processes seems like a natural place to put it.

---

Governing Test for This Architecture

A new component exists only if it answers a system-level question that
none of the existing components should answer.

This test was applied during design (see the review document) and ruled
out a fifth "Evaluation" component and several other candidates.
Applying it again in the future is the correct process for considering
any fifth component -- not an assumption that four is permanent by
default, but a bar every future addition must clear.

---

## 1. Orchestrator

Question answered:

«How should this interaction be processed?»

Responsibilities:

- Deciding which Sensemaking Engine processes execute for a given
  interaction
- Routing requests
- Selecting models -- as interaction-level POLICY (e.g. "this interaction
  warrants a stronger model tier"), not call-level provider selection
- Skipping unnecessary computation
- Coordinating execution across the five Sensemaking Engine processes
- Managing retries and latency -- at the STAGE level (e.g. "Judgment
  failed across every configured provider: retry the stage, skip to a
  fallback Response, or abort the turn"), not the call level

Explicit scope boundary: call-level HTTP retry, provider fallback, and
model-selection mechanics already exist as shared plumbing beneath every
Sensemaking Engine process (`src/llm/providers.py`'s
`resolve_provider_chain`/`call_provider`). Orchestrator does not
duplicate or re-own that layer. Orchestrator's model-selection and
retry responsibilities operate one level up: deciding INTERACTION-LEVEL
policy and STAGE-LEVEL recovery, not re-implementing or second-guessing
the call-level plumbing underneath.

Explicit scope boundary on skipping computation: skip/route decisions
are restricted to MECHANICAL, STRUCTURAL triggers over already-produced
Sensemaking Engine artifacts (e.g. "Interpretation produced no new Facts,
Claims, Goals, or Unknowns beyond what's already in WorldState, so reuse
the last Judgment"). The moment a skip decision requires judging whether
a change actually MATTERS to the user's situation, that decision has
become Judgment's job, not Orchestrator's, and must not be made here.

Non-Goals: Orchestrator must never perform user reasoning, judge
semantic importance, or decide what a piece of content means. It decides
sequencing and resourcing, nothing else.

---

## 2. Instrumentation

Question answered:

«How did Confidant perform?»

Responsibilities:

- Execution tracing
- Latency measurement
- Token accounting
- Cost tracking
- Model usage logging
- Schema validation metrics (counting/recording validation outcomes --
  the validation itself stays owned by each Sensemaking Engine process,
  per its own "typed over prompted" discipline; Instrumentation only
  records that it happened)
- Reliability metrics
- Evaluation logging
- Benchmarking support
- Experiment instrumentation

Explicit scope boundary: Instrumentation produces raw, recorded material
about what happened. It does not draw conclusions from that material.
"Evaluation logging" and "benchmarking support" mean capturing the
comparative data (e.g. which condition was run, what its measured
outputs were) -- deciding WHICH condition performed better, or what
should change as a result, is either a human judgment call today, or
Learning's responsibility once Learning is implemented. Instrumentation
never makes that call itself.

Non-Goals: Instrumentation must never change cognition, influence a
Sensemaking Engine call's behavior, or decide what the recorded data
means. It observes; it does not evaluate or act.

---

## 3. Learning

Question answered:

«What should Confidant learn over time?»

Responsibilities:

- Identifying durable patterns across many conversations and many
  Instrumentation records
- Producing calibration adjustments or durable, cross-conversation
  knowledge
- Improving future sensemaking
- Operating asynchronously, never inside a live conversation turn

Explicit scope boundary: Learning must never write directly into a live
WorldState. WorldState is a per-conversation Sensemaking Engine artifact
that Judgment reasons over; if Learning reached in and edited it directly,
Learning would become a de facto sensemaking process, contradicting the
System Architecture's own boundary of never reasoning about the user's
world. Learning's outputs (calibration adjustments, cross-conversation
memory, or whatever "durable knowledge" concretely turns out to mean)
feed INTO a future Sensemaking Engine run as external input or
configuration. A future Interpretation call, or a future WorldState-
seeding step, decides what that input means for a given conversation --
Learning itself never makes that decision.

Implementation status: Learning exists in this architecture as a named
process with this one-sentence contract, deliberately NOT implemented
yet. Building "identify durable patterns" logic before Confidant has run
at any real volume would invent capability the evidence doesn't support
-- the same mistake this codebase has corrected for repeatedly elsewhere
(Interpretation's multi-round hardening process, Judgment's "resist
tuning until Planner exists," Planner's own restraint at n=1/n=2 real
samples). Learning should remain a reserved slot -- named, scoped, and
bounded by the WorldState non-goal above -- until Instrumentation has
accumulated enough real operational history to learn FROM. Implementing
Learning's actual logic requires deliberately reopening this spec, the
same discipline applied to every other component.

Non-Goals: Learning must never participate in real-time conversation,
never write to a live WorldState, and never invent a durable pattern
that isn't backed by real accumulated Instrumentation data.

---

## 4. Executor

Question answered:

«How should completed sensemaking be materialized?»

Responsibilities:

- Generating persistent artifacts derived from a completed Sensemaking
  Engine pass (e.g. Clarity Briefs)
- Supporting future external actions (email drafts, reminders,
  documents, etc.)

Explicit scope boundary, distinguishing Executor from Response
Generator: Response Generator materializes sensemaking into the NEXT
CONVERSATIONAL TURN. Executor materializes completed sensemaking into
PERSISTENT ARTIFACTS OR EXTERNAL ACTIONS -- anything consumed outside the
live conversational turn. These are mutually exclusive by definition;
Executor is never a second path to producing the reply the user reads
next.

Explicit scope boundary on reasoning: every Executor artifact is
governed by a FIXED, DESIGN-TIME TEMPLATE mapping WorldState, Judgment,
and Planner content into the artifact's sections -- authored once,
applied uniformly every time, the same way Response Generator's own
prompt is authored once and applied faithfully every turn. For example,
a Clarity Brief's template:

- Situation ← WorldState
- Key insights ← Judgment
- Current direction ← Planner
- Remaining unknowns ← WorldState / Judgment
- Decisions ← WorldState

The only judgment involved in this template (what a Clarity Brief
structurally contains) is made once, at design time, not freshly per
conversation. An empty section, where the mapped upstream field is
empty, is a structural consequence of that field being empty -- not a
fresh decision -- the same "sparse by default" pattern already used
throughout the Sensemaking Engine. This is what keeps Executor's
rendering "expression, not cognition," exactly like Response Generator,
without requiring any change to Planner.

Governing test for when an artifact WOULD require a Sensemaking Engine
change: does the artifact need information or decisions that don't
already exist in WorldState + Judgment + Planner, or does it just
reorganize what's already there? A Clarity Brief reorganizes -- no
Sensemaking Engine change needed. A hypothetical artifact requiring
genuinely NEW decisions (e.g. a "90-day action plan" needing sequencing,
milestones, and timeframes none of the three cognitive layers currently
produce) would need Planner extended first, inside the Sensemaking
Engine, before Executor could render it -- because deciding what matters
is reasoning about the user's world, which stays a Sensemaking Engine
responsibility regardless of which system process ultimately triggers
the need for it. No artifact requiring that kind of extension is in
scope today.

Non-Goals: Executor must never perform reasoning, never decide what
belongs in an artifact beyond its fixed template, never invent content
beyond what WorldState/Judgment/Planner already contain, and never
produce the live conversational reply (Response Generator's exclusive
responsibility).

---

Relationship Between the Four Processes

Orchestrator decides how an interaction is processed -- which
Sensemaking Engine processes run, in what order, with what recovery
policy.

Instrumentation observes every process, in the Sensemaking Engine and in
the System Architecture alike, recording what happened without
influencing it.

Learning consumes Instrumentation's accumulated record, asynchronously
and outside any live conversation, to decide what should change about
future operation -- without ever reaching into a live WorldState to make
that change directly.

Executor consumes a completed Sensemaking Engine pass (WorldState,
Judgment, Planner) through a fixed, pre-authored template, to produce
artifacts and actions that exist outside the live conversational turn --
distinct from, and never a substitute for, Response Generator.

None of the four reasons about the user's world. All four reason about
how Confidant itself runs, is measured, improves, and produces things
beyond the conversation itself.

---

Non-Goals (System Architecture as a whole)

The System Architecture must never:

- Reason about the user's world (that is the Sensemaking Engine's
  exclusive responsibility)
- Let Orchestrator judge semantic importance or meaning
- Let Instrumentation draw conclusions from what it records
- Let Learning write directly into a live WorldState
- Let Executor decide artifact content beyond its fixed template, or
  duplicate Response Generator's role
- Add a fifth standing process without first applying the Governing
  Test above and finding a genuine gap

---

Design Philosophy Summary

The Sensemaking Engine understands the user's world and gives that
understanding a voice.

The System Architecture keeps that engine running, honestly measured,
improving over time, and able to produce more than just the next reply.

It does this without ever reasoning about the user's world itself --
every process here answers a question about Confidant's own operation,
never a question about the user's situation.

Four processes, four questions, no overlap:

- Orchestrator: how should this interaction be processed?
- Instrumentation: how did Confidant perform?
- Learning: what should Confidant learn over time?
- Executor: how should completed sensemaking be materialized?

A fifth process is added only when a genuine fifth question emerges that
none of these four should answer -- not before.
