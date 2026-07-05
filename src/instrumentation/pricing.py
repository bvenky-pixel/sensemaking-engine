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

Ollama is always $0.00 -- local inference has no per-token API charge,
this is a fact, not an estimate.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

# model -> (input $ per 1M tokens, output $ per 1M tokens). Snapshot only
# -- see module docstring. Add entries as needed; an unlisted model is
# reported as unknown cost, not silently priced at $0.
_OPENROUTER_PRICING_PER_MTOK: Dict[str, Tuple[float, float]] = {
    "openai/gpt-4o-mini": (0.15, 0.60),
}


def estimate_cost_usd(
    provider: str, model: str, input_tokens: int, output_tokens: int
) -> Optional[float]:
    """Returns None when the model isn't in the pricing table -- never a
    guessed number."""
    if provider == "ollama":
        return 0.0

    pricing = _OPENROUTER_PRICING_PER_MTOK.get(model)
    if pricing is None:
        return None

    input_price_per_mtok, output_price_per_mtok = pricing
    return (input_tokens / 1_000_000) * input_price_per_mtok + (
        output_tokens / 1_000_000
    ) * output_price_per_mtok
