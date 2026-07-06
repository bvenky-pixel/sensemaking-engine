"""
Tests for the instrumentation layer (src/instrumentation/usage.py,
pricing.py) -- all deterministic, no LLM calls needed. Covers: provider-
agnostic usage extraction (OpenRouter/OpenAI-compatible, Anthropic,
Ollama), the None-vs-zero honesty rule for reasoning/cached tokens, raw
payload preservation, cost estimation, tracker aggregation (including the
new by_provider breakdown and average stats), and the disabled-by-default
behavior that's the whole point of "measurement only, no behavior change
outside evaluation runs."
"""

from __future__ import annotations

import os

import pytest

from src.instrumentation.frontier_pricing import estimate_frontier_costs_usd
from src.instrumentation.pricing import estimate_cost_usd
from src.instrumentation.usage import (
    AttemptRecord,
    LLMUsage,
    ParsedUsage,
    UsageTracker,
    build_usage,
    extract_anthropic_usage,
    extract_ollama_usage,
    extract_openai_compatible_usage,
    is_tracking_enabled,
    print_turn_summary,
)


@pytest.fixture(autouse=True)
def _clear_tracking_env():
    """Every test controls CONFIDANT_TRACK_USAGE explicitly rather than
    inheriting whatever the shell happened to have set."""
    original = os.environ.pop("CONFIDANT_TRACK_USAGE", None)
    yield
    if original is not None:
        os.environ["CONFIDANT_TRACK_USAGE"] = original
    else:
        os.environ.pop("CONFIDANT_TRACK_USAGE", None)


def test_tracking_disabled_by_default():
    assert is_tracking_enabled() is False


def test_tracking_enabled_via_env_var():
    os.environ["CONFIDANT_TRACK_USAGE"] = "1"
    assert is_tracking_enabled() is True
    os.environ["CONFIDANT_TRACK_USAGE"] = "true"
    assert is_tracking_enabled() is True
    os.environ["CONFIDANT_TRACK_USAGE"] = "0"
    assert is_tracking_enabled() is False


def test_tracker_records_nothing_when_disabled():
    tracker = UsageTracker()
    usage = build_usage("Interpretation", "openrouter", "openai/gpt-4o-mini", 100, 50, 500.0)
    tracker.record(usage)
    assert tracker.records == [], "recording must be a no-op when CONFIDANT_TRACK_USAGE is unset"


def test_tracker_records_when_enabled():
    os.environ["CONFIDANT_TRACK_USAGE"] = "1"
    tracker = UsageTracker()
    usage = build_usage("Interpretation", "openrouter", "openai/gpt-4o-mini", 100, 50, 500.0)
    tracker.record(usage)
    assert len(tracker.records) == 1
    assert tracker.records[0].total_tokens == 150


def test_build_usage_defaults_reasoning_and_cached_to_none_not_zero():
    """A caller that doesn't pass reasoning_tokens/cached_tokens (e.g.
    Ollama, which has no such concept) must get None, not a silently
    assumed 0 -- 0 would falsely claim "confirmed zero usage"."""
    usage = build_usage("Interpretation", "ollama", "llama3.2:3b", 100, 50, 500.0)
    assert usage.reasoning_tokens is None
    assert usage.cached_tokens is None
    assert usage.raw_usage is None


def test_build_usage_total_tokens_excludes_reasoning_and_cached_to_avoid_double_counting():
    """reasoning_tokens is a SUBSET of completion_tokens and cached_tokens
    is a SUBSET of prompt_tokens (per every provider's own accounting) --
    total_tokens must not add them again."""
    usage = build_usage(
        "Judgment", "openai", "o1", 100, 50, 500.0, reasoning_tokens=30, cached_tokens=20
    )
    assert usage.total_tokens == 150


def test_build_usage_preserves_raw_usage_verbatim():
    raw = {"prompt_tokens": 100, "completion_tokens": 50, "some_future_field": 42}
    usage = build_usage("Interpretation", "openrouter", "m", 100, 50, 500.0, raw_usage=raw)
    assert usage.raw_usage == raw


# --- OpenRouter/OpenAI-compatible extraction ---


def test_extract_openai_compatible_usage_basic_fields():
    parsed = extract_openai_compatible_usage(
        {"usage": {"prompt_tokens": 10, "completion_tokens": 5}}
    )
    assert parsed == ParsedUsage(10, 5, None, None)


def test_extract_openai_compatible_usage_handles_missing_usage():
    assert extract_openai_compatible_usage({}) == ParsedUsage(0, 0, None, None)
    assert extract_openai_compatible_usage({"usage": {}}) == ParsedUsage(0, 0, None, None)


