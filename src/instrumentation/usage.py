"""
Instrumentation layer: token/cost/latency measurement for every LLM call
in the pipeline (Interpretation, Judgment -- Planner and Response will use
the same abstraction unmodified once they exist). Measurement only --
nothing in this module changes what a provider call sends or what it
returns to its caller; see src/llm/providers.py for how it's wired in (a
try/except around the recording step ensures an instrumentation failure
can never break the actual LLM call).

Disabled by default. Enable with CONFIDANT_TRACK_USAGE=1 (see
.env.example). When disabled, recording is a no-op -- zero behavioral
footprint outside evaluation runs, per explicit constraint.

Shared infrastructure, not duplicated: this module is new, independent
infrastructure that belongs to neither the interpretation nor judgment
package -- both (and src/llm/providers.py itself) depending on one shared
module here doesn't create any coupling concern.

PROVIDER-AGNOSTIC NORMALIZATION (2026-07-05 redesign -- see
engine/decisions.md "Comprehensive LLM usage tracking"): `LLMUsage` now
carries the full set of fields providers can expose (prompt/completion/
reasoning/cached tokens) plus the provider's own raw usage object,
verbatim, in `raw_usage`. Field-name/shape verification for each provider
below was done via web search against each provider's own API docs
2026-07-05, not guessed -- see each extract_*_usage function's docstring
for the source. `reasoning_tokens` and `cached_tokens` are `None` when a
provider/model genuinely doesn't expose them (e.g. a non-reasoning model)
-- NEVER estimated or defaulted to 0, per explicit instruction, since 0
would falsely claim "confirmed zero" where the truth is "unknown."

RELIABILITY METRICS (System Architecture v2 -- Instrumentation, first
component built from engine/specs/system-architecture-v2-specification.md):
`LLMUsage` only ever gets recorded for a call that actually returned
content (see src/llm/providers.py) -- it says nothing about whether that
content went on to parse as JSON or validate against the target schema.
`AttemptRecord`/`record_outcome` fill that gap: every engine.py records
one outcome per provider attempt (success, provider_call_error,
invalid_json, or schema_validation_failed), so "how did Confidant
perform" can finally include "how often did a structured-output attempt
actually succeed," not just token/cost/latency for the attempts that
happened to return SOMETHING. Same off-by-default gating as `LLMUsage`;
same None-honesty rule for `model` (see AttemptRecord below).
"""

from __future__ import annotations

import os
from typing import Dict, List, Literal, NamedTuple, Optional

from pydantic import BaseModel, Field

from src.instrumentation.frontier_pricing import estimate_frontier_costs_usd
from src.instrumentation.pricing import estimate_cost_usd


def is_tracking_enabled() -> bool:
    return os.environ.get("CONFIDANT_TRACK_USAGE", "").strip().lower() in ("1", "true", "yes")


class LLMUsage(BaseModel):
    component: str  # e.g. "Interpretation", "Judgment", "Planner", "Response"
    provider: str  # e.g. "openrouter", "openai", "anthropic"
    model: str

    prompt_tokens: int
    completion_tokens: int
    reasoning_tokens: Optional[int] = None
    cached_tokens: Optional[int] = None

    total_tokens: int

    latency_ms: float

    estimated_cost_usd: Optional[float] = None

    # Calculated field, not real cost: what this call's exact token counts
    # would have cost on a fixed set of frontier reference models (see
    # src/instrumentation/frontier_pricing.py), regardless of which
    # provider/model actually served this call. Always fully populated --
    # unlike estimated_cost_usd, there's no "unknown model" case here since
    # the reference table is fixed.
    frontier_cost_comparison_usd: Dict[str, float] = Field(default_factory=dict)

    # The provider's own usage object, preserved exactly as returned, so a
    # future provider (or a new field an existing provider starts
    # exposing) never requires another instrumentation redesign -- the
    # normalized fields above are for reporting; this is for future
    # compatibility and debugging. None only when a provider has no
    # concept of a discrete usage object to preserve (shouldn't happen in
    # practice; see each call site).
    raw_usage: Optional[dict] = None


