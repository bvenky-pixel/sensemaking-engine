"""
Frontier-model cost COMPARISON -- a calculated field, not a real cost.

For every actual LLM call (regardless of which provider/model really served
it), this computes what the SAME prompt_tokens/completion_tokens would have
cost had they been billed at a fixed set of frontier reference models'
published rates. This answers "how much would this call have cost on a
frontier model like Fable" without needing to actually call one.

Pricing confirmed via the claude-api skill (Anthropic's own current pricing
table, cached 2026-06-24) -- not guessed:

    Model            | Model ID          | Input $/1M | Output $/1M
    Claude Fable 5    | claude-fable-5    | $10.00     | $50.00
    Claude Opus 4.8   | claude-opus-4-8   | $5.00      | $25.00
    Claude Sonnet 5   | claude-sonnet-5   | $3.00      | $15.00
    Claude Haiku 4.5  | claude-haiku-4-5  | $1.00      | $5.00

Claude Sonnet 5 has an introductory rate ($2.00/$10.00 per 1M through
2026-08-31); this table intentionally uses the standard post-intro rate
so the comparison reflects durable pricing, not a temporary promotion.

Like src/instrumentation/pricing.py, this table is a manually-maintained
snapshot and will go stale -- re-verify against Anthropic's current
pricing before trusting these numbers long after 2026-06-24.

This is unrelated to src/instrumentation/pricing.py's estimate_cost_usd,
which estimates what a call actually cost on its real provider. This
module never touches the actual provider or the actual cost -- it's a
hypothetical "what if" figure computed purely from token counts, always
available (no per-provider unknown-cost case), and clearly separate from
the real `estimated_cost_usd` field on LLMUsage.
"""

from __future__ import annotations

from typing import Dict, Tuple

# model_id -> (input $ per 1M tokens, output $ per 1M tokens).
_FRONTIER_PRICING_PER_MTOK: Dict[str, Tuple[float, float]] = {
    "claude-fable-5": (10.00, 50.00),
    "claude-opus-4-8": (5.00, 25.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
}


def estimate_frontier_costs_usd(prompt_tokens: int, completion_tokens: int) -> Dict[str, float]:
    """Returns {model_id: hypothetical_cost_usd} for every model in the
    frontier reference table, given this call's actual token counts.
    Always fully populated (unlike estimate_cost_usd in pricing.py) --
    the reference table is fixed and every entry has known pricing, so
    there's no "unknown model" case to report as None here."""
    return {
        model_id: (prompt_tokens / 1_000_000) * input_price + (completion_tokens / 1_000_000) * output_price
        for model_id, (input_price, output_price) in _FRONTIER_PRICING_PER_MTOK.items()
    }