def test_extract_openai_compatible_usage_reasoning_and_cached_tokens_present():
    """Confirmed field names via OpenAI's/OpenRouter's own API docs:
    usage.completion_tokens_details.reasoning_tokens,
    usage.prompt_tokens_details.cached_tokens."""
    payload = {
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 80,
            "completion_tokens_details": {"reasoning_tokens": 30},
            "prompt_tokens_details": {"cached_tokens": 40},
        }
    }
    parsed = extract_openai_compatible_usage(payload)
    assert parsed == ParsedUsage(100, 80, 30, 40)


def test_extract_openai_compatible_usage_zero_is_not_none_when_field_present():
    """A model that supports reasoning but used none this call reports
    reasoning_tokens: 0 -- that's real data (confirmed zero), not the
    same as the field being absent (unknown)."""
    payload = {
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 80,
            "completion_tokens_details": {"reasoning_tokens": 0},
        }
    }
    parsed = extract_openai_compatible_usage(payload)
    assert parsed.reasoning_tokens == 0
    assert parsed.reasoning_tokens is not None


def test_extract_openai_compatible_usage_absent_details_object_yields_none():
    payload = {"usage": {"prompt_tokens": 100, "completion_tokens": 80}}
    parsed = extract_openai_compatible_usage(payload)
    assert parsed.reasoning_tokens is None
    assert parsed.cached_tokens is None


# --- Anthropic extraction ---


def test_extract_anthropic_usage_basic_fields():
    payload = {"usage": {"input_tokens": 200, "output_tokens": 90}}
    assert extract_anthropic_usage(payload) == ParsedUsage(200, 90, None, None)


def test_extract_anthropic_usage_cache_read_maps_to_cached_tokens():
    """Confirmed via Anthropic's own docs: cache_read_input_tokens is a
    cache HIT -- maps to this module's `cached_tokens`. Anthropic has no
    reasoning_tokens field at all (extended thinking is inside
    output_tokens), so that's always None for this provider."""
    payload = {
        "usage": {
            "input_tokens": 200,
            "output_tokens": 90,
            "cache_creation_input_tokens": 500,
            "cache_read_input_tokens": 150,
        }
    }
    parsed = extract_anthropic_usage(payload)
    assert parsed.prompt_tokens == 200
    assert parsed.completion_tokens == 90
    assert parsed.reasoning_tokens is None
    assert parsed.cached_tokens == 150  # cache_read, not cache_creation


def test_extract_anthropic_usage_handles_missing_usage():
    assert extract_anthropic_usage({}) == ParsedUsage(0, 0, None, None)


# --- Ollama extraction ---


def test_extract_ollama_usage_handles_missing_fields():
    assert extract_ollama_usage({"prompt_eval_count": 500, "eval_count": 120}) == ParsedUsage(
        500, 120, None, None
    )
    assert extract_ollama_usage({}) == ParsedUsage(0, 0, None, None)


def test_extract_ollama_usage_never_reports_reasoning_or_cached_tokens():
    """Ollama's API has no concept of either -- always None, never a guess."""
    parsed = extract_ollama_usage({"prompt_eval_count": 10, "eval_count": 5})
    assert parsed.reasoning_tokens is None
    assert parsed.cached_tokens is None


# --- Cost estimation (unchanged behavior, renamed params) ---


def test_ollama_cost_is_always_zero_not_unknown():
    assert estimate_cost_usd("ollama", "llama3.2:3b", 1000, 1000) == 0.0


def test_unknown_openrouter_model_cost_is_none_not_a_guess():
    assert estimate_cost_usd("openrouter", "some/unlisted-model", 1000, 1000) is None


def test_known_openrouter_model_cost_computed_from_pricing_table():
    cost = estimate_cost_usd("openrouter", "openai/gpt-4o-mini", 1_000_000, 1_000_000)
    assert cost == pytest.approx(0.15 + 0.60)


def test_openrouter_free_suffix_model_cost_is_verified_zero_not_unknown():
    cost = estimate_cost_usd("openrouter", "nvidia/nemotron-3-ultra-550b-a55b:free", 1000, 1000)
    assert cost == 0.0


def test_openrouter_free_router_cost_is_verified_zero_not_unknown():
    cost = estimate_cost_usd("openrouter", "openrouter/free", 1000, 1000)
    assert cost == 0.0


# --- Tracker aggregation ---


