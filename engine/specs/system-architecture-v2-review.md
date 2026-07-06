# Confidant System Architecture v2 — Design Review

Status: REVIEW ONLY. Nothing in this document has been implemented.
No code, schema, or prompt in the Sensemaking Engine (v1, frozen) is
touched by this review. This mirrors how the Judgment v2 calibration
review was handled earlier on this branch: analysis and recommendations
first, implementation only after explicit confirmation.

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

**Executor's "never performs reasoning" claim doesn't hold yet,
structurally.** For Response Generator to never reason, Planner must
already have decided the complete plan (objective, strategy,
constraints) — Response Generator only renders it. For Executor to
genuinely never reason about a Clarity Brief, *something* upstream has
to have already decided what belongs in that brief and what it's trying
to accomplish. Today, Planner's contract (v1, frozen) is scoped to
conversational objectives (`primary_objective`, `conversational_strategy`,
`desired_outcome`, ...) — it has no notion of "produce an artifact-shaped
objective." Until that exists, Executor either quietly performs its own
selection/prioritization (reasoning about the user's world — a
Sensemaking Engine job, violating its own non-goal) or it has nothing to
render.

**This is not a missing fifth component — it is a gap in Planner's
remit.** Recommendation: extend Planner (still inside the Sensemaking
Engine, since deciding what matters is reasoning about the user's world)
to be able to produce a plan for non-conversational artifacts too, not
just conversational replies. Then Executor stays a pure renderer, exactly
mirroring how Response Generator relates to Planner today.

With those two clarifications, four is sufficient. See Section 5 for
candidate fifth-component ideas considered and rejected.

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

**Executor**: single responsibility is real once the Planner-extension
above is resolved; until then it risks a second, hidden responsibility
(silently deciding artifact content).

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

Only the one piece flagged in Section 1: whatever reasoning decides
*what a Clarity Brief or artifact should contain and accomplish* is
Sensemaking Engine work (specifically, an extension of Planner), even
though it's triggered by Executor's system-level need to produce that
artifact. The materialization itself (formatting, structuring,
rendering into the target medium) correctly stays with Executor.

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

## Summary of recommendations

Four components, kept as four, with three precision edits rather than
new architecture:

1. Tighten Executor's contract to explicitly exclude the live
   conversational reply (Response Generator's job).
2. Extend Planner (inside the Sensemaking Engine) to produce plans for
   non-conversational artifacts, so Executor can genuinely never reason.
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
incorporating these four recommendations before any code exists.
