"""
Tests for the DB persistence side of production observability
(2026-07-19, backlog #230, see engine/decisions.md "Production
observability beyond opt-in UsageTracker") -- record_llm_usage/
record_llm_attempt/get_llm_usage_records/get_llm_attempt_records in
src/api/db.py. Server-level wiring (send_message actually calling
these when CONFIDANT_TRACK_USAGE is set) is covered in
tests/test_api_server.py; scripts/usage_report.py's own report
formatting is covered in tests/test_usage_report.py.
"""

from __future__ import annotations

from src.api import db
from src.instrumentation.usage import AttemptRecord, LLMUsage


def _usage(component="Interpretation", latency_ms=100.0, cost=0.01) -> LLMUsage:
    return LLMUsage(
        component=component, provider="openrouter", model="openai/gpt-4o-mini",
        prompt_tokens=100, completion_tokens=50, total_tokens=150,
        latency_ms=latency_ms, estimated_cost_usd=cost,
    )


def _attempt(component="Interpretation", outcome="success") -> AttemptRecord:
    return AttemptRecord(component=component, provider="openrouter", model="openai/gpt-4o-mini", outcome=outcome)


def test_record_and_read_usage_round_trips(tmp_path):
    db.init_db(tmp_path / "test.db")
    db.record_llm_usage("session-1", _usage())

    records = db.get_llm_usage_records()
    assert len(records) == 1
    assert records[0].component == "Interpretation"
    assert records[0].latency_ms == 100.0
    assert records[0].estimated_cost_usd == 0.01


def test_record_and_read_attempt_round_trips(tmp_path):
    db.init_db(tmp_path / "test.db")
    db.record_llm_attempt("session-1", _attempt(outcome="schema_validation_failed"))

    records = db.get_llm_attempt_records()
    assert len(records) == 1
    assert records[0].outcome == "schema_validation_failed"


def test_usage_records_accept_a_null_session_id(tmp_path):
    """session_id is nullable -- no FOREIGN KEY constraint, since this
    is operational telemetry, not data attributed to any one account or
    even necessarily a real session."""
    db.init_db(tmp_path / "test.db")
    db.record_llm_usage(None, _usage())
    assert len(db.get_llm_usage_records()) == 1


def test_get_llm_usage_records_filters_by_since(tmp_path, monkeypatch):
    db.init_db(tmp_path / "test.db")
    db.record_llm_usage("session-1", _usage())

    # A timestamp far in the future excludes the record just written.
    assert db.get_llm_usage_records(since_iso="2999-01-01T00:00:00+00:00") == []
    # A timestamp far in the past includes it.
    assert len(db.get_llm_usage_records(since_iso="2000-01-01T00:00:00+00:00")) == 1


def test_get_llm_attempt_records_filters_by_since(tmp_path):
    db.init_db(tmp_path / "test.db")
    db.record_llm_attempt("session-1", _attempt())

    assert db.get_llm_attempt_records(since_iso="2999-01-01T00:00:00+00:00") == []
    assert len(db.get_llm_attempt_records(since_iso="2000-01-01T00:00:00+00:00")) == 1