def test_tracker_since_isolates_records_added_after_a_checkpoint():
    os.environ["CONFIDANT_TRACK_USAGE"] = "1"
    tracker = UsageTracker()
    tracker.record(build_usage("Interpretation", "openrouter", "m", 10, 5, 100.0))
    checkpoint = tracker.count()
    tracker.record(build_usage("Judgment", "openrouter", "m", 20, 10, 200.0))

    since = tracker.since(checkpoint)
    assert len(since) == 1
    assert since[0].component == "Judgment"


def test_summary_aggregates_across_components_and_reports_cost_correctly():
    os.environ["CONFIDANT_TRACK_USAGE"] = "1"
    tracker = UsageTracker()
    tracker.record(build_usage("Interpretation", "openrouter", "openai/gpt-4o-mini", 812, 267, 1400.0))
    tracker.record(build_usage("Judgment", "openrouter", "openai/gpt-4o-mini", 1354, 194, 1700.0))

    summary = tracker.summary()
    expected_cost = estimate_cost_usd(
        "openrouter", "openai/gpt-4o-mini", 812, 267
    ) + estimate_cost_usd("openrouter", "openai/gpt-4o-mini", 1354, 194)

    assert summary["prompt_tokens"] == 812 + 1354
    assert summary["completion_tokens"] == 267 + 194
    assert summary["total_tokens"] == (812 + 267) + (1354 + 194)
    assert summary["cost_fully_known"] is True
    assert summary["estimated_cost_usd"] == pytest.approx(expected_cost)
    assert set(summary["by_component"].keys()) == {"Interpretation", "Judgment"}
    assert summary["by_component"]["Interpretation"]["prompt_tokens"] == 812


def test_summary_reports_unknown_cost_honestly_when_model_unpriced():
    os.environ["CONFIDANT_TRACK_USAGE"] = "1"
    tracker = UsageTracker()
    tracker.record(build_usage("Interpretation", "openrouter", "some/unlisted-model", 100, 50, 100.0))

    summary = tracker.summary()
    assert summary["cost_fully_known"] is False
    assert summary["estimated_cost_usd"] is None


def test_summary_reasoning_and_cached_tokens_none_when_no_record_reports_them():
    os.environ["CONFIDANT_TRACK_USAGE"] = "1"
    tracker = UsageTracker()
    tracker.record(build_usage("Interpretation", "ollama", "llama3.2:3b", 100, 50, 100.0))

    summary = tracker.summary()
    assert summary["reasoning_tokens"] is None
    assert summary["cached_tokens"] is None


def test_summary_reasoning_and_cached_tokens_sum_known_values_ignoring_unreported_calls():
    os.environ["CONFIDANT_TRACK_USAGE"] = "1"
    tracker = UsageTracker()
    tracker.record(
        build_usage("Interpretation", "openai", "o1", 100, 80, 100.0, reasoning_tokens=30, cached_tokens=10)
    )
    tracker.record(build_usage("Judgment", "ollama", "llama3.2:3b", 50, 20, 100.0))  # no reasoning/cached

    summary = tracker.summary()
    assert summary["reasoning_tokens"] == 30
    assert summary["cached_tokens"] == 10


def test_summary_includes_average_stats():
    os.environ["CONFIDANT_TRACK_USAGE"] = "1"
    tracker = UsageTracker()
    tracker.record(build_usage("Interpretation", "openrouter", "m", 100, 50, 1000.0))
    tracker.record(build_usage("Judgment", "openrouter", "m", 200, 100, 3000.0))

    summary = tracker.summary()
    assert summary["avg_latency_ms"] == pytest.approx(2000.0)
    assert summary["avg_prompt_tokens"] == pytest.approx(150.0)
    assert summary["avg_completion_tokens"] == pytest.approx(75.0)


def test_summary_includes_by_provider_breakdown():
    os.environ["CONFIDANT_TRACK_USAGE"] = "1"
    tracker = UsageTracker()
    tracker.record(build_usage("Interpretation", "openrouter", "m", 100, 50, 1000.0))
    tracker.record(build_usage("Judgment", "ollama", "llama3.2:3b", 50, 20, 500.0))

    summary = tracker.summary()
    assert set(summary["by_provider"].keys()) == {"openrouter", "ollama"}
    assert summary["by_provider"]["openrouter"]["calls"] == 1
    assert summary["by_provider"]["ollama"]["calls"] == 1
    assert summary["by_provider"]["ollama"]["estimated_cost_usd"] == 0.0


# --- Frontier cost comparison (calculated field, not real cost) ---


