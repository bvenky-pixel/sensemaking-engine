# Latency North Star v1 — a measured baseline, not an estimate

**Status: LIVING TARGET.** First baseline established 2026-07-18, from
direct founder feedback after using Strategize mode live: "latency is a
bitch we have to solve for it in the long run." This doc exists so
future latency work has a real number to aim at and check itself
against, rather than "make it faster" with nothing to measure progress
against — same discipline every other component in this codebase
already applies (Interpretation's calibration dataset, Judgment's
evaluation-design doc).

## Why the pipeline is inherently sequential

Every turn runs through a strict, undocumented-nowhere-else-but-worth-
restating dependency chain: Interpretation → WorldState update →
Judgment → (Tier2, conditional) → Planner → Response. Each stage's
input is the previous stage's own committed output
(`src/orchestrator/engine.py`'s own docstring: "each stage's input is
the previous stage's committed output... no reordering or parallelism
to decide between yet"). That means 2–5 sequential LLM calls per turn,
back to back, with no parallelism available across them without a
genuine redesign of the reasoning core — this isn't a bug, it's the
architecture as designed and calibrated so far.

## Baseline (measured, not estimated)

Pulled directly from the most recent live dispatch of
`scripts/run_worldstate_walkthrough.py` (an 11-turn real conversation,
career-decision transcript, GitHub Actions run `29641474956`,
2026-07-18) — already-paid-for data from this session's own Realign
re-verification round, not a new dispatch. Models in use at the time:
Qwen3-32B for the shared reasoning chain (Interpretation/Judgment/
Tier2/Planner), DeepSeek-Chat for Response (see
`src/llm/providers.py::_DEFAULT_COMPONENT_MODELS`).

**Per-stage latency** (turn 10, a turn that happened to run all 5
possible calls):

| Stage | Latency | Model |
|---|---|---|
| Interpretation | 11.7 s | qwen/qwen3-32b |
| Judgment | 13.8 s | qwen/qwen3-32b |
| Tier2 (conditional) | 14.0 s | qwen/qwen3-32b |
| Planner | 8.5 s | qwen/qwen3-32b |
| Response | 4.9 s | deepseek/deepseek-chat |
| **Turn total (all 5 stages)** | **53.0 s** | |
| **Turn total without Tier2 (the common case, 4 stages)** | **38.9 s** | |

**Whole-conversation aggregate** (11 turns, 51 total LLM calls, one
Interpretation call failed schema validation and stopped that turn
before any downstream call):

- Total latency: 479.3 s
- Average latency per individual LLM call: ~9.4 s
- Average latency per completed turn (Tier2 ran on all 10 completed
  turns in this particular run): ~48 s

## What this means, plainly

A typical turn today takes somewhere in the high 30s to high 40s of
seconds end to end, and a person sees nothing at all until the very
end (see "Streaming" below) — the app looks frozen for that whole
window, then the full answer appears at once.

## The two distinct levers, and which is already scoped

1. **Perceived latency** (how long it FEELS like, independent of total
   wall-clock time): the biggest available win with no architectural
   risk. SSE today (`src/api/server.py`'s `stream_stages`) only
   signals stage-COMPLETION events, not token-level streaming of the
   Response text itself. Streaming Response's own generation
   token-by-token (see the new backlog task for this) turns "frozen,
   then a wall of text" into "watching it get written," the same
   feeling every mainstream chat UI already gives — without changing
   the actual sequential-call architecture at all.
2. **Actual wall-clock latency** (the real ~40-50s number above):
   requires either (a) faster models per stage where quality allows
   (a genuine speed-vs-quality-vs-cost tradeoff, distinct from the
   cost-only optimization already done in "Per-component paid model
   pinning"), or (b) reducing the number of sequential stages a turn
   requires (a real architecture change with real risk — e.g.
   revisiting whether Judgment and Planner could ever merge — not
   something to do without deliberate scoping first).

## Target

**Not yet set.** Picking a concrete number (e.g. "typical turn under
20s wall-clock," "Response's first token within 2s") is a product
decision, not an engineering one to make unilaterally — flagged here
as the next open question rather than guessed at, same "don't invent
a target the evidence doesn't support" discipline this codebase
applies everywhere else.

## Re-measuring

Whenever a latency-affecting change ships (streaming, a model swap,
a stage-count change), re-pull the same two numbers this baseline
used (per-stage latency, whole-conversation average) from the next
live dispatch's usage summary — `src/instrumentation/usage.py` already
prints exactly this breakdown on every live dispatch, so re-measuring
costs nothing beyond the dispatch itself.
