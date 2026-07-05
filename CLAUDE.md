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

## Ollama vs. OpenRouter: what each is FOR (standing rule)

**Ollama (`LLM_PROVIDER=ollama`, `llama3.2:3b`) is the reliability/test
harness. OpenRouter (`openrouter/free`) is the quality benchmark.** Don't
conflate the two purposes:

- Ollama answers mechanical questions: does the pipeline run end to end?
  Does the model's output validate against the Pydantic schema? Does
  WorldState evolve correctly turn to turn? Does Planner actually consume
  Judgment's output correctly? A small local model is sufficient for all
  of these -- they're checks about OUR code, not about output quality.
- OpenRouter is where actual output QUALITY gets judged (is this
  primary_problem well-reasoned, is this risk genuinely grounded, etc.) --
  but per the existing `openrouter/free` caveat above, it is NOT reliable
  enough (rate limits, per-call model variance) to serve as the mechanical
  correctness harness. Never treat an `openrouter/free` failure as a
  pipeline bug without checking whether Ollama reproduces it first.

**Do not judge Ollama/llama3.2:3b output against GPT-4o- or Claude-level
quality expectations.** A vague, generic, or unpolished Ollama response
that still validates against the schema and reads as roughly on-topic is
a PASS for its job. Content-quality judgments (is this the *right*
primary_problem, is this risk *well-chosen*) belong to OpenRouter/frontier
model review, not to Ollama runs.
