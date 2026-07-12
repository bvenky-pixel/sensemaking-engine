# Validation Report: Stable Identity + Tier 1 Understanding

**Date**: 2026-07-12
**Scope**: `src/state/world_state.py` (KnowledgeItem.id, confidence tiering, Assumption/Inference), `src/understanding/` (Tier 1 schema + engine), `scripts/backfill_knowledge_item_ids.py`, the prompt-hygiene fix, shipped in commit `7c93fcc`.
**Question**: Can Stable Identity + Tier 1 Understanding serve as a trustworthy foundation for Shared Understanding?
**Method**: This is not a re-derivation of correctness — it is an attempt to break the implementation. Findings below are grounded in three evidence sources, each labeled by provenance:

- **[LIVE]** — a real 10-turn, 4-call-per-turn conversation dispatched through `.github/workflows/worldstate-walkthrough.yml` against a live LLM (GitHub Actions run `29189585671`). Turns 1-5 were lost to a log-retrieval truncation limit; turns 6-10 plus the full final accumulated state were recovered and analyzed.
- **[CAPTURED]** — real single-turn Interpretation outputs from `experiments/confidant-validation/log.md` (30 cases, captured 2026-07-07), replayed through the current, real `update_state`/`build_tier1_statements` code. This dataset predates the v1.1 Interpretation schema (5 fields — `has_assumption`, `assumption_check`, `has_decision_event`, `decision_event_option`, `decision_event_type` — did not exist yet); replay required supplying defaults for those fields. Findings from this source describe real model behavior on a pre-v1.1 baseline, not the exact current Interpretation prompt.
- **[SYNTHETIC]** — a standalone stress harness (`/tmp/.../scratchpad/long_horizon_stress.py`, not part of the shipped codebase) that drives the real, unmodified `update_state`/`build_tier1_statements` functions through 100 synthetic-but-realistic turns to observe behavior at a turn count no real Journey has reached yet (product is pre-launch). Explicitly not a claim of real Journey data — it isolates the deterministic merge/render code under volume.

No other evidence sources were available: this sandbox cannot reach the production Fly.io database (network-proxied, 403), has no local database with real Journeys, and has no `OPENROUTER_API_KEY` for direct live calls.

---

## Executive Summary

**Overall assessment**: The core mechanism — stable per-item ids, deterministic confidence tiers, byte-identical re-rendering of an unchanged WorldState — works exactly as designed and is well-covered by tests (241 passing, including dedicated determinism and prompt-hygiene regression tests). That part of the foundation is trustworthy.

But "foundation for Shared Understanding" is a larger claim than "the rendering layer is deterministic," and validation surfaced real, reproducible problems one layer up — in what gets *fed into* that stable rendering, and in what happens *after* something changes. None of these are Tier 1 rendering bugs; all of them are either (a) pre-existing gaps in `src/state/builder.py`'s matching logic that this round's stable ids make newly visible rather than newly caused, or (b) structural absences — content Interpretation captures that has nowhere to go in WorldState at all.

**Confidence level**: Medium. High confidence in the mechanism that was actually validated (identity stability, determinism, tiering, prompt isolation). Low confidence in production-readiness of what a person would actually see, because the input data feeding Tier 1 duplicates, goes stale, and drops real signal (emotions, assumptions caught too late, decision options with no sentence template) well before Tier 1 ever gets a chance to render it.

**Major risks**:
1. The migration script (`scripts/backfill_knowledge_item_ids.py`) has never been run against production. This is not a design flaw — it's an operational gap with a concrete, immediate consequence.
2. Near-duplicate facts/claims are not merged (exact-string dedup only) and accumulate without bound or decay — confirmed in real (not just synthetic) data.
3. Facts and Claims have `"retracted"`/`"superseded"` states defined in the type system but **no code path ever sets them** — the schema anticipated correction; the implementation doesn't deliver it yet.
4. `emotional_signals` — a real, structured Interpretation output — has no field anywhere in WorldState. It's not filtered out of Understanding; it's discarded before WorldState exists.

