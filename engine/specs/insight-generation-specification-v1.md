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

### Tier B -- Cross-session, offline (Learning + Insight Engine, as TWO LAYERS)

**Decided (founder/CPO, 2026-07-22)**: Tier B is not "pick one of
Learning or Insight Engine per pattern type" (this spec's own earlier
draft framed it that way and that framing is now superseded). It is two
layers with an explicit dependency between them:

- **Learning Layer -- durable memory.** Stores raw, recurring,
  individually-evidenced observations. Founder's own worked examples:
  "Frequently prioritizes autonomy over compensation," "Often delays
  decisions until confidence exceeds 80%," "Avoids interpersonal
  conflict." Each is a single, bounded, evidence-gated claim -- exactly
  the shape `src/learning/`'s existing `MIN_EVIDENCE`-gated pattern
  detection already produces. Learning's job stops at storing these as
  discrete patterns; it does not connect them to each other.
- **Insight Engine -- interpretation OF Learning's own patterns.**
  Generates a higher-level observation FROM a set of Learning's already-
  detected patterns, not from raw session content directly. Founder's
  worked example: Learning independently stores "Autonomy > Compensation,"
  "Autonomy > Prestige," and "Autonomy > Security" as three separate
  patterns; Insight Engine synthesizes those three into "Across six
  major decisions, autonomy appears to be your strongest recurring
  decision criterion." A second worked example, a different shape of
  synthesis entirely: "You often continue gathering information after
  your preferred option is already apparent" -- a meta-observation about
  a recurring DECISION-MAKING BEHAVIOR, not a restatement of any single
  stored pattern.

**This is a real, new dependency, not the status quo.** Confirmed by
reading the actual code: Insight Engine and Learning today are SIBLINGS,
not layers -- both independently read raw session/behavioral data
(`src/retrieval/engine.py` reads `get_learned_patterns`/`get_insights` as
two parallel, independently-computed outputs, never one feeding the
other). Making Insight Engine actually consume Learning's stored
patterns as its own input is new plumbing this spec must call out
explicitly, not assume already works this way.

| Insight type | Layer | Status |
|---|---|---|
| Recurring avoidance patterns | Learning | New pattern category on existing `MIN_EVIDENCE`-gated infrastructure -- not a new mechanism, a new label Learning's existing detection can produce. |
| Decision-making tendencies (e.g. "delays until >80% confidence") | Learning | Same -- new category, same mechanism. |
| Repeated tradeoff patterns, RAW form (e.g. "Autonomy > Compensation") | Learning | New category -- each individual tradeoff comparison is itself a Learning-shaped pattern. |
| Repeated tradeoff patterns, SYNTHESIZED form (e.g. "autonomy is your strongest recurring decision criterion") | Insight Engine, reading Learning's own stored patterns as input | **New dependency.** Insight Engine's `Theme` generation must be extended to accept Learning's patterns as an input source, not just raw session content. |

**What this means for the build**: three new Learning pattern
categories (additive, same evidence-gating as every existing category --
no new mechanism), plus one real architecture change (Insight Engine
gains a new input path: Learning's own stored patterns, in addition to
whatever it reads today), plus a new SYNTHESIS step in Insight Engine
specifically for connecting multiple same-shaped Learning patterns
(e.g. multiple "X > Y" tradeoff patterns) into one higher-level claim --
this synthesis step is conceptually close to what Tier 2
(`src/understanding/tier2_engine.py`) already does within a single
Journey (connecting two or more Tier 1 candidates into something neither
states alone), just one layer up, across Journeys instead of across
WorldState items. Worth building Insight Engine's new synthesis step
with that existing Tier 2 discipline as the direct model: same "must
connect two or more inputs in a way that adds real insight, restating
one input's own content is not synthesis" law, same grounding
enforcement (never trust the model's own citations of which Learning
patterns it drew from -- filter post-hoc against real ids, same as Tier
2's `_enforce_grounding`).

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

1. **Surfacing location.** Tier A insights (contradictions, stalls)
   surface in the Clarity Brief (per that spec). Where do Tier B
   insights surface -- Learning's raw patterns presumably stay on the
   You tab (where they already live), but where do Insight Engine's new
   SYNTHESIZED cross-pattern observations surface? The You tab alongside
   the raw patterns they were built from, a new dedicated surface, or a
   conversational callback INTO a live Journey (POM already has a
   precedent for this -- backlog #210, "Insight-triggered conversational
   callback")? Worth an explicit decision rather than defaulting to
   wherever Learning's output already renders.
2. **Cadence.** Tier B computation is `workflow_dispatch`-only today
   (backlog #268, deliberate, not yet revisited). The new Learning ->
   Insight Engine dependency actually makes this MORE relevant, not
   less: Insight Engine's new synthesis step needs a fresh run of
   Learning's own patterns to synthesize FROM, so the two computations
   likely need to run in a defined order (Learning, then Insight Engine)
   rather than independently on their own separate schedules as today --
   worth resolving alongside whatever resolves #268, not independently.

---

Rollout

1. Confirm Tier A requires no new backend work (true today) -- fold its
   visibility gap entirely into the Clarity Brief spec's rollout.
2. Add the new Learning pattern categories (avoidance, decision-making
   tendency, raw tradeoff comparisons) -- additive, existing
   `MIN_EVIDENCE` mechanism, no new plumbing.
3. Build Insight Engine's new input path (reading Learning's own stored
   patterns, not just raw session content) and its new synthesis step
   (connecting multiple same-shaped Learning patterns into one higher-
   level claim), modeled directly on Tier 2's existing synthesis
   discipline (see above) -- this is the one genuinely new piece of
   engineering in this whole spec.
4. Resolve Open Question 1 (surfacing location for Insight Engine's new
   synthesized observations) before finalizing the frontend surface.
5. Live-dispatch calibrate the new categories AND the new synthesis step
   against real multi-Journey data, same discipline as every existing
   Learning/Insight Engine calibration round (tasks #289, #292, #293).
