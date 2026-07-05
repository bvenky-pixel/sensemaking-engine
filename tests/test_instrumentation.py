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

from src.instrumentation.pricing import estimate_cost_usd
from src.instrumentation.usage import (
    LLMUsage,
    ParsedUsage,
    UsageTracker,
    build_usage,
    extract_anthropic_usage,
    extract_ollama_usage,
    extract_openai_compatible_usage,
    is_tracking_enabled,
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