**Recommendation**: **Perform targeted fixes first.**

---

## Findings by Validation Area

### Area 1 — Identity Stability

**Positive, confirmed [LIVE]**: Across the recovered turns of the live walkthrough, every `KnowledgeItem.id` was stable turn to turn for unchanged content, and entity identity survived enrichment — the entity "Sarah" kept the same id across turns while gaining a `role: Head of Product` attribute mid-conversation (turn 8). This is exactly the "same entity, evolving over time" behavior the whole Journey-scoped design was meant to produce, and it worked on live LLM output, not just constructed fixtures.

**Negative, confirmed [LIVE]**: Stable ids do not imply *unique* ids per real-world referent. `_merge_content_items`'s exact-match, case-insensitive string dedup (unchanged this round, by design) let the same underlying fact accumulate multiple ids across turns because the model phrased it differently each time. In the live 10-turn run: "considering applying externally" appears as byte-identical text in **both** the facts section and the claims section (two separate ids, same content, same referent, different epistemic tier) — and "wants to move to the Product team" is restated with enough wording drift across turns that it was never recognized as the same fact.

**Negative, confirmed [SYNTHETIC], scaled**: The stress harness's `NEAR_DUPLICATE_FACT_VARIANTS` group (4 realistic phrasings of one underlying fact, injected once every 7 turns) produced exactly 4 separate `Fact` objects with 4 separate ids at every turn count tested (20/40/100) — none ever merged, confirming this is not a rare edge case but the deterministic, guaranteed outcome of the current matching logic whenever phrasing drifts even slightly.

**Verdict**: Ids are stable. Identity — "this is the same real-world thing as last turn" — is not reliably assigned in the first place, because the matching step upstream of id assignment is exact-string. This is a pre-existing gap (not introduced this round, confirmed as an explicit non-goal in the original plan), but it directly undermines the "trustworthy foundation" claim: an id is only as trustworthy as the matching decision that created it.

### Area 2 — Understanding (Tier 1) Stability

**Positive, confirmed by test + [LIVE]**: `build_tier1_statements` is provably a pure function — `test_build_tier1_statements_is_byte_identical_across_two_runs_given_identical_worldstate` asserts full-list equality including `id`, and the live walkthrough's printed Tier 1 output showed ids of the form `tier1:{kind}:{item.id}` remaining unchanged across turns for unchanged source items. Re-rendering does not itself introduce churn — the specific problem this layer was built to solve is solved.

**Verdict**: Solid. No caveats found. This is the one area with no negative findings.

### Area 3 — Understanding Quality

Evidence: full turn-10 state from the live walkthrough (26 Tier 1 statements: 12 facts, 10 claims, 2 goals, 2 decisions rendered from 12/10/2/2 source items; 3 `assumption_items`, 0 `inference_items`), plus three [CAPTURED] replays chosen for diversity (career/fact-heavy, emotional, decision, assumption-detection).

**Usefulness/readability — mostly good for Fact/Claim/Goal**: Second-person rendering reads naturally in the common case. `[CAPTURED] D01` ("I can afford either a house or an MBA, but not both."): `[fact] 'You can afford a house.'`, `[claim] 'You can afford either a house or an MBA.'` — clean, recognizable, grounded.

**Real grammar defect, confirmed [CAPTURED] R02**: `to_second_person`'s own docstring documents a deliberate conservative choice — "they"/"their"/"them" are left unrewritten whenever the sentence contains a third-party noun (friend, manager, etc.), to avoid misattributing another person's pronoun to the user. Replaying R02's real Interpretation output ("User thinks their friend is angry with them.") through the actual pipeline produces: `[claim] 'You think their friend is angry with them.'` In this specific, real sentence, both "their" and "them" refer to the *user*, not the friend — the heuristic's false-positive case is not hypothetical, it's the first real example tested. The result is a grammatically confusing sentence that mixes second- and third-person for the same referent, which is arguably harder to read than pure third person would have been. This is a distinct, narrower residual of the same class of bug fixed in the pre-session grammar/spelling regression (`f335113`), not yet covered by that fix.

