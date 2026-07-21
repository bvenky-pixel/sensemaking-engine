# Orchestrator v1 — Specification

**Status: IMPLEMENTED, the single call site for every live turn.**
Written retroactively (2026-07-19, backlog #221) to give Orchestrator
its own versioned spec, distinct from the abstract "Orchestrator"
section already in `engine/specs/system-architecture-v2-specification.md`
(§1) — that section describes the vision's full scope; this doc
describes what `src/orchestrator/engine.py::run_turn` actually does
today, deliberately narrower.

## What Orchestrator is, and what it isn't

Orchestrator coordinates one turn through the fixed Sensemaking Engine
pipeline: Interpretation → WorldState update/phase → Judgment → Planner
→ Response Generator. This was previously duplicated, inline, in two
separate driver scripts (`conversation_runner.py`,
`scripts/run_worldstate_walkthrough.py`) — extracting it into
`run_turn` didn't invent new behavior, it gave already-working
coordination logic one tested, shared home, and fixed a real
correctness bug in the process: `conversation_runner.py` used to print
"State unchanged" on ANY stage failure, which was false whenever
Judgment, Planner, or Response Generator failed, since WorldState had
already been genuinely updated by that point.

**Scoped down deliberately from §1's full vision**, same discipline as
every other "build X" task in this codebase. Built: sequencing/
coordination (which processes run, in what order) and stage-level
recovery (if a stage fails, stop the turn and report exactly how far it
got, including whatever state/artifacts earlier stages already
produced). Explicitly NOT built, deliberately deferred, named in §1 but
with no implementation here yet:
- **Skipping unnecessary computation** — no evidence yet this
  optimization is needed, and §1's own restriction ("skip logic must
  stay mechanical/structural, never semantic") means this needs a real
  structural trigger design, not a guess.
- **Selecting models as interaction-level policy** (e.g. a stronger
  model tier for a higher-stakes turn) — no criteria for
  "higher-stakes" exists anywhere in this codebase today.
- **Managing retries beyond stage-level stop-and-report** — no
  evidence yet that retrying a whole failed stage would help; the
  call-level provider fallback each engine already does
  (`src/llm/providers.py`) stays exactly where it is, per §1's explicit
  scope boundary between call-level and stage-level.

Orchestrator never performs user reasoning: it only sequences calls and
reports what happened, never judging what any stage's output means.

## The fixed pipeline, stage by stage

`run_turn(message, state, tracker=None, session_id="", on_stage_complete=None, mode=None, retrieved_context="", pom=None) -> TurnResult`:

1. **Interpretation** (`run_interpretation`) — the only stage that runs
   before WorldState is touched. On failure, `state` in the returned
   `TurnResult` is genuinely unchanged (the only case where that's
   true).
2. **`update_state(state, interp)`** — commits this turn's
   Interpretation into WorldState. Once this runs, every later failure
   still reflects a real, committed WorldState update in the returned
   `TurnResult.state`. `diff_behavioral_events` (Learning Phase 1) is
   computed against the pre/post snapshot immediately after.
3. **`recommend_phase_transition`** and **Tier 1 rendering**
   (`build_tier1_statements`) — both cheap, WorldState-only,
   deliberately NOT gated behind try/except (no external call, no
   failure mode worth guarding against), unlike the four real pipeline
   stages.
4. **Judgment** (`run_judgment`, given `retrieved_context`) — on
   success, two write-back exceptions to "Judgment only ever reads
   WorldState" apply: `apply_judgment_resolutions` (turns
   `decision_resolutions` into an actual `WorldState.decisions` status
   update) and `apply_knowledge_corrections` (the Fact/Claim correction
   pathway). Each is diffed for behavioral events same as step 2.
5. **Tier 2** (`update_tier2`) — placed here, not after Planner/
   Response, because Tier 2 only depends on WorldState (already fully
   updated by the corrections above); it doesn't need Planner/Response
   to have run, so it still gets a chance to update even on a turn
   where one of those two later fails. CONDITIONAL (most turns skip the
   LLM call) and NON-BLOCKING (failure already caught inside
   `update_tier2` itself — see
   `engine/specs/understanding-specification-v1.md`).
6. **Planner** (`run_planner`, given `mode`) — on success, resolves
   `effective_mode`: Synthesis's Adaptive mode reports its per-turn
   lens choice on `plan.active_lens`, so Response must be given THAT
   concrete lens, not the literal string `"adaptive"` (which has no
   entry of its own in `RESPONSE_MODE_FOCUS`). Every other mode's
   `effective_mode` is just `mode` unchanged.
