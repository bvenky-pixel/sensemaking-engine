"""
Instrumentation layer: token/cost/latency measurement for every LLM call
in the pipeline (Interpretation, Judgment). Measurement only -- nothing
in this module changes what a provider call sends or what it returns to
its caller; see src/interpretation/providers.py and
src/judgment/providers.py for how it's wired in (a try/except around the
recording step ensures an instrumentation failure can never break the
actual LLM call).

Disabled by default. Enable with CONFIDANT_TRACK_USAGE=1 (see
.env.example). When disabled, recording is a no-op -- zero behavioral
footprint outside evaluation runs, per explicit constraint.

Shared by both providers.py files rather than duplicated: unlike
providers.py itself (deliberately duplicated across interpretation/ and
judgment/ to avoid coupling judgment to frozen interpretation code), this
module is new, independent infrastructure that belongs to neither
package -- both depending on one shared module here doesn't reintroduce
that coupling concern.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel

from src.instrumentation.pricing import estimate_cost_usd


def is_tracking_enabled() -> bool:
    return os.environ.get("CONFIDANT_TRACK_USAGE", "").strip().lower() in ("1", "true", "yes")


class LLMUsage(BaseModel):
    component: str  # e.g. "Interpretation", "Judgment"
    provider: str  # e.g. "openrouter", "ollama"
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_ms: float
    estimated_cost_usd: Optional[float] = None


def build_usage(
    component: str,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: float,
) -> LLMUsage:
    return LLMUsage(
        component=component,
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        latency_ms=latency_ms,
        estimated_cost_usd=estimate_cost_usd(provider, model, input_tokens, output_tokens),
    )


def extract_openai_compatible_usage(payload: dict) -> Tuple[int, int]:
    """OpenRouter (and any OpenAI-compatible response) -- usage.prompt_tokens
    / usage.completion_tokens. Missing/malformed usage returns (0, 0)
    rather than raising -- instrumentation must never break the real call."""
    usage = payload.get("usage") or {}
    return int(usage.get("prompt_tokens", 0) or 0), int(usage.get("completion_tokens", 0) or 0)


def extract_ollama_usage(payload: dict) -> Tuple[int, int]:
    """Ollama's native /api/chat -- prompt_eval_count / eval_count."""
    return int(payload.get("prompt_eval_count", 0) or 0), int(payload.get("eval_count", 0) or 0)


class UsageTracker:
    """
    Accumulates LLMUsage records for one run. Instantiate a fresh one per
    conversation/experiment condition to keep aggregates from bleeding
    across runs -- `default_tracker` below is a shared instance for
    convenience in interactive scripts (conversation_runner.py); the
    future experiment framework should create its own per run instead of
    relying on the shared default.
    """

    def __init__(self) -> None:
        self.records: List[LLMUsage] = []

    def record(self, usage: LLMUsage) -> None:
        if is_tracking_enabled():
            self.records.append(usage)

    def count(self) -> int:
        return len(self.records)

    def since(self, start_index: int) -> List[LLMUsage]:
        """Records added after `start_index` (from a prior .count()) --
        lets a caller isolate "this turn's" records without needing the
        tracker to know about turn boundaries itself."""
        return self.records[start_index:]

    def reset(self) -> None:
        self.records = []

    def summary(self, records: Optional[List[LLMUsage]] = None) -> Dict:
        """
        Structured aggregate stats for the given records (defaults to all
        of them) -- the experiment framework should read this (or build
        its own aggregation over `.records`, which are plain Pydantic
        models and serialize via `.model_dump()`), never parse console
        output.
        """
        rs = self.records if records is None else records

        known_costs = [r.estimated_cost_usd for r in rs if r.estimated_cost_usd is not None]
        cost_total = sum(known_costs) if known_costs else None
        cost_fully_known = len(known_costs) == len(rs) and len(rs) > 0

        by_component: Dict[str, Dict] = {}
        for r in rs:
            bucket = by_component.setdefault(
                r.component,
                {
                    "calls": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "latency_ms": 0.0,
                    "_known_costs": [],
                },
            )
            bucket["calls"] += 1
            bucket["input_tokens"] += r.input_tokens
            bucket["output_tokens"] += r.output_tokens
            bucket["total_tokens"] += r.total_tokens
            bucket["latency_ms"] += r.latency_ms
            if r.estimated_cost_usd is not None:
                bucket["_known_costs"].append(r.estimated_cost_usd)
        for bucket in by_component.values():
            costs = bucket.pop("_known_costs")
            bucket["estimated_cost_usd"] = sum(costs) if costs else None

        return {
            "calls": len(rs),
            "input_tokens": sum(r.input_tokens for r in rs),
            "output_tokens": sum(r.output_tokens for r in rs),
            "total_tokens": sum(r.total_tokens for r in rs),
            "latency_ms": sum(r.latency_ms for r in rs),
            "estimated_cost_usd": cost_total,
            "cost_fully_known": cost_fully_known,
            "by_component": by_component,
        }


default_tracker = UsageTracker()


def _format_cost(records: List[LLMUsage]) -> str:
    costs = [r.estimated_cost_usd for r in records if r.estimated_cost_usd is not None]
    if not costs:
        return "unknown"
    return f"${sum(costs):.4f}"


def print_turn_summary(records: List[LLMUsage]) -> None:
    """
    Console output matching the requested format: one block per
    component (in first-seen order), then a Pipeline Total block. No-op
    if `records` is empty (e.g. tracking disabled, or nothing recorded).
    """
    if not records:
        return

    order: List[str] = []
    grouped: Dict[str, List[LLMUsage]] = {}
    for r in records:
        grouped.setdefault(r.component, []).append(r)
        if r.component not in order:
            order.append(r.component)

    for component in order:
        crs = grouped[component]
        model = crs[-1].model
        input_tokens = sum(r.input_tokens for r in crs)
        output_tokens = sum(r.output_tokens for r in crs)
        total_tokens = sum(r.total_tokens for r in crs)
        latency_s = sum(r.latency_ms for r in crs) / 1000

        print(f"\n{component}")
        print(f"- Model: {model}")
        print(f"- Input: {input_tokens:,}")
        print(f"- Output: {output_tokens:,}")
        print(f"- Total: {total_tokens:,}")
        print(f"- Latency: {latency_s:.1f} s")
        print(f"- Cost: {_format_cost(crs)}")

    total_input = sum(r.input_tokens for r in records)
    total_output = sum(r.output_tokens for r in records)
    total_tokens = sum(r.total_tokens for r in records)
    total_latency_s = sum(r.latency_ms for r in records) / 1000

    print("\nPipeline Total")
    print(f"- Input: {total_input:,}")
    print(f"- Output: {total_output:,}")
    print(f"- Total Tokens: {total_tokens:,}")
    print(f"- Total Cost: {_format_cost(records)}")
    print(f"- Total Latency: {total_latency_s:.1f} s")