**Structural quality gap, confirmed [CAPTURED] D01**: Decisions are rendered by running `decision.content` through the same `to_second_person` template as Facts/Claims/Goals. But `decision.content` comes from Interpretation's `decision_options` field, which is a bare label ("House", "MBA"), not a sentence — Interpretation never produces full-sentence decision options. The real Tier 1 output for D01 is two isolated bullet statements: `[decision] 'House'` and `[decision] 'MBA'`. There is no wrapping template ("Deciding between: House vs. MBA") — this is the one statement kind that doesn't get a real English sentence, and it's not a rare input shape; every Decision in the corpus is bare-label content by construction.

**Completeness gap, confirmed across [LIVE] and [CAPTURED]**: `build_tier1_statements` renders exactly four of WorldState's eight knowledge-item categories (Fact, Claim, Goal, Decision). `Unknown` and `Entity` are never rendered at all — confirmed in both the live run (a stale Unknown from turn 2 remains invisible to Understanding even though it's a first-class, populated WorldState field) and R02 (`entities: ['friend']` present in WorldState, absent from Tier 1). `Assumption`/`Inference` (the two new types shipped this round specifically to give Understanding something to cite) are populated in WorldState (3 assumption_items by turn 10 of the live run) but also never appear in `build_tier1_statements`'s output — the shipped engine only has loop bodies for facts/claims/goals/decisions. A person reading the Understanding panel today would see a *subset* of what the system has captured about them, with no visible indication that the subset is partial.

**Staleness, confirmed [LIVE]**: A Goal recorded at turn 1 (`first_seen=1, last_updated=1`) never received a status update across all 10 turns, despite the conversation's trajectory plausibly bearing on it. Two Unknowns recorded at turn 2 (`first_seen=2, last_updated=2`) remained open and unrendered-as-resolved through turn 10, even though the underlying ambiguity was substantively addressed by the conversation (Sarah's promotion explaining the freeze) — the word-overlap resolution threshold simply didn't fire. Nothing in Understanding distinguishes "this was just established" from "this hasn't been touched in 8 turns and might no longer be true."

**Structural signal loss, confirmed [CAPTURED] E03**: Replaying E03 ("User doesn't enjoy anything anymore") through the real pipeline produces a correct, minimal Tier 1 render (`[fact] 'You express a lack of enjoyment.'`, `[claim] 'You do not enjoy anything.'`) — but Interpretation's own `emotional_signals` output for this input (`EmotionalSignal(emotion='disenchantment', intensity=0.8, confidence=0.9, source='explicit')`) has no home anywhere in `WorldState`. This isn't a Tier 1 rendering omission (like Unknown/Entity above) — `WorldState` has no `emotional_signals` field at all. A structured, confidence-scored, explicitly-sourced emotional signal is captured by Interpretation and then discarded before the state layer even exists, let alone before Understanding could reflect it.

**Would a person recognize themselves?** For the rendered subset (Fact/Claim/Goal, most Decisions), largely yes — the second-person voice and grounding-by-id genuinely deliver "this reads like it's about me, not a summary of me." For the unrendered/lost content (Unknowns, Entities, Assumptions, Inferences, emotional signals, anything requiring correction) — no, because that content isn't in the document at all, and there's no way for a reader to know something is missing.

### Area 4 — Persistence Tier Audit