def build_usage(
    component: str,
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: float,
    reasoning_tokens: Optional[int] = None,
    cached_tokens: Optional[int] = None,
    raw_usage: Optional[dict] = None,
) -> LLMUsage:
    """total_tokens = prompt_tokens + completion_tokens only --
    reasoning_tokens and cached_tokens are both SUBSETS of completion/
    prompt tokens respectively (per every provider's own accounting, not
    an assumption made here), so adding them again would double-count.
    estimated_cost_usd is likewise computed from prompt/completion tokens
    only -- this codebase's tiny pricing table has no per-provider cached-
    token discount rates, and inventing one would be exactly the kind of
    guessed number this module's docstring and pricing.py's docstring
    both explicitly reject."""
    return LLMUsage(
        component=component,
        provider=provider,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        reasoning_tokens=reasoning_tokens,
        cached_tokens=cached_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        latency_ms=latency_ms,
        estimated_cost_usd=estimate_cost_usd(provider, model, prompt_tokens, completion_tokens),
        frontier_cost_comparison_usd=estimate_frontier_costs_usd(prompt_tokens, completion_tokens),
        raw_usage=raw_usage,
    )


CallOutcome = Literal["success", "provider_call_error", "invalid_json", "schema_validation_failed"]


class AttemptRecord(BaseModel):
    """
    One provider attempt's structured-output outcome -- recorded by each
    engine.py's run_X function at the same decision points it already
    has (the ProviderCallError/JSONDecodeError/ValidationError catches,
    and the successful return), never a new decision point of its own.
    Purely additive: recording an outcome never changes which provider
    is tried next or what gets returned/raised -- that control flow is
    unchanged, per Instrumentation's "never changes cognition" contract.

    `model` is None for every AttemptRecord -- engine.py only knows
    `provider` (the resolve_provider_chain() loop variable); the actual
    resolved model string is internal to call_openrouter in
    src/llm/providers.py and never returned to the caller. This is the
    same None-honesty rule as reasoning_tokens/cached_tokens above:
    genuinely unknown at this call site, not guessed or backfilled by
    reading another record out of the tracker.
    """

    component: str  # e.g. "Interpretation", "Judgment", "Planner", "Response"
    provider: str  # e.g. "openrouter"
    model: Optional[str] = None
    outcome: CallOutcome
    detail: Optional[str] = None  # short failure message; None on success


class ParsedUsage(NamedTuple):
    """Return type for every extract_*_usage function below -- one
    normalized shape regardless of how differently each provider reports
    it. `reasoning_tokens`/`cached_tokens` are `None` when the provider's
    response doesn't include that field at all (not merely zero)."""

    prompt_tokens: int
    completion_tokens: int
    reasoning_tokens: Optional[int]
    cached_tokens: Optional[int]


def extract_openai_compatible_usage(payload: dict) -> ParsedUsage:
    """OpenRouter and OpenAI share this exact usage shape -- both confirmed
    via web search against their own API docs 2026-07-05:
    usage.prompt_tokens / usage.completion_tokens are the top-level
    counts; usage.prompt_tokens_details.cached_tokens and
    usage.completion_tokens_details.reasoning_tokens are present only for
    providers/models that support caching/reasoning (OpenAI's o-series
    reasoning models; OpenRouter passes the same nested shape through for
    models/providers it routes to that support it). Missing/malformed
    top-level usage returns (0, 0) for prompt/completion tokens rather
    than raising -- instrumentation must never break the real call --
    but a present-with-zero `_details` sub-field is still recorded as 0,
    not None, since the provider DID report it; only a genuinely absent
    `_details` object (or absent key within it) yields None."""
    usage = payload.get("usage") or {}
    prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
    completion_tokens = int(usage.get("completion_tokens", 0) or 0)

    reasoning_tokens = None
    completion_details = usage.get("completion_tokens_details")
    if isinstance(completion_details, dict) and "reasoning_tokens" in completion_details:
        reasoning_tokens = completion_details["reasoning_tokens"]

    cached_tokens = None
    prompt_details = usage.get("prompt_tokens_details")
    if isinstance(prompt_details, dict) and "cached_tokens" in prompt_details:
        cached_tokens = prompt_details["cached_tokens"]

    return ParsedUsage(prompt_tokens, completion_tokens, reasoning_tokens, cached_tokens)


