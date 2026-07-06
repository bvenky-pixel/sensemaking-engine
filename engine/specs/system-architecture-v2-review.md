# Confidant System Architecture v2 — Design Review

Status: REVIEW ONLY. Nothing in this document has been implemented.
No code, schema, or prompt in the Sensemaking Engine (v1, frozen) is
touched by this review. This mirrors how the Judgment v2 calibration
review was handled earlier on this branch: analysis and recommendations
first, implementation only after explicit confirmation.

**Revision note (post-review discussion)**: Section 1's original
recommendation to extend Planner so Executor could "never reason" about
a Clarity Brief was reviewed against direct feedback and corrected --
see the "Clarity Briefs are formatting, not planning" callout in Section
1. The original text is struck through and replaced rather than quietly
edited, so the correction itself is part of the record.

## Context

The Sensemaking Engine v1 is frozen:

```
Interpretation -> WorldState -> Judgment -> Planner -> Response Generator
```

It answers one question: *"Given everything the user has shared, what is
the most faithful understanding of their situation, and how should that
understanding be expressed?"* Each of its five processes has exactly one
responsibility and reasons about the user's world.

System Architecture v2 is proposed to operate, observe, improve, and
externalize the Sensemaking Engine — it reasons about the operation of
Confidant itself, never about the user's world. The proposal is four
processes:

1. **Orchestrator** — "How should this interaction be processed?"
2. **Instrumentation** — "How did Confidant perform?"
3. **Learning** — "What should Confidant learn over time?"
4. **Executor** — "How should completed sensemaking be materialized?"

The standard applied throughout this review, per explicit instruction:
*a new component should exist only if it answers a system-level question
that none of the existing components should answer.* Infrastructure
concerns (auth, databases, networking, deployment, APIs, caching,
monitoring platforms) are deliberately out of scope, as are speculative
AI modules that don't answer a genuinely new system-level question.

---

## 1. Are these four processes sufficient?

Close, but two open questions should be resolved first — by tightening
the four proposed processes, not by adding a fifth.

**The Executor / Response Generator boundary is underspecified.**
Response Generator already "generates the user-facing artifact" for a
conversational turn. Executor's stated job is also "generating
user-facing artifacts." As written, these overlap. There is a real,
non-redundant distinction available — Response Generator produces *this
turn's reply*; Executor produces artifacts consumed *outside* the live
turn (a Clarity Brief, an email draft, a reminder) — but the current
wording doesn't say that explicitly, so a builder could easily let the
two blur or duplicate effort.

**Recommendation**: tighten Executor's one-sentence contract to:
*"materializes completed sensemaking into artifacts other than the live
conversational reply."* That one clause resolves the overlap without
adding a component.

~~**Executor's "never performs reasoning" claim doesn't hold yet,
structurally.** For Response Generator to never reason, Planner must
already have decided the complete plan (objective, strategy,
constraints) — Response Generator only renders it. For Executor to
genuinely never reason about a Clarity Brief, *something* upstream has
to have already decided what belongs in that brief and what it's trying
to accomplish. Recommendation: extend Planner to be able to produce a
plan for non-conversational artifacts too, not just conversational
replies.**~~ **Corrected below.**

### Clarity Briefs are formatting, not planning (correction)

The recommendation above was wrong, for a reason worth stating precisely
rather than just reversing the conclusion. It conflated two different
things: *selecting content per instance* (a runtime judgment call) and
*applying a fixed template decided once at design time* (not a runtime
decision at all).

A Clarity Brief is not a new plan — it is a different rendering of the
same cognitive state Planner already produced. Planner has already
answered what the objective is, what blocks progress, and what matters
next. A Clarity Brief is simply an organized presentation of:

- Situation ← WorldState
- Key insights ← Judgment
- Current direction ← Planner
- Remaining unknowns ← WorldState/Judgment
- Decisions ← WorldState

Executor doesn't need Planner to produce an "artifact plan." It needs a
*template* — authored once, applied uniformly every time, the same way
Response Generator's own prompt is authored once and applied faithfully
every turn. That template is design-time work, not a runtime reasoning
act, so Executor rendering it is genuinely "expression, not cognition,"
exactly like Response Generator: the only judgment involved (what a
Clarity Brief structurally contains) was made once, not freshly decided
per conversation. An empty section (e.g., no remaining unknowns) is a
structural consequence of an upstream field being empty, not a fresh
decision either — the same "sparse by default" pattern already used
everywhere else in this pipeline.