def test_estimate_frontier_costs_usd_covers_all_reference_models():
    costs = estimate_frontier_costs_usd(1_000_000, 1_000_000)
    assert set(costs.keys()) == {
        "claude-fable-5",
        "claude-opus-4-8",
        "claude-sonnet-5",
        "claude-haiku-4-5",
    }
    # 1M prompt + 1M completion tokens at each model's published rate
    assert costs["claude-fable-5"] == pytest.approx(10.00 + 50.00)
    assert costs["claude-opus-4-8"] == pytest.approx(5.00 + 25.00)
    assert costs["claude-sonnet-5"] == pytest.approx(3.00 + 15.00)
    assert costs["claude-haiku-4-5"] == pytest.approx(1.00 + 5.00)


def test_estimate_frontier_costs_usd_scales_with_tokens():
    costs = estimate_frontier_costs_usd(500_000, 0)
    assert costs["claude-fable-5"] == pytest.approx(5.00)  # half of the 1M input rate


def test_build_usage_always_populates_frontier_cost_comparison():
    """Unlike estimated_cost_usd (which can be None for an unpriced/
    unlisted model), frontier_cost_comparison_usd is always fully
    populated -- it's computed purely from token counts against a fixed
    reference table, independent of which provider/model actually served
    the call."""
    usage = build_usage("Interpretation", "openrouter", "some/unlisted-model", 100, 50, 500.0)
    assert usage.estimated_cost_usd is None  # real cost: unknown
    assert len(usage.frontier_cost_comparison_usd) == 4  # comparison: always known


def test_summary_sums_frontier_cost_comparison_across_records():
    os.environ["CONFIDANT_TRACK_USAGE"] = "1"
    tracker = UsageTracker()
    tracker.record(build_usage("Interpretation", "openrouter", "m", 1_000_000, 0, 100.0))
    tracker.record(build_usage("Judgment", "openrouter", "m", 1_000_000, 0, 100.0))

    summary = tracker.summary()
    assert summary["frontier_cost_comparison_usd"]["claude-fable-5"] == pytest.approx(20.00)


def test_by_component_breakdown_includes_frontier_cost_comparison():
    os.environ["CONFIDANT_TRACK_USAGE"] = "1"
    tracker = UsageTracker()
    tracker.record(build_usage("Interpretation", "openrouter", "m", 1_000_000, 0, 100.0))

    summary = tracker.summary()
    interp = summary["by_component"]["Interpretation"]
    assert interp["frontier_cost_comparison_usd"]["claude-opus-4-8"] == pytest.approx(5.00)


# --- Reliability metrics (AttemptRecord / record_outcome) -- System
# Architecture v2 Instrumentation, see engine/decisions.md and
# engine/specs/system-architecture-v2-specification.md ---


def test_record_outcome_is_noop_when_tracking_disabled():
    tracker = UsageTracker()
    tracker.record_outcome(AttemptRecord(component="Judgment", provider="openrouter", outcome="success"))
    assert tracker.outcomes == []


def test_record_outcome_appends_when_tracking_enabled():
    os.environ["CONFIDANT_TRACK_USAGE"] = "1"
    tracker = UsageTracker()
    tracker.record_outcome(AttemptRecord(component="Judgment", provider="openrouter", outcome="success"))
    assert tracker.outcome_count() == 1
    assert tracker.outcomes[0].component == "Judgment"


def test_attempt_record_model_defaults_to_none():
    """engine.py never knows the resolved model string -- only
    src/llm/providers.py does -- so AttemptRecord.model must default to
    None (genuinely unknown), never a guessed value."""
    record = AttemptRecord(component="Planner", provider="ollama", outcome="provider_call_error", detail="boom")
    assert record.model is None


def test_outcomes_since_isolates_a_single_turn():
    os.environ["CONFIDANT_TRACK_USAGE"] = "1"
    tracker = UsageTracker()
    tracker.record_outcome(AttemptRecord(component="Judgment", provider="openrouter", outcome="success"))
    start = tracker.outcome_count()
    tracker.record_outcome(AttemptRecord(component="Planner", provider="openrouter", outcome="success"))
    assert len(tracker.outcomes_since(start)) == 1
    assert tracker.outcomes_since(start)[0].component == "Planner"


def test_reset_clears_outcomes_too():
    os.environ["CONFIDANT_TRACK_USAGE"] = "1"
    tracker = UsageTracker()
    tracker.record_outcome(AttemptRecord(component="Judgment", provider="openrouter", outcome="success"))
    tracker.reset()
    assert tracker.outcomes == []
    assert tracker.records == []