def extract_anthropic_usage(payload: dict) -> ParsedUsage:
    """Anthropic's Messages API -- confirmed via web search against
    Anthropic's own docs 2026-07-05: usage.input_tokens/usage.output_tokens
    are always present; usage.cache_read_input_tokens (tokens actually
    served from cache -- a cache HIT) maps to this module's `cached_tokens`
    concept. usage.cache_creation_input_tokens (tokens spent WRITING to
    cache) is a distinct cost, not a hit/reuse discount, so it is
    deliberately NOT folded into `cached_tokens` -- it's preserved as-is
    in `raw_usage` instead, available for anyone who needs it. Anthropic
    has no reasoning_tokens equivalent in its usage object -- extended
    thinking tokens are counted inside output_tokens, not broken out --
    so this always returns None for reasoning_tokens, never a guess.

    Not currently wired into any provider chain (this codebase only calls
    OpenRouter today, see src/llm/providers.py) -- provided ahead of
    an actual Anthropic provider adapter so adding one only means calling
    this function, not redesigning this module."""
    usage = payload.get("usage") or {}
    prompt_tokens = int(usage.get("input_tokens", 0) or 0)
    completion_tokens = int(usage.get("output_tokens", 0) or 0)
    cached_tokens = usage.get("cache_read_input_tokens")
    return ParsedUsage(prompt_tokens, completion_tokens, None, cached_tokens)


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
        self.outcomes: List[AttemptRecord] = []

    def record(self, usage: LLMUsage) -> None:
        if is_tracking_enabled():
            self.records.append(usage)

    def record_outcome(self, outcome: AttemptRecord) -> None:
        if is_tracking_enabled():
            self.outcomes.append(outcome)

    def count(self) -> int:
        return len(self.records)

    def outcome_count(self) -> int:
        return len(self.outcomes)

    def since(self, start_index: int) -> List[LLMUsage]:
        """Records added after `start_index` (from a prior .count()) --
        lets a caller isolate "this turn's" records without needing the
        tracker to know about turn boundaries itself."""
        return self.records[start_index:]

    def outcomes_since(self, start_index: int) -> List[AttemptRecord]:
        """Same idea as `.since()`, for outcomes -- pair with
        `.outcome_count()` the same way `.since()` pairs with `.count()`."""
        return self.outcomes[start_index:]

    def reset(self) -> None:
        self.records = []
        self.outcomes = []

    def summary(
        self,
        records: Optional[List[LLMUsage]] = None,
        outcomes: Optional[List[AttemptRecord]] = None,
    ) -> Dict:
        """
        Structured aggregate stats for the given records (defaults to all
        of them) -- returned as a plain dict/number structure (not
        printed text) so future experiment code can aggregate
        programmatically (average latency, average prompt/completion/
        reasoning tokens, cost by stage, cost by provider, token growth
        over a conversation via `.records`' call order) without ever
        parsing console output. `.records` are plain Pydantic models and
        serialize via `.model_dump()` for anything not covered here.

        reasoning_tokens/cached_tokens aggregates follow the same
        None-honesty rule as the per-record fields: if NO record in the
        group reports a value, the aggregate is None ("unknown/not
        applicable"), not 0 ("confirmed zero"). If at least one record
        reports a value, the aggregate sums the ones that did (silently
        treating a record with None for that field as not contributing,
        since "this call didn't expose it" isn't "this call used zero").

        `reliability` is built from `outcomes` (defaults to all of
        `self.outcomes`), independent of `records`/`rs` above -- an
        AttemptRecord exists for every provider attempt regardless of
        whether it produced a usable LLMUsage record, so the two lists
        are deliberately not the same length or reconciled against each
        other here (see AttemptRecord's docstring for why).
        """
        rs = self.records if records is None else records
        os_ = self.outcomes if outcomes is None else outcomes

        return {
            "calls": len(rs),
            "prompt_tokens": sum(r.prompt_tokens for r in rs),
            "completion_tokens": sum(r.completion_tokens for r in rs),
            "reasoning_tokens": _sum_optional(r.reasoning_tokens for r in rs),
            "cached_tokens": _sum_optional(r.cached_tokens for r in rs),
            "total_tokens": sum(r.total_tokens for r in rs),
            "latency_ms": sum(r.latency_ms for r in rs),
            "avg_latency_ms": (sum(r.latency_ms for r in rs) / len(rs)) if rs else None,
            "avg_prompt_tokens": (sum(r.prompt_tokens for r in rs) / len(rs)) if rs else None,
            "avg_completion_tokens": (sum(r.completion_tokens for r in rs) / len(rs)) if rs else None,
            "avg_reasoning_tokens": _avg_optional(r.reasoning_tokens for r in rs),
            "estimated_cost_usd": _sum_optional(r.estimated_cost_usd for r in rs),
            "cost_fully_known": _cost_fully_known(rs),
            "frontier_cost_comparison_usd": _sum_frontier_costs(rs),
            "by_component": _group_by(rs, key=lambda r: r.component),
            "by_provider": _group_by(rs, key=lambda r: r.provider),
            "reliability": _reliability_summary(os_),
        }