**The corrected test, more general than the original recommendation**:
does the artifact require information or decisions that don't already
exist in WorldState + Judgment + Planner, or does it just reorganize
what's already there? A Clarity Brief reorganizes — no Planner extension
needed. A hypothetical "generate a 90-day action plan" artifact would
need genuinely NEW decisions (sequencing, milestones, timeframes) that
none of the three cognitive layers currently produce — *that* would
legitimately need an upstream extension. Only extend Planner when an
artifact actually clears that bar; a Clarity Brief does not.

With this correction, Executor's "never reasons" claim holds for any
artifact governed by a fixed, uniformly-applied template. Four processes
remain sufficient. See Section 5 for candidate fifth-component ideas
considered and rejected.

---

## 2. Does each process have exactly one responsibility?

**Instrumentation, Learning: yes, cleanly.** Both pass the
one-system-level-question test well. Instrumentation's long
responsibility list (tracing, tokens, cost, schema-validation metrics,
evaluation logging, benchmarking, experiment instrumentation) all reduce
to one question — *what happened* — and none of it decides anything.
This matches what's already built: `src/instrumentation/usage.py`'s
`UsageTracker`/`LLMUsage` genuinely just records; it never influences a
cognitive call.

**Orchestrator: coherent, but "selecting models" and "managing retries"
need an altitude clarification, not a split.** The codebase already has
provider selection and retry-on-failure living in `src/llm/providers.py`
(`resolve_provider_chain`/`call_provider`, shared by every cognitive
layer) — that's low-level LLM-client plumbing, not a system-level "how
should this interaction be processed" decision. If Orchestrator's
"selecting models" / "managing retries" means the *same* thing
(HTTP-level retry, provider fallback on a single call), it's redundant
with what already exists and arguably doesn't belong at the
architecture-process level at all — it's a shared library, not a
process. If instead it means interaction-level *policy* ("this turn
looks high-stakes, use a stronger model tier" or "Judgment failed across
every provider — abort this stage vs. retry the whole stage vs. fall
back to a canned response"), that's a genuinely different,
correctly-Orchestrator-level decision.

**Recommendation**: state explicitly that Orchestrator owns stage-level
and policy-level decisions; call-level HTTP retry/fallback stays exactly
where it is today, in the shared provider layer, underneath all four
system processes and all five sensemaking processes alike.

**Executor**: single responsibility holds once its contract is
explicitly template-driven (see Section 1's correction) — a fixed,
design-time template per artifact type, applied uniformly, with no
per-instance content judgment at runtime.

---

## 3. Are any responsibilities assigned to the wrong component?

One concrete risk: **Orchestrator's "skipping unnecessary computation"
could quietly become a reasoning job.** A mechanical skip criterion —
"Interpretation produced no new Facts/Claims/Goals/Unknowns beyond what's
already in WorldState, so reuse the last Judgment" — is a legitimate,
purely structural check Orchestrator can own without reasoning about
meaning. But the moment the skip criterion becomes "does this change
actually *matter*," that's a judgment about the user's world, which is
Judgment's job, not Orchestrator's.

**Recommendation**: state explicitly in the spec that Orchestrator's
skip/route logic is restricted to mechanical/structural triggers over
already-produced sensemaking artifacts, never semantic evaluation of
them.

Everything else reviewed is correctly assigned.

---

## 4. Is anything here actually part of the Sensemaking Engine?

No, once Section 1's correction is applied. A fixed, design-time
template (Clarity Brief: Situation/Insights/Direction/Unknowns/Decisions,
each mapped to a specific upstream field) is not sensemaking work — it's
the same kind of authored-once contract Response Generator's own prompt
already is. Sensemaking Engine involvement is only required for an
artifact that needs genuinely NEW decisions beyond reorganizing
WorldState/Judgment/Planner content (the 90-day-action-plan example in
Section 1) — no such artifact is in scope today.

---

## 5. Missing system-level responsibilities — genuine gaps vs. already covered

Several candidates were considered and rejected, in the interest of
honesty about what's actually missing versus what's already covered:

- **A safety/output-gating checkpoint** ("should this generated Response
  actually be released?") — does not need a new component. It's
  naturally an extension of Orchestrator's existing "coordinating
  execution" responsibility (a coordination decision about whether to
  proceed, retry, or suppress a stage's output), not a new system-level
  question.
- **Feedback/correction ingestion** (the user pushes back or corrects
  something) — not a gap. A correction is just more conversation
  content; it flows through Interpretation like anything else. No new
  component needed.
- **Cross-session state loading/retrieval** — adjacent to Learning's
  "updating long-term knowledge," but the actual mechanics
  (loading/storing state) are the infrastructure concerns explicitly
  excluded from this review. The *decision* of what's durable enough to
  retain belongs to Learning; retrieval is infra.
- **Evaluation as a standing fifth process** — seriously considered,
  since the codebase already has a real `src/evaluation/` package
  (baseline comparisons, groundedness/constraint-violation heuristic
  scoring) that does more than passive measurement — it produces
  comparative judgments. This does not clear the stated bar, though. It
  is an occasional, often-manual analysis activity that *consumes*
  Instrumentation's recorded data; it doesn't run continuously the way
  Orchestrator/Instrumentation/Executor do, and its question ("which
  condition performed better") is a specific application of "what
  happened," not a distinct standing system-level question.

  **Recommendation**: fold this explicitly under Instrumentation's remit
  (as the draft already does via "evaluation logging, benchmarking
  support") but add one clarifying sentence: Instrumentation produces
  the raw comparative material; drawing a conclusion from it is either a
  human call today or Learning's job once Learning is real. Do not build
  Evaluation as a fifth component.

### A sequencing caution on Learning (not a structural objection)

Learning is the only one of the four with no existing code behind it at
all, and it's also the one most tempting to over-build speculatively —
"identify durable patterns" and "update long-term knowledge" are exactly
the kind of capability this project's own history (documented across
`engine/decisions.md`) has repeatedly warned against building ahead of
real evidence (see: Judgment's "resist tuning until Planner exists and
consumes it," Planner's deliberate restraint at n=1/n=2 real samples).

**Recommendation**: let Learning exist in the v2 architecture as a named
slot with a one-sentence contract now, but stay unimplemented (or
manual-review-only) until Instrumentation has actually accumulated
enough real operational history to learn *from*. Building Learning's
logic today, before Confidant has run at any real volume, would be
inventing capability the evidence doesn't yet support — the same mistake
this codebase has corrected for repeatedly elsewhere.

**One more precision worth adding to Learning's contract**:
"updating long-term knowledge" should not mean writing directly into a
live WorldState. WorldState is a per-conversation Sensemaking Engine
artifact that Judgment reasons over; if Learning reaches in and edits it,
Learning has become a de facto sensemaking process, which contradicts the
architecture's own framing that the System Architecture "does not reason
about the user's world." Learning's outputs (calibration adjustments,
cross-conversation memory, whatever "durable knowledge" turns out to
mean) should feed *into* a future Sensemaking Engine run as external
input/config — Interpretation or a WorldState-seeding step decides what
that means for a given conversation, not Learning directly.

---

## Summary of recommendations (post-correction)

Four components, kept as four, with three precision edits rather than
new architecture:

1. Tighten Executor's contract: *"materializes completed sensemaking
   into persistent artifacts or external actions"* — explicitly distinct
   from Response Generator, which *"materializes sensemaking into the
   next conversational turn."*
2. Executor's artifacts (Clarity Briefs, etc.) are governed by a fixed,
   design-time template mapping WorldState/Judgment/Planner content into
   sections — authored once, applied uniformly, no per-instance runtime
   judgment. This is what keeps Executor's "never reasons" claim true,
   without any Planner extension. Only extend Planner (inside the
   Sensemaking Engine) if a future artifact needs genuinely NEW decisions
   the three cognitive layers don't already produce (e.g. a 90-day action
   plan needing sequencing/milestones) — no such artifact is in scope now.
3. State explicitly that Orchestrator's model-selection/retry ownership
   is interaction-level policy, not the call-level HTTP plumbing already
   living in the shared provider layer (`src/llm/providers.py`) — and
   that its skip/route logic is restricted to structural triggers, never
   semantic ones.

Plus one sequencing recommendation:

4. Build Learning's slot and contract now, but leave its logic
   unimplemented until there's real operational history to learn from.
   Do not let Learning write directly into WorldState.

And one explicit non-addition:

5. Do not add Evaluation as a fifth standing component — fold it into
   Instrumentation's existing remit, with the human/Learning boundary on
   drawing conclusions stated explicitly.

Nothing in this document has been implemented. Next step, if this
direction is approved: write the actual System Architecture v2
specification (mirroring how `engine/specs/planner-specification-v1.md`
and `engine/specs/response-generator-specification-v1.md` were written),
incorporating these recommendations before any code exists.