Constants confirmed correct by direct test coverage (`test_fact_goal_decision_get_highest_tier_confidence`, `test_claim_gets_interpretive_tier_confidence`, `test_assumption_item_gets_lowest_tier_confidence`, `test_inference_item_confidence_matches_real_interpretation_confidence_not_a_constant`): Fact/Goal/Decision = 1.0, Claim = 0.7, Assumption = 0.3 (flat constant), Inference = real per-item value from Interpretation's own calibrated `Inference.confidence`.

**Finding — tier asymmetry**: Assumption and Inference are the system's two lowest-epistemic-tier categories, and they're treated inconsistently. Inference gets genuine per-item confidence, already floor-filtered upstream (`INFERENCE_CONFIDENCE_FLOOR = 0.15`) — a real, differentiated signal. Assumption gets one flat number (0.3) for every assumption regardless of how confidently or tentatively Interpretation stated it, because `Interpretation.assumptions` is a bare `List[str]` with no per-item confidence field upstream. This isn't a bug in this round's code — the constant correctly reflects "no real signal exists" — but it means Assumption's confidence value carries no actual information; anything that later treats `confidence` as meaningful (a future ranking, a future "how sure is Confidant about this" UI affordance) will be silently wrong for every Assumption specifically.

### Area 5 — Long-Horizon Journeys (20/40/100 turns) [SYNTHETIC]

- **Unbounded linear growth, no pruning or decay anywhere in the pipeline**: `facts`, `claims`, `assumption_items`, `inference_items`, and `tier1` statement counts all grow roughly linearly with turn count across all three checkpoints. By 100 turns, Understanding would be rendering on the order of 100+ statements with no ranking, grouping, or recency weighting — only the binary status-based inclusion filters that already exist. A "living document" that only ever grows is not distinguishable from a transcript with better formatting.
- **Near-duplicate accumulation confirmed at scale**: the injected 4-variant fact group produced exactly 4 permanent, never-merged ids at every checkpoint (matches the real-data finding in Area 1, now shown to compound with volume rather than self-correct).
- **Goal staleness confirmed at scale**: the turn-3 goal's `last_updated` never advances past turn 3 at any checkpoint (20/40/100) — `status`/`confidence` stay at their initial values indefinitely with zero signal that 97+ turns have passed since anything touched it.
- **Unknown resolution confirmed fragile at scale**: the turn-4 unknown, "indirectly" touched by a low-word-overlap related fact at turn 30, remains open and unresolved at every later checkpoint — the same `_is_resolved_by` threshold behavior seen in the live run, now confirmed as a systematic property rather than a one-off miss.
- **Assumption/Inference growth is also unbounded**: both grow steadily (~1 new item per 4-5 turns) with no retraction or expiry mechanism (see Area 6).