def test_reliability_summary_counts_and_rate():
    os.environ["CONFIDANT_TRACK_USAGE"] = "1"
    tracker = UsageTracker()
    tracker.record_outcome(AttemptRecord(component="Judgment", provider="openrouter", outcome="provider_call_error", detail="x"))
    tracker.record_outcome(AttemptRecord(component="Judgment", provider="ollama", outcome="success"))
    tracker.record_outcome(AttemptRecord(component="Planner", provider="openrouter", outcome="schema_validation_failed", detail="y"))

    reliability = tracker.summary()["reliability"]
    assert reliability["attempts"] == 3
    assert reliability["successes"] == 1
    assert reliability["failures"] == 2
    assert reliability["success_rate"] == pytest.approx(1 / 3)
    assert reliability["failures_by_type"] == {"provider_call_error": 1, "schema_validation_failed": 1}


def test_reliability_success_rate_is_none_not_zero_when_no_attempts():
    """No data and 'confirmed 0% success' are different claims -- same
    None-honesty rule as every other optional aggregate in this module."""
    tracker = UsageTracker()
    reliability = tracker.summary()["reliability"]
    assert reliability["attempts"] == 0
    assert reliability["success_rate"] is None


def test_reliability_by_component_and_by_provider_breakdowns():
    os.environ["CONFIDANT_TRACK_USAGE"] = "1"
    tracker = UsageTracker()
    tracker.record_outcome(AttemptRecord(component="Judgment", provider="openrouter", outcome="provider_call_error", detail="x"))
    tracker.record_outcome(AttemptRecord(component="Judgment", provider="ollama", outcome="success"))

    reliability = tracker.summary()["reliability"]
    assert reliability["by_component"]["Judgment"] == {
        "attempts": 2, "successes": 1, "failures": 1, "success_rate": pytest.approx(0.5),
    }
    assert reliability["by_provider"]["openrouter"]["successes"] == 0
    assert reliability["by_provider"]["ollama"]["successes"] == 1


def test_reliability_uses_explicit_outcomes_param_over_self_outcomes():
    """summary(outcomes=...) isolates a slice the same way summary(records=...)
    already does -- doesn't fall back to self.outcomes when an explicit
    (even empty) list is passed."""
    os.environ["CONFIDANT_TRACK_USAGE"] = "1"
    tracker = UsageTracker()
    tracker.record_outcome(AttemptRecord(component="Judgment", provider="openrouter", outcome="success"))
    reliability = tracker.summary(outcomes=[])["reliability"]
    assert reliability["attempts"] == 0


def test_print_turn_summary_is_noop_when_both_records_and_outcomes_empty(capsys):
    print_turn_summary([], [])
    print_turn_summary([])
    assert capsys.readouterr().out == ""


def test_print_turn_summary_still_reports_a_component_with_zero_records(capsys):
    """Bug found during the System Architecture v2 review pass: a component
    whose every provider attempt fails at the call-error stage (see
    src/llm/providers.py) never produces an LLMUsage record -- only
    AttemptRecord failures exist. print_turn_summary used to bail out
    entirely with `if not records: return`, silently dropping that
    component's real, recorded failure data from the report. It must now
    still print a block for that component (token/cost fields as N/A) and
    the Reliability line for it, plus a Pipeline Total reliability line,
    driven off outcomes alone."""
    outcomes = [
        AttemptRecord(component="Judgment", provider="openrouter", outcome="provider_call_error", detail="boom"),
        AttemptRecord(component="Judgment", provider="ollama", outcome="provider_call_error", detail="boom"),
    ]
    print_turn_summary([], outcomes)
    out = capsys.readouterr().out
    assert "Judgment" in out
    assert "N/A (no call returned content)" in out
    assert "Reliability: 0/2 succeeded (0%)" in out
    assert "Pipeline Total" in out


def test_print_turn_summary_mixes_recorded_and_record_less_components(capsys):
    """One component succeeded (has an LLMUsage record), another failed
    every attempt (outcomes only, no record) -- both must appear, each
    with accurate per-component data, not just the one with records."""
    records = [
        build_usage(
            component="Planner", provider="openrouter", model="m",
            prompt_tokens=10, completion_tokens=5, latency_ms=100,
        )
    ]
    outcomes = [
        AttemptRecord(component="Planner", provider="openrouter", outcome="success"),
        AttemptRecord(component="Judgment", provider="openrouter", outcome="provider_call_error", detail="boom"),
    ]
    print_turn_summary(records, outcomes)
    out = capsys.readouterr().out
    assert "Planner" in out and "Judgment" in out
    assert "Reliability: 1/1 succeeded (100%)" in out
    assert "Reliability: 0/1 succeeded (0%)" in out
    # Pipeline Total token fields come from the one real record, not N/A,
    # since `records` isn't empty overall.
    assert "Prompt Tokens: 10" in out