default_tracker = UsageTracker()


def _sum_optional(values) -> Optional[int]:
    values = list(values)
    known = [v for v in values if v is not None]
    return sum(known) if known else None


def _avg_optional(values) -> Optional[float]:
    values = list(values)
    known = [v for v in values if v is not None]
    return (sum(known) / len(known)) if known else None


def _cost_fully_known(records: List[LLMUsage]) -> bool:
    return len(records) > 0 and all(r.estimated_cost_usd is not None for r in records)


def _reliability_summary(outcomes: List[AttemptRecord]) -> Dict:
    """Attempt/success/failure counts overall and per component/provider.
    `success_rate` is None (not 0.0) when there are zero attempts --
    "no data" and "confirmed 0% success" are different claims."""
    attempts = len(outcomes)
    successes = sum(1 for o in outcomes if o.outcome == "success")
    failures = attempts - successes

    failures_by_type: Dict[str, int] = {}
    for o in outcomes:
        if o.outcome != "success":
            failures_by_type[o.outcome] = failures_by_type.get(o.outcome, 0) + 1

    return {
        "attempts": attempts,
        "successes": successes,
        "failures": failures,
        "success_rate": (successes / attempts) if attempts else None,
        "failures_by_type": failures_by_type,
        "by_component": _group_outcomes_by(outcomes, key=lambda o: o.component),
        "by_provider": _group_outcomes_by(outcomes, key=lambda o: o.provider),
    }


def _group_outcomes_by(outcomes: List[AttemptRecord], key) -> Dict[str, Dict]:
    groups: Dict[str, List[AttemptRecord]] = {}
    for o in outcomes:
        groups.setdefault(key(o), []).append(o)

    result: Dict[str, Dict] = {}
    for group_key, group_outcomes in groups.items():
        attempts = len(group_outcomes)
        successes = sum(1 for o in group_outcomes if o.outcome == "success")
        result[group_key] = {
            "attempts": attempts,
            "successes": successes,
            "failures": attempts - successes,
            "success_rate": (successes / attempts) if attempts else None,
        }
    return result


