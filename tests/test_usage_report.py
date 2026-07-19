"""
Tests for scripts/usage_report.py (2026-07-19, backlog #230, see
engine/decisions.md "Production observability beyond opt-in
UsageTracker") -- the report's own aggregation/formatting logic,
against a seeded temp database. DB persistence itself is covered in
tests/test_usage_persistence.py.
"""

from __future__ import annotations

import sys

from scripts.usage_report import _percentile, main as usage_report_main
from src.api import db
from src.instrumentation.usage import AttemptRecord, LLMUsage


def test_percentile_of_empty_list_is_zero():
    assert _percentile([], 0.5) == 0.0


def test_percentile_nearest_rank():
    values = [10, 20, 30, 40, 50]
    assert _percentile(values, 0.0) == 10
    assert _percentile(values, 1.0) == 50
    assert _percentile(values, 0.5) == 30


def test_report_handles_no_records(tmp_path, monkeypatch, capsys):
    db_path = tmp_path / "empty.db"
    db.init_db(db_path)

    monkeypatch.setattr(sys, "argv", ["usage_report.py", "--db-path", str(db_path)])
    usage_report_main()
    out = capsys.readouterr().out
    assert "No usage/attempt records found" in out


def test_report_summarizes_success_rate_and_cost(tmp_path, monkeypatch, capsys):
    db_path = tmp_path / "seeded.db"
    db.init_db(db_path)
    db.record_llm_usage("s1", LLMUsage(
        component="Judgment", provider="openrouter", model="openai/gpt-4o-mini",
        prompt_tokens=100, completion_tokens=50, total_tokens=150,
        latency_ms=200.0, estimated_cost_usd=0.02,
    ))
    db.record_llm_usage("s1", LLMUsage(
        component="Judgment", provider="openrouter", model="openai/gpt-4o-mini",
        prompt_tokens=100, completion_tokens=50, total_tokens=150,
        latency_ms=400.0, estimated_cost_usd=0.03,
    ))
    db.record_llm_attempt("s1", AttemptRecord(component="Judgment", provider="openrouter", outcome="success"))
    db.record_llm_attempt("s1", AttemptRecord(component="Judgment", provider="openrouter", outcome="invalid_json"))

    monkeypatch.setattr(sys, "argv", ["usage_report.py", "--db-path", str(db_path)])
    usage_report_main()
    out = capsys.readouterr().out

    assert "Judgment" in out
    assert "success rate: 50.0%" in out
    assert "invalid_json: 1" in out
    assert "Calls: 2" in out
    assert "$0.05" in out  # total cost across both calls
