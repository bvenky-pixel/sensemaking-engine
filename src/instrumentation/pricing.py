"""
Approximate USD pricing for estimating LLM call cost from token counts.

IMPORTANT, read before trusting a cost number from this module: this
table is a small, manually-maintained snapshot and WILL go stale --
verify against https://openrouter.ai/models before relying on cost
figures in an actual evaluation run (see
engine/specs/judgment-v2-evaluation-design.md, which depends on
trustworthy cost data). Unlisted models return None (unknown cost)
rather than a guessed number -- an honest "we don't know" is safer than
a wrong number in a study whose whole point is comparing cost/efficiency
across architectures.

OpenRouter models with a `:free` suffix are treated as a verified
$0.00, not an estimate -- that suffix is OpenRouter's own naming
convention for its no-cost tier (confirmed against
https://openrouter.ai/models 2026-07-05), not a guess on our part.

`openrouter/free` (a distinct model ID, no `:free` suffix -- this is
OpenRouter's own auto-router that randomly selects among available free
models per-request, not a single model) is also a verified $0.00,
confirmed via web search against OpenRouter's own pricing page
2026-07-05 ("$0.00/1M input tokens and $0.00/1M output tokens"). Listed
explicitly rather than relying on the `:free`-suffix rule since its own
ID doesn't match that pattern.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

# model -> (input $ per 1M tokens, output $ per 1M tokens). Snapshot only
# -- see module docstring. Add entries as needed; an unlisted, non-":free"
# model is reported as unknown cost, not silently priced at $0.
#
# Refreshed 2026-07-19 (backlog #294, see engine/decisions.md
# "Instrumentation: pricing.py refreshed with production model costs"):
# "openai/gpt-4o-mini" is the original, no-longer-used uniform pin,
# kept for any historical run still referencing it. The three entries
# below are what src/llm/providers.py's per-component model chains
# actually dispatch to in production today (2026-07-18 rebalance, see
# that module's own docstring for the sourcing) -- added because
# engine/decisions.md logged this exact gap producing "unknown cost"
# results in real calibration runs before this fix.
_OPENROUTER_PRICING_PER_MTOK: Dict[str, Tuple[float, float]] = {
    "openai/gpt-4o-mini": (0.15, 0.60),
    "qwen/qwen3-32b": (0.08, 0.28),
    "google/gemini-2.5-flash-lite": (0.10, 0.40),
    "deepseek/deepseek-chat": (0.20, 0.80),
}

# Verified-$0 OpenRouter model IDs that don't match the `:free`-suffix
# naming convention -- see module docstring for how each was confirmed.
_VERIFIED_ZERO_COST_MODELS = {"openrouter/free"}


def estimate_cost_usd(
    provider: str, model: str, prompt_tokens: int, completion_tokens: int
) -> Optional[float]:
    """Returns None when the model isn't in the pricing table and isn't a
    known-free OpenRouter model -- never a guessed number. Cost is based
    on prompt_tokens/completion_tokens only -- this table has no per-
    provider cached-token discount rate, so a cached-token-aware cost
    would have to be guessed; better to slightly overstate cost on a
    cache hit than invent a discount rate (see
    src/instrumentation/usage.py's build_usage docstring)."""
    if model.endswith(":free") or model in _VERIFIED_ZERO_COST_MODELS:
        return 0.0

    pricing = _OPENROUTER_PRICING_PER_MTOK.get(model)
    if pricing is None:
        return None

    input_price_per_mtok, output_price_per_mtok = pricing
    return (prompt_tokens / 1_000_000) * input_price_per_mtok + (
        completion_tokens / 1_000_000
    ) * output_price_per_mtok