def _sum_frontier_costs(records: List[LLMUsage]) -> Dict[str, float]:
    """Per-model sum of frontier_cost_comparison_usd across records --
    always fully populated per model_id (see frontier_pricing.py), so
    this is a plain sum, not an optional-aware one."""
    totals: Dict[str, float] = {}
    for r in records:
        for model_id, cost in r.frontier_cost_comparison_usd.items():
            totals[model_id] = totals.get(model_id, 0.0) + cost
    return totals


def _group_by(records: List[LLMUsage], key) -> Dict[str, Dict]:
    groups: Dict[str, Dict] = {}
    for r in records:
        bucket = groups.setdefault(
            key(r),
            {
                "calls": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "reasoning_tokens": [],
                "cached_tokens": [],
                "total_tokens": 0,
                "latency_ms": 0.0,
                "_costs": [],
                "frontier_cost_comparison_usd": {},
            },
        )
        bucket["calls"] += 1
        bucket["prompt_tokens"] += r.prompt_tokens
        bucket["completion_tokens"] += r.completion_tokens
        if r.reasoning_tokens is not None:
            bucket["reasoning_tokens"].append(r.reasoning_tokens)
        if r.cached_tokens is not None:
            bucket["cached_tokens"].append(r.cached_tokens)
        bucket["total_tokens"] += r.total_tokens
        bucket["latency_ms"] += r.latency_ms
        if r.estimated_cost_usd is not None:
            bucket["_costs"].append(r.estimated_cost_usd)
        for model_id, cost in r.frontier_cost_comparison_usd.items():
            bucket["frontier_cost_comparison_usd"][model_id] = (
                bucket["frontier_cost_comparison_usd"].get(model_id, 0.0) + cost
            )
    for bucket in groups.values():
        reasoning = bucket.pop("reasoning_tokens")
        cached = bucket.pop("cached_tokens")
        costs = bucket.pop("_costs")
        bucket["reasoning_tokens"] = sum(reasoning) if reasoning else None
        bucket["cached_tokens"] = sum(cached) if cached else None
        bucket["estimated_cost_usd"] = sum(costs) if costs else None
    return groups


def _fmt_optional_int(value: Optional[int]) -> str:
    return f"{value:,}" if value is not None else "N/A"


def _fmt_cost(value: Optional[float]) -> str:
    return f"${value:.4f}" if value is not None else "N/A"


def _fmt_frontier_costs(costs: Dict[str, float]) -> str:
    if not costs:
        return "N/A"
    return ", ".join(f"{model_id}=${cost:.4f}" for model_id, cost in costs.items())


