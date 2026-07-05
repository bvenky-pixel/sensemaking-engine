# Project policies for Claude Code

## LLM model selection (standing rule, not just this repo)

**Only use free-to-use OpenRouter models by default.** Any model that is
not free-tier (i.e. has a real per-token cost) requires the user's
explicit permission before being set as a default or run against without
asking first — this applies to every project, not just this one.

Current default: `openrouter/free` (see `OPENROUTER_MODEL` in
`.env.example`, `src/llm/providers.py` -- the shared provider layer used
by Interpretation, Judgment, and the evaluation harness). This is
OpenRouter's own auto-router: it randomly selects among whatever free
models are currently available per request, rather than pinning to one
specific free model that might individually be overloaded (see
engine/decisions.md for why this replaced the earlier pinned
`nvidia/nemotron-3-ultra-550b-a55b:free` default). Before changing this
default to any model without a `:free` suffix (or away from
`openrouter/free`), ask first — don't just verify the model exists and
switch it.

Note: because `openrouter/free` can answer different calls with different
underlying models, it's NOT suitable for anything that depends on model
invariance (e.g. re-running the Judgment v2 evaluation harness in
`src/evaluation/`) -- pin `OPENROUTER_MODEL` to one specific `:free`
model for that instead.

`src/instrumentation/pricing.py` treats any OpenRouter model ending in
`:free`, plus `openrouter/free` specifically (listed by exact ID, since
it doesn't match that suffix pattern), as a verified `$0.00`; a paid
model reports its actual per-token cost via the pricing table there (see
that file's docstring for how to add entries and why unlisted models
report unknown cost rather than a guess).