7. **Response Generator** (`run_response_generator`, given
   `effective_mode`, `pom`) — the final stage; success returns a fully
   populated `TurnResult`.

Never raises — a failure at any stage is data (a `TurnResult` with
`failed_stage`/`error` set), not an exception the caller has to catch.

## Per-stage failure semantics (`TurnResult`)

`src/orchestrator/schema.py::TurnResult` is the structural fix
described above: every field that ran successfully is populated,
regardless of whether a LATER stage failed. `state` is always present
and accurate — genuinely unchanged only on an Interpretation failure,
reflecting the real committed update for every later failure point.
Unlike every other Sensemaking Engine schema, `TurnResult` is never
produced by an LLM call — Orchestrator makes no LLM call of its own,
which is also why there is deliberately no `prompt.py` in
`src/orchestrator/`.

## Cross-cutting parameters threaded selectively

Several `run_turn` parameters are deliberately threaded to only the ONE
stage whose prompt actually references them, not broadcast to all four:

- `retrieved_context` → Judgment only (Interpretation has no
  cross-turn memory by design; Planner/Response only see it indirectly
  through whatever Judgment surfaces in `supporting_evidence`).
- `mode` → Planner and Response Generator only (Interpretation and
  Judgment are mode-unaware, same reasoning as `phase` staying their
  own separate concern).
- `pom` → Response Generator only, used alongside `state.turn_count` to
  decide whether a mode's POM-seeding clause should fire this turn.
- `on_stage_complete` → an optional synchronous callback invoked once
  per completed stage (`"interpretation"`/`"judgment"`/`"planner"`/
  `"response"`), added for real-time SSE streaming
  (`GET /sessions/{id}/stream`) without changing `run_turn`'s own
  `result = run_turn(...)` contract for every other caller.

Every one of these defaults to a true no-op (`""`/`None`) so every
pre-existing caller (`conversation_runner.py`,
`scripts/run_worldstate_walkthrough.py`, tests) is unaffected by a
parameter it doesn't pass.

## Non-goals

No model-tier selection, no mechanical skip-logic — still deferred, see
"What Orchestrator is, and what it isn't" above. Whole-stage retry is
no longer a non-goal (see Open Questions below) -- narrowly, bounded to
one extra attempt per stage, not the broader "managing retries"
scope. No semantic judgment of any kind — sequencing and resourcing
only.

## Open questions

**Backlog #238 ("Orchestrator: revisit deferred skip-logic/
model-routing scope") — RESOLVED 2026-07-19** (see engine/decisions.md
"Orchestrator: skip-logic/model-routing provisional criteria proposed",
and the full discussion draft at
`engine/specs/orchestrator-skip-logic-model-routing-proposal.md`): asked
to define provisional criteria for both deferred non-goals rather than
leave them closed, the founder chose that non-recommended path.
Skip-logic, traced through the actual pipeline, turned out to be
architecturally unsafe in its literal form (skipping Judgment cascades
to no reply at all, since Response depends on Planner depends on
Judgment) — the recommendation is to close it outright, not provisionally
define it; the two deferred non-goals above still stand as written.
Model-routing has a real, already-available mechanical signal
(`interp.urgency == "high"`) and a scoped-but-not-built plumbing path,
contingent on the founder naming a specific target model and accepting
its cost under CLAUDE.md's standing policy — that naming has not
happened, so no routing behavior exists yet. Treat as closed research,
not an implemented feature.

**Backlog #250 ("Orchestrator: revisit whole-stage retry, distinct from
call-level fallback") — RESOLVED 2026-07-19** (see engine/decisions.md
"Orchestrator: bounded single-stage retry"): the founder was asked
directly whether the honest partial-failure behavior should stay as-is
or gain automatic retry, and chose to add ONE bounded re-attempt per
stage -- `run_turn` now retries a stage exactly once if its first
attempt raises that stage's own `*Error`, via `_with_bounded_retry`
(`src/orchestrator/engine.py`). Still bounded, never a loop, never a
retry of the whole turn or of stages that already succeeded -- a
second failure still returns `failed_stage`/`error` exactly as before.

## Verification

Covered by `tests/test_orchestrator.py`: the fixed stage order,
per-stage failure returning the correct partial `TurnResult` (including
the specific "state IS updated even though Judgment/Planner/Response
failed" regression this extraction was built to fix), the
`on_stage_complete` callback firing once per completed stage, Synthesis
mode's `effective_mode` resolution from `plan.active_lens`, and
`retrieved_context`/`pom` threading to exactly the stages that consume
them.