def print_turn_summary(
    records: List[LLMUsage], outcomes: Optional[List[AttemptRecord]] = None
) -> None:
    """
    Console output: one block per component (in first-seen order), then a
    Pipeline Total block. Every field that isn't available for a given
    group (e.g. no reasoning_tokens because the model doesn't do
    reasoning) prints "N/A", never a guessed or silently-zeroed value.
    No-op only if BOTH `records` and `outcomes` are empty (e.g. tracking
    disabled, or nothing recorded at all).

    `outcomes`: optional AttemptRecord list (e.g. `tracker.outcomes_since(...)`)
    -- when given, a "Reliability" line is added per component and to
    Pipeline Total (attempts/successes/failures). Omitted entirely if not
    passed, so existing callers that only track LLMUsage keep working
    unchanged.

    A component can have outcomes with zero LLMUsage records -- every
    provider attempt failed at the call-error stage, so nothing ever
    returned content to record token/cost/latency for (see
    src/llm/providers.py). That component still gets a printed block here,
    token/cost fields shown as "N/A" rather than silently vanishing from
    the report, since its reliability data (real, recorded failures) is
    exactly the thing this report exists to surface.
    """
    if not records and not outcomes:
        return

    order: List[str] = []
    grouped: Dict[str, List[LLMUsage]] = {}
    for r in records:
        grouped.setdefault(r.component, []).append(r)
        if r.component not in order:
            order.append(r.component)

    outcomes_by_component: Dict[str, List[AttemptRecord]] = {}
    if outcomes:
        for o in outcomes:
            outcomes_by_component.setdefault(o.component, []).append(o)
            if o.component not in order:
                order.append(o.component)

    for component in order:
        crs = grouped.get(component)
        print(f"\n{component}")
        if crs:
            provider = crs[-1].provider
            model = crs[-1].model
            prompt_tokens = sum(r.prompt_tokens for r in crs)
            completion_tokens = sum(r.completion_tokens for r in crs)
            reasoning_tokens = _sum_optional(r.reasoning_tokens for r in crs)
            cached_tokens = _sum_optional(r.cached_tokens for r in crs)
            total_tokens = sum(r.total_tokens for r in crs)
            latency_s = sum(r.latency_ms for r in crs) / 1000
            cost = _sum_optional(r.estimated_cost_usd for r in crs)
            frontier_costs = _sum_frontier_costs(crs)

            print(f"- Provider: {provider}")
            print(f"- Model: {model}")
            print(f"- Prompt Tokens: {prompt_tokens:,}")
            print(f"- Completion Tokens: {completion_tokens:,}")
            print(f"- Reasoning Tokens: {_fmt_optional_int(reasoning_tokens)}")
            print(f"- Cached Tokens: {_fmt_optional_int(cached_tokens)}")
            print(f"- Total Tokens: {total_tokens:,}")
            print(f"- Latency: {latency_s:.1f} s")
            print(f"- Estimated Cost: {_fmt_cost(cost)}")
            print(f"- Frontier Cost Comparison: {_fmt_frontier_costs(frontier_costs)}")
        else:
            # Every provider attempt for this component failed before
            # returning content -- no LLMUsage exists to report.
            print("- Provider: N/A (no call returned content)")
        if component in outcomes_by_component:
            print(f"- Reliability: {_fmt_reliability(outcomes_by_component[component])}")

    if records:
        total_prompt = sum(r.prompt_tokens for r in records)
        total_completion = sum(r.completion_tokens for r in records)
        total_reasoning = _sum_optional(r.reasoning_tokens for r in records)
        total_cached = _sum_optional(r.cached_tokens for r in records)
        total_tokens = sum(r.total_tokens for r in records)
        total_latency_s = sum(r.latency_ms for r in records) / 1000
        total_cost = _sum_optional(r.estimated_cost_usd for r in records)
        total_frontier_costs = _sum_frontier_costs(records)

        print("\nPipeline Total")
        print(f"- Prompt Tokens: {total_prompt:,}")
        print(f"- Completion Tokens: {total_completion:,}")
        print(f"- Reasoning Tokens: {_fmt_optional_int(total_reasoning)}")
        print(f"- Cached Tokens: {_fmt_optional_int(total_cached)}")
        print(f"- Total Tokens: {total_tokens:,}")
        print(f"- Total Cost: {_fmt_cost(total_cost)}")
        print(f"- Frontier Cost Comparison: {_fmt_frontier_costs(total_frontier_costs)}")
        print(f"- Total Latency: {total_latency_s:.1f} s")
    else:
        print("\nPipeline Total")
        print("- Tokens/Cost/Latency: N/A (no call returned content)")
    if outcomes:
        print(f"- Reliability: {_fmt_reliability(outcomes)}")


def _fmt_reliability(outcomes: List[AttemptRecord]) -> str:
    attempts = len(outcomes)
    successes = sum(1 for o in outcomes if o.outcome == "success")
    rate = (successes / attempts * 100) if attempts else 0.0
    return f"{successes}/{attempts} succeeded ({rate:.0f}%)"
