"""
Tests for the instrumentation layer (src/instrumentation/usage.py,
pricing.py) -- all deterministic, no LLM calls needed. Covers: usage
extraction from provider response shapes, cost estimation, tracker
aggregation, and the disabled-by-default behavior that's the whole point
of "measurement only, no behavior change outside evaluation runs."
"""

from __future__ import annotations

import os

import pytest

from src.instrumentation.pricing import estimate_cost_usd
from src.instrumentation.usage import (
    LLMUsage,
    UsageTracker,
    build_usage,
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


def test_extract_openai_compatible_usage_handles_missing_fields():
    assert extract_openai_compatible_usage({"usage": {"prompt_tokens": 10, "completion_tokens": 5}}) == (10, 5)
    assert extract_openai_compatible_usage({}) == (0, 0)
    assert extract_openai_compatible_usage({"usage": {}}) == (0, 0)


def test_extract_ollama_usage_handles_missing_fields():
    assert extract_ollama_usage({"prompt_eval_count": 500, "eval_count": 120}) == (500, 120)
    assert extract_ollama_usage({}) == (0, 0)


def test_ollama_cost_is_always_zero_not_unknown():
    assert estimate_cost_usd("ollama", "llama3.2:3b", 1000, 1000) == 0.0


def test_unknown_openrouter_model_cost_is_none_not_a_guess():
    assert estimate_cost_usd("openrouter", "some/unlisted-model", 1000, 1000) is None


def test_known_openrouter_model_cost_computed_from_pricing_table():
    cost = estimate_cost_usd("openrouter", "openai/gpt-4o-mini", 1_000_000, 1_000_000)
    assert cost == pytest.approx(0.15 + 0.60)


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

    assert summary["input_tokens"] == 812 + 1354
    assert summary["output_tokens"] == 267 + 194
    assert summary["total_tokens"] == (812 + 267) + (1354 + 194)
    assert summary["cost_fully_known"] is True
    assert summary["estimated_cost_usd"] == pytest.approx(expected_cost)
    assert set(summary["by_component"].keys()) == {"Interpretation", "Judgment"}
    assert summary["by_component"]["Interpretation"]["input_tokens"] == 812


def test_summary_reports_unknown_cost_honestly_when_model_unpriced():
    os.environ["CONFIDANT_TRACK_USAGE"] = "1"
    tracker = UsageTracker()
    tracker.record(build_usage("Interpretation", "openrouter", "some/unlisted-model", 100, 50, 100.0))

    summary = tracker.summary()
    assert summary["cost_fully_known"] is False
    assert summary["estimated_cost_usd"] is None
