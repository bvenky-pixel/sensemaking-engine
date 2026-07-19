# Understanding v1 — Specification

**Status: IMPLEMENTED, both tiers live in production.** Written
retroactively (2026-07-19, backlog #215) to give Understanding the same
versioned-spec treatment every other mature component already has.
Tier 1 shipped first as a deliberately narrow slice; Tier 2 was
originally deferred and shipped in a later round — this doc covers
both as they actually exist today, not as a proposal.

## What Understanding is, and what it isn't

Understanding answers one question: *given everything a Journey's own
WorldState already knows, what does a settled, non-flickering
statement of that understanding look like* — one that doesn't reword
itself every turn the way Judgment's freshly-synthesized prose does,
because it's rendered from WorldState's own stable, id-bearing
Fact/Claim/Goal/Decision objects rather than re-synthesized by an LLM
call each turn.

Two tiers, deliberately different in kind, not just in richness:

- **Tier 1** (`src/understanding/engine.py::build_tier1_statements`) —
  a pure, deterministic template over WorldState's raw knowledge items.
  Zero LLM calls, same discipline as
  `src/executor/engine.py::build_clarity_brief`. Calling it twice on an
  unchanged WorldState produces a byte-identical list, including every
  statement's `id` — that stability, not richness, is Tier 1's entire
  job.
- **Tier 2** (`src/understanding/tier2_engine.py`) — LLM-synthesized
  statements that connect multiple Tier 1 candidates into something
  none of them says alone (a genuine synthesis, not a restatement of
  one item). Conditional, not every-turn (see "Cost discipline" below).

`UnderstandingState` (`src/understanding/schema.py`) lives directly on
`WorldState`, not a separate DB table — Journey-scoped by construction,
so it round-trips for free through the existing
`save_turn_result`/`load_state` path, unlike `src/insight/`'s tables,
which need their own storage because they're genuine cross-session
aggregates with no single owning WorldState.

## Tier 1: deterministic rendering

`build_tier1_statements(state)` loops over all nine WorldState
knowledge-item kinds — Fact, Claim, Goal, Decision, Unknown (rendered
as `kind="uncertainty"`), Entity, Assumption, Inference,
EmotionalSignalItem — each behind its own status-visibility filter
(e.g. `_GOAL_VISIBLE_STATUSES = {"active", "paused", "completed"}`),
first-cut and explicitly uncalibrated, same convention as every other
threshold in this codebase. `id` is deterministic
(`f"tier1:{kind}:{item.id}"`), derived from the grounding item's own
stable id rather than a fresh uuid, specifically so re-rendering never
introduces the wording/identity churn this layer exists to eliminate.

Two kinds need special-case rendering because they have no single
`content` string to pass through `to_second_person`:
- **Entity** — only ever rendered when it carries at least one
  attribute or relationship; a bare mention with nothing else to say
  would just redundantly restate what a Fact already says.
- **EmotionalSignalItem** — rendered from `emotion`/`intensity`
  (scaled by `INTENSITY_SCALE` into a `/10` reading), not a content
  string.

**Decision rendering is deliberately not status-differentiated.**
`decision.content` is a bare noun-phrase label ("House", "MBA"), not a
sentence, so it's wrapped in a template
(`f"You're weighing {...} as an option."`) rather than passed through
raw. A resolved Decision's actual outcome (chosen vs. rejected) isn't
recoverable from `status` alone — `DecisionResolution`/`DecisionEvent`
both collapse to the same `"resolved"` value — so a confident
"You've decided on X" phrasing would risk asserting the wrong outcome
for a rejected option. One neutral template stays correct regardless.

## Tier 2: conditional LLM synthesis

Design decisions (see `engine/decisions.md` "Tier 2 design"), as
actually implemented in `tier2_engine.py`:

- **Runs inside the live turn**, unlike `src/insight/` (offline-only) —
  Tier 2 lives on ONE Journey's own WorldState.
  `src/orchestrator/engine.py::run_turn` is the single call site
  (`update_tier2`, called after Tier 1 populates).
- **Non-blocking failure mode** — unlike
  Interpretation/Judgment/Planner/Response, ANY Tier 2 exception
  (provider error, invalid JSON, schema validation) is caught inside
  `update_tier2` and swallowed; WorldState is returned completely
  unchanged, exactly as if the turn hadn't recomputed Tier 2 at all.
  Tier 2 must never abort a turn or regress WorldState.
- **Conditional, not every-turn** — the whole point of the design
  pass: a 5th LLM call every turn was rejected as a cost. Two gates
  decide whether to actually call the LLM this turn:
  1. `select_tier2_candidates` splits candidates into "thread" kinds
     (goal/decision/uncertainty — kept as long as non-terminal,
     regardless of recency) and "detail" kinds (fact/claim/assumption/
     inference/entity/emotion — kept only within
     `TIER2_RECENCY_WINDOW_TURNS` (10) turns of their own
     `provenance.last_updated`).
  2. `compute_tier2_grounding_signature` hashes the CURRENT candidate
     pool (id + real status + text), not just the ids an existing
     Tier 2 statement cites — this is deliberate: hashing only
     already-cited ids would miss a new near-duplicate candidate
     entering the pool. `should_recompute_tier2` triggers a real LLM
     call when this signature changed, Tier 2 has never been computed,
     or `TIER2_STALENESS_TURNS` (5) turns have passed regardless —
     a hard backstop, since the hash can't catch every staleness cause
     (e.g. conversational emphasis shifting with no new WorldState
     item at all).
- **Engine-level grounding enforcement** (`_enforce_grounding`), same
  discipline as `src/insight/engine.py`'s own evidence-id filtering:
  every `Tier2Statement.grounding_item_ids` is filtered to the
  intersection with ids actually offered as candidates; a statement
  with fewer than `MIN_GROUNDING_ITEMS` (2) surviving ids is dropped
  entirely — a synthesis grounded in fewer than 2 real candidates is a
  paraphrase of one, not a synthesis of several. Surviving statements
  get a fresh `id` (`f"tier2:{uuid4()}"`) and `tier=2`, `kind="synthesis"`
  — a Tier 2 statement's identity is its own cached-until-regenerated
  text, not a 1:1 mapping to one grounding item the way Tier 1's is.

## Frontend

`GET /sessions/{id}/understanding` returns both tiers
(`UnderstandingResponse.tier1`/`.tier2`). `Understanding.svelte`
deliberately renders ONLY `tier2`, never `tier1`, directly — Tier 1 is
a raw, unranked, per-item render that substantially duplicates what
`situation`/`key_insights`/`decisions`/`remaining_unknowns` (Judgment's
own curated Clarity Brief content, rendered elsewhere in the same
component) already show, and its own growth is confirmed unbounded
with no prioritization design yet (validation report Area 5/7). Tier 2
is different: genuinely additive, LLM-synthesized content, naturally
bounded by what synthesis actually produces rather than by turn count.

## Non-goals

Tier 1 never calls an LLM and never changes its own rendering logic
based on conversation content — richer Tier 1 rendering (e.g. ranking,
grouping) is a distinct, not-yet-scoped increment (see backlog #248,
"Understanding: scope Tier 2 v2"). Tier 2 never runs unconditionally,
never blocks a turn on its own failure, and never trusts a model's
grounding claims without engine-level verification.

## Open questions

1. **`src/understanding/__init__.py`'s own docstring is stale** — it
   still describes Tier 2 as "deferred," written when that was true;
   Tier 2 has since shipped in full (this doc's own existence is the
   correction). Worth a direct docstring fix, tracked separately, not
   done as part of writing this spec (same "don't silently expand
   scope while documenting" discipline as `learning-specification-v1.md`'s
   own reconciliation entries). Tracked as backlog #288.
2. **Tier 1's status-visibility filters and Tier 2's
   TIER2_RECENCY_WINDOW_TURNS/TIER2_STALENESS_TURNS/MIN_GROUNDING_ITEMS
   constants are all explicitly uncalibrated** first-cut values, same
   as `learned_patterns`' own `MIN_EVIDENCE` before Learning's own
   calibration backlog item. Backlog #289 dispatched a real 11-turn
   live walkthrough specifically to check this (`engine/decisions.md`
   "Understanding #289") — no constant was changed, since the finding
   was about the recompute TRIGGER's sensitivity (see #295 below), not
   evidence that either turn-count number itself is miscalibrated. The
   recency window's own pruning behavior remains genuinely untested:
   an 11-turn transcript is structurally incapable of exercising a
   10-turn window's first exclusion.
3. **Backlog #295 — RESOLVED 2026-07-19** (see engine/decisions.md
   "Understanding: Tier 2 recompute gated to thread-item status changes
   only"): the founder was asked directly, given the mechanism-question
   framing above, and chose to gate `compute_tier2_grounding_signature`
   on thread-kind (goal/decision/uncertainty) status changes ONLY,
   excluding detail-kind (fact/claim/entity/assumption/inference/
   emotional signal) candidates from the signature entirely — ordinary
   detail accumulation no longer counts as "the situation changed
   enough to re-synthesize," restoring the original design's intended
   rarity. Detail kinds remain full candidates once a recompute IS
   triggered by something else (`select_tier2_candidates` unaffected).
4. **Tier 2 v2** (declarative-uncertainty and values-level synthesis
   beyond what the current candidate-pool design produces): a concrete
   discussion-draft proposal was written 2026-07-19 at the founder's
   direction (see `engine/specs/tier2-v2-design-proposal.md`), defining
   both phrases concretely for the first time and recommending further
   review before either is built — not yet approved, not yet
   implemented. See backlog #248.
5. **Live-dispatch calibration (backlog #290) has now run three times**
   against `scripts/run_tier2_calibration.py`'s four scripted scenarios
   — see engine/decisions.md's three "Tier 2 ... live calibration run"
   entries. The third run (self-check gate added to law 3 of
   `tier2_prompt.py`) scored 3/3, fixing the over-synthesis problem
   (fabricating a connection between two genuinely unrelated
   candidates) that both prior runs left open. Still only 4 scripted
   scenarios, not real production conversation volume — worth
   continued attention once real usage exists, not a closed question.

## Verification

Real, live-dispatched validation exists for Tier 1: the original
validation report (`experiments/confidant-validation/tier1-validation-report.md`)
covered completeness (the Entity/Assumption/Inference/Unknown render
gaps that were later fixed) and the Decision bare-label rendering bug
(also fixed). Tier 2's own design and grounding-enforcement logic are
covered by `tests/test_understanding.py`'s Tier 2 test classes
(candidate selection by kind, grounding-signature stability,
recompute-trigger conditions, and grounding enforcement dropping
under-grounded statements). Three live-dispatch calibration rounds have
now run against `scripts/run_tier2_calibration.py` (see
`engine/decisions.md`) — the third, after adding a mandatory self-check
to the synthesis prompt, scored 3/3 and fixed the over-synthesis
problem (fabricating a plausible-sounding but unstated connection) both
prior rounds left open, without suppressing genuine synthesis.