**Verdict**: The deterministic merge/render code itself does not degrade, crash, or slow at these volumes (it's O(n) string comparisons — no correctness failure was found). But nothing in the current design bounds what accumulates, which means the long-horizon failure mode isn't a code defect, it's an absence of any pruning/prioritization concept at all.

### Area 6 — Correction Readiness

This is the area with the clearest, most concrete architectural gap.

**What already has a correction pathway**: `Goal.status`, `Decision.status`, and `Unknown` resolution are mutated by dedicated Interpretation-driven signals (`GoalUpdate`, `DecisionEvent`, judgment-driven resolutions) via `_apply_goal_updates`/`_apply_decision_events`/`_reconcile_unknowns` in `src/state/builder.py`. This machinery pre-dates this round and is untouched by it.

**What the type system anticipates but the code never wires up**: `FactStatus` and `ClaimStatus` (`src/state/world_state.py`) are both `Literal["active", "superseded", "retracted"]` — the schema was explicitly designed with correction in mind. Confirmed by grep across `src/state/builder.py`: `.status = ` is assigned only for `Goal` and `Decision` objects. **No code anywhere ever sets a Fact or Claim's status to `"superseded"` or `"retracted"`.** Once created, a Fact or Claim is permanent for the life of the Journey; the only way it stops appearing is if it was never created in the first place (blocked by exact-match dedup at creation time, not a correction). The two new types shipped this round, `Assumption`/`Inference`, copy this same pattern — both define `status: Literal["active", "retracted"]`, and neither has any code path that ever sets `"retracted"`.

**Where detection happens but nothing acts on it**: `Judgment.contradictions: List[str]` is a real, populated field — Judgment's own prompt explicitly instructs it to name "real conflicts between two specific pieces of WorldState" (`src/judgment/prompt.py`). Confirmed by grep: `judgment.contradictions` is consumed only as descriptive text fed into Planner's prompt and into evaluation metrics — it never triggers a WorldState mutation, and `Judgment` objects aren't persisted turn-to-turn, so a detected contradiction is architecturally incapable of surviving past the turn that found it.

**Net effect**: if a person said "actually, that's wrong" about something in their Understanding today, there is a complete gap between "the system could plausibly notice" (Judgment's contradiction detection exists and works at the text level) and "the system could act" (nothing consumes that detection to retract or supersede the specific Fact/Claim/Assumption/Inference it concerns). Correction semantics are not a Tier 2 feature to design from scratch — the status vocabulary already exists — but the mutation logic and the detection-to-mutation wiring do not exist for four of the eight knowledge-item types.

### Area 7 — Tier 2 Readiness

Grounded directly in Areas 3 and 6, not a fresh line of speculation:

- **The deferred Tier 2 design assumes it synthesizes from WorldState's grounding items** (cache key = `(id, status, content)` per item). But Area 3 showed real signal — assumptions, emotional intensity/valence — either arrives too late to be captured in WorldState in the shape Tier 2 would need (R02: the assumption was only ever named at Planner, never populated in Interpretation's own dedicated `assumptions` field, so `assumption_items` had nothing to hold for that turn) or has no WorldState field at all (E03: `emotional_signals`). Tier 2 built purely against WorldState inherits both gaps — it would have nothing to synthesize from in exactly the cases where synthesis would add the most value (naming an unstated assumption, reflecting an emotional undertone).
- **Tier 2's grounding-signature cache invalidates on `(id, status, content)` changes to already-grounded items** — but Area 1/5 showed the dominant real failure mode is a *new* near-duplicate item appearing (a new id), not an existing item's content/status changing. The deferred cache design would correctly invalidate on a Decision flipping to `resolved`, but would not obviously prompt re-synthesis when three new near-duplicate Facts pile up around an existing one — an open question the deferred design doesn't yet address.
- **Tier 2 has no answer yet for prioritization at scale**: Area 5 showed unbounded Tier 1 growth with no ranking. If Tier 2 is meant to be the layer that produces a smaller number of higher-level synthesized statements, its design doc doesn't yet say how it would choose which of (at 100 turns) 100+ Tier 1 candidates to synthesize from, or how it would avoid re-synthesizing stale material every time grounding drifts.
- **Positive**: the non-blocking failure mode, single call-site design, and grounding-enforcement plan (mirroring `src/insight/engine.py`'s existing, working pattern) are sound and don't need rework — they weren't touched by anything found in this validation.

---

## Failure Modes (ranked by priority)

1. **Migration script never run in production.** `scripts/backfill_knowledge_item_ids.py` is implemented, tested (4 passing tests including idempotency and `updated_at` preservation), and safe — but this sandbox has no path to production's database, so it has not actually been executed there. Until it runs, every pre-existing production session's `KnowledgeItem.id` values are being freshly regenerated by `default_factory` on every load, meaning Tier 1's `id=f"tier1:{kind}:{item.id}"` scheme is *not yet stable* for any Journey that predates this deploy — the exact bug this whole round exists to fix. This is an operational gap, not a design flaw, but it means the foundation isn't actually load-bearing yet for existing users.
2. **Facts/Claims/Assumptions/Inferences have no retraction pathway despite the type system anticipating one.** (Area 6.) A person's stated correction has nowhere to land for 4 of 8 knowledge-item types.
3. **Near-duplicate accumulation is real, not hypothetical, and unbounded.** (Areas 1, 5.) Confirmed in live data, confirmed to compound with volume, no decay or merge-on-similarity exists.
4. **Emotional signal is structurally discarded before WorldState exists.** (Area 3.) Not a rendering gap — a schema gap. Any future "does Understanding reflect how someone feels, not just what they said" ambition is blocked at the state layer, not the Understanding layer.
5. **Tier 1 renders 4 of 8 knowledge-item kinds; the panel understates what the system knows with no signal that it's doing so.** (Area 3.)
6. **Decision rendering produces bare labels, not sentences.** (Area 3.) Narrower than #5 but a concrete, always-reproducible quality defect given how Interpretation actually populates `decision_options`.
7. **The `to_second_person` third-party-marker heuristic has a confirmed false-positive on real data**, producing mixed-person sentences. (Area 3.) Lower severity than the above — cosmetic, not a data-loss or correctness issue — but real and reproducible.
8. **Assumption confidence is a flat, uninformative constant.** (Area 4.) Latent risk, not yet causing visible harm, but will silently mislead any future consumer that treats `confidence` as meaningful signal.

---

## Architectural Implications

- **WorldState**: needs (a) an `emotional_signals` field with its own lifecycle, not folded into Facts/Claims as prose, and (b) a real similarity-based merge step (beyond exact-string) if near-duplicate accumulation is to be addressed at the source rather than papered over at render time. Both are pre-existing gaps this round's stable ids made *measurable* rather than newly introduced.
- **Understanding (Tier 1)**: needs coverage for Unknown/Entity/Assumption/Inference (four straightforward additions, same template pattern already proven for Fact/Claim/Goal/Decision) and a dedicated Decision template (not a `to_second_person` passthrough) before it can claim to represent "what the system knows," not just a curated four-of-eight subset.
- **Identity**: the id mechanism itself is sound; what needs rework sits one layer below it, in `_merge_content_items`'s matching function. Any future identity-adjacent work (e.g., a similarity-based merge) should be layered on top of the existing id scheme, not require changing it.
- **Tiering**: sound for Fact/Goal/Decision/Claim/Inference; Assumption's flat constant should either be left explicitly documented as "not a real signal, do not rank by it" or be given a real per-item source (would require an Interpretation schema change).
- **Correction workflows (future)**: the type system is ahead of the implementation here — `FactStatus`/`ClaimStatus`/`AssumptionStatus`/`InferenceStatus` already include the right vocabulary. The missing piece is entirely on the mutation side: an Interpretation-level or Judgment-level signal analogous to `GoalUpdate`/`DecisionEvent`, plus `update_state` wiring to consume it. `Judgment.contradictions` is the closest existing precedent for detection and could plausibly be extended into this role rather than inventing a new detection mechanism from scratch.

---

## Recommendation

**Perform targeted fixes first.**

The rendering mechanism this round set out to build — stable ids, deterministic tiering, byte-identical Tier 1 re-rendering, prompt isolation — is genuinely solid and well-tested; nothing in this validation found a defect in that specific mechanism. But "trustworthy foundation for Shared Understanding" was tested against real and synthetic data, not just unit fixtures, and that testing surfaced concrete, reproducible problems that would be directly visible to a person using the product today: duplicated statements, stale goals and unknowns with no way to tell they're stale, a Decision that renders as a bare word, lost emotional content, and — most urgently — a migration that hasn't actually run against the data it exists to fix. Building Tier 2 on top of this foundation now would inherit every one of these gaps and make them harder to isolate later, since Tier 2's synthesis would be reasoning over data that's already duplicated, stale, and incomplete. None of the findings suggest the Journey-scoped identity architecture itself is wrong — they suggest the layer just below it (matching, mutation, completeness of what gets captured) needs to catch up before more is built on top.
