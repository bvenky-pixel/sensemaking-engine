# Project policies for Claude Code

## LLM model selection (standing rule, not just this repo)

**Only use free-to-use OpenRouter models by default.** Any model that is
not free-tier (i.e. has a real per-token cost) requires the user's
explicit permission before being set as a default or run against without
asking first — this applies to every project, not just this one.

Current default: `nvidia/nemotron-3-ultra-550b-a55b:free` (see
`OPENROUTER_MODEL` in `.env.example`, `src/interpretation/providers.py`,
`src/judgment/providers.py`). Before changing this default to any model
without a `:free` suffix, ask first — don't just verify the model exists
and switch it.

`src/instrumentation/pricing.py` already treats any OpenRouter model
ending in `:free` as a verified `$0.00`; a paid model reports its actual
per-token cost via the pricing table there (see that file's docstring for
how to add entries and why unlisted models report unknown cost rather
than a guess).
