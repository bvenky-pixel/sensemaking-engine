"""
Tests for src/insight/ -- the cross-session theme detection engine (see
engine/decisions.md "Major update"). call_provider is mocked at
src.insight.engine's own import path (same pattern as
tests/test_api_server.py's _always_returns), no real LLM calls.

Focus: the engine-level grounding enforcement (never trust the model's
own evidence_session_ids uncritically) and the evidence-floor
short-circuit that avoids spending an LLM call when it's structurally
impossible to ground a theme.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from src.insight.engine import InsightEngineError, run_insight_detection, select_relevant_insight
from src.insight.schema import MIN_EVIDENCE_SESSIONS, Insight, InsightBatch
from src.state.world_state import Claim, Fact, WorldState


def _always_returns(payload):
    def _call(provider_name, system_prompt, messages, schema, temperature, component="unknown", tracker=None):
        return json.dumps(payload)
    return _call


def test_insight_batch_defaults_to_empty_list():
    assert InsightBatch().insights == []


def test_insight_requires_theme_and_detail():
    with pytest.raises(ValidationError):
        Insight()


def test_below_evidence_floor_short_circuits_without_calling_the_provider(monkeypatch):
    def _fail_if_called(*args, **kwargs):
        raise AssertionError("call_provider should never be reached below the evidence floor")

    monkeypatch.setattr("src.insight.engine.call_provider", _fail_if_called)

    session_texts = [("s1", "Considering a move.", "Undecided about relocating.")]
    assert len(session_texts) < MIN_EVIDENCE_SESSIONS
    assert run_insight_detection(session_texts) == []


def test_grounding_filters_hallucinated_session_ids(monkeypatch):
    """The model cites a real evidence session plus one that was never
    sent -- the hallucinated id must be dropped, not trusted."""
    payload = {
        "insights": [
            {
                "theme": "Decisions paused pending more certainty",
                "detail": "Both sessions stalled waiting on someone else's timeline.",
                "evidence_session_ids": ["s1", "s2", "s-does-not-exist"],
            }
        ]
    }
    monkeypatch.setattr("src.insight.engine.call_provider", _always_returns(payload))

    session_texts = [
        ("s1", "Waiting on manager approval.", "Blocked on manager's decision."),
        ("s2", "Waiting on co-founder to decide.", "Blocked on co-founder's decision."),
    ]
    result = run_insight_detection(session_texts)

    assert len(result) == 1
    assert result[0].evidence_session_ids == ["s1", "s2"]


def test_insight_dropped_when_surviving_evidence_falls_below_floor(monkeypatch):
    """After filtering out ids that weren't actually sent, only ONE real
    session remains -- below MIN_EVIDENCE_SESSIONS, so the whole Insight
    must be dropped, not kept with weakened evidence."""
    payload = {
        "insights": [
            {
                "theme": "Some theme",
                "detail": "Some detail.",
                "evidence_session_ids": ["s1", "s-hallucinated-1", "s-hallucinated-2"],
            }
        ]
    }
    monkeypatch.setattr("src.insight.engine.call_provider", _always_returns(payload))

    session_texts = [
        ("s1", "Situation one.", "Problem one."),
        ("s2", "Situation two.", "Problem two."),
    ]
    result = run_insight_detection(session_texts)

    assert result == []


def test_empty_insights_is_a_valid_correct_response(monkeypatch):
    monkeypatch.setattr("src.insight.engine.call_provider", _always_returns({"insights": []}))

    session_texts = [
        ("s1", "Situation one.", "Problem one."),
        ("s2", "Completely unrelated situation.", "Unrelated problem."),
    ]
    assert run_insight_detection(session_texts) == []


def test_raises_when_every_provider_fails(monkeypatch):
    def _always_invalid_json(*args, **kwargs):
        return "not valid json"

    monkeypatch.setattr("src.insight.engine.call_provider", _always_invalid_json)

    session_texts = [
        ("s1", "Situation one.", "Problem one."),
        ("s2", "Situation two.", "Problem two."),
    ]
    with pytest.raises(InsightEngineError):
        run_insight_detection(session_texts)


# --- select_relevant_insight (2026-07-19, backlog #210) ---

def test_select_relevant_insight_returns_none_for_no_insights():
    state = WorldState(facts=[Fact(content="User is considering a job offer.")])
    assert select_relevant_insight([], state) is None


def test_select_relevant_insight_returns_none_when_state_has_no_content():
    insight = Insight(theme="Avoidance", detail="Tends to delay hard conversations.")
    assert select_relevant_insight([insight], WorldState()) is None


def test_select_relevant_insight_returns_none_when_nothing_overlaps():
    """A callback referencing something with zero real connection to
    this conversation would read as a non sequitur -- worse than saying
    nothing."""
    insight = Insight(theme="Avoidance", detail="Tends to delay hard conversations with managers.")
    state = WorldState(facts=[Fact(content="User just adopted a new puppy.")])
    assert select_relevant_insight([insight], state) is None


def test_select_relevant_insight_picks_the_highest_overlap_score():
    relevant = Insight(theme="Avoiding hard conversations", detail="Delays direct feedback with managers.")
    unrelated = Insight(theme="Sleep schedule", detail="Struggles to keep a consistent bedtime.")
    state = WorldState(
        facts=[Fact(content="User is nervous about giving their manager direct feedback.")],
        claims=[Claim(content="User believes avoiding hard conversations makes things worse.")],
    )
    assert select_relevant_insight([unrelated, relevant], state) == relevant


def test_select_relevant_insight_breaks_ties_by_list_order():
    first = Insight(theme="Career direction", detail="Weighs job offers for a long time.")
    second = Insight(theme="Career choices", detail="Weighs job offers for a long time.")
    state = WorldState(facts=[Fact(content="User is weighing a new job offer.")])
    assert select_relevant_insight([first, second], state) == first
