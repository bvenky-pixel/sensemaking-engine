# Project policies for Claude Code

## LLM model selection (standing rule, not just this repo)

**Only use free-to-use OpenRouter models by default.** Any model that is
not free-tier (i.e. has a real per-token cost) requires the user's
explicit permission before being set as a default or run against without
asking first — this applies to every project, not just this one.

Current default: `openrouter/free` (see `OPENROUTER_MODEL` in
`.env.example`, `src/llm/providers.py` -- the shared provider layer used
by Interpretation, Judgment, Planner, Response, and the evaluation
harness; OpenRouter is the only registered provider). This is
OpenRouter's own auto-router: it randomly selects among whatever free
models are currently available per request, rather than pinning to one
specific free model that might individually be overloaded (see
engine/decisions.md for why this replaced the earlier pinned
`nvidia/nemotron-3-ultra-550b-a55b:free` default, and again for why an
automatic local-Ollama fallback that used to sit behind this was removed
entirely rather than kept as a safety net). Before changing this default
to any model without a `:free` suffix (or away from `openrouter/free`),
ask first — don't just verify the model exists and switch it.

Note: because `openrouter/free` can answer different calls with different
underlying models, it's NOT suitable for anything that depends on model
invariance (e.g. re-running the Judgment v2 evaluation harness in
`src/evaluation/`) -- pin `OPENROUTER_MODEL` to one specific `:free`
model for that instead, with the awareness that a single pinned free
model can itself get rate-limited harder than the rotating pool (see
engine/decisions.md).

`src/instrumentation/pricing.py` treats any OpenRouter model ending in
`:free`, plus `openrouter/free` specifically (listed by exact ID, since
it doesn't match that suffix pattern), as a verified `$0.00`; a paid
model reports its actual per-token cost via the pricing table there (see
that file's docstring for how to add entries and why unlisted models
report unknown cost rather than a guess).

Rate limits on `:free`-suffixed OpenRouter models (confirmed current
2026-07-07): 20 req/minute, 50 req/day with no credits loaded, 1,000/day
once $10+ has been loaded. The full pipeline is 4 LLM calls per
conversation turn (Interpretation, Judgment, Planner, Response) -- any
recurring automated job against this API key (e.g. a scheduled
validation-experiment runner) should be sized with real margin against
the no-credit daily ceiling, not scheduled right up against it; hitting
the limit now surfaces as a hard failure for that turn, since there is no
longer a fallback provider to silently absorb it.
