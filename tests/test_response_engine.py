"""
Tests for src/response/engine.py's Insight-triggered conversational
callback threading (2026-07-19, backlog #210, see engine/decisions.md
"POM: Insight-triggered conversational callback"). call_provider is
mocked at src.response.engine's own import path, same pattern as
tests/test_understanding.py's own _capture_call_provider -- no real LLM
calls.
"""

from __future__ import annotations

import json

from src.insight.schema import Insight
from src.judgment.schema import Judgment
from src.planner.schema import Planner
from src.response.engine import run_response_generator
from src.state.world_state import Fact, WorldState

# Same minimal fixtures as tests/test_understanding.py -- kept in sync
# by copying, not importing, per this codebase's own "small fixtures
# duplicated across test files" convention (mirrors src/pom/engine.py's
# own duplicated-helper discipline).
_MINIMAL_JUDGMENT = {
    "primary_problem": "", "primary_goal": "", "current_focus": "", "key_blockers": [],
    "secondary_issues": [], "open_unknowns": [], "active_decisions": [], "contradictions": [],
    "has_knowledge_correction": False, "knowledge_correction_target": "",
    "knowledge_correction_kind": "", "knowledge_correction_corrected_content": "",
    "has_risk_signal": False, "risk_scan": "No risk-worthy signal identified.", "risks": [],
    "opportunities": [], "has_decision_resolution": False, "decision_resolution_option": "",
    "decision_resolution_status": "", "stagnation_notes": [], "confidence": 0.5,
    "supporting_evidence": [],
}

_MINIMAL_PLANNER = {
    "primary_objective": "clarify uncertainty", "rationale": "Early turn.",
    "conversational_strategy": "ask exploratory questions", "resolution_blocker": "",
    "priority_topics": [], "questions_to_explore": [], "assumptions_to_test": [],
    "planning_constraints": [], "desired_outcome": "user gains clarity",
    "temporal_horizon": "immediate", "confidence": 0.5,
}


def _capture_call_provider():
    captured = {}

    def _call(provider_name, system_prompt, messages, schema, temperature, component="unknown", tracker=None):
        captured["messages"] = json.dumps(messages)
        return json.dumps({"response_text": "ok", "confidence": 0.5})

    return _call, captured


def test_run_response_generator_surfaces_a_relevant_insight_on_turn_one(monkeypatch):
    call, captured = _capture_call_provider()
    monkeypatch.setattr("src.response.engine.call_provider", call)

    state = WorldState(facts=[Fact(content="User is nervous about giving their manager direct feedback.")])
    state.turn_count = 1
    insight = Insight(theme="Avoiding hard conversations", detail="Delays direct feedback with managers.")

    run_response_generator(
        state, Judgment(**_MINIMAL_JUDGMENT), Planner(**_MINIMAL_PLANNER), insights=[insight],
    )

    assert "Avoiding hard conversations" in captured["messages"]
    assert "Insight-triggered" in captured["messages"]


def test_run_response_generator_omits_the_callback_past_turn_one(monkeypatch):
    call, captured = _capture_call_provider()
    monkeypatch.setattr("src.response.engine.call_provider", call)

    state = WorldState(facts=[Fact(content="User is nervous about giving their manager direct feedback.")])
    state.turn_count = 2
    insight = Insight(theme="Avoiding hard conversations", detail="Delays direct feedback with managers.")

    run_response_generator(
        state, Judgment(**_MINIMAL_JUDGMENT), Planner(**_MINIMAL_PLANNER), insights=[insight],
    )

    assert "Insight-triggered" not in captured["messages"]


def test_run_response_generator_omits_the_callback_when_nothing_is_relevant(monkeypatch):
    call, captured = _capture_call_provider()
    monkeypatch.setattr("src.response.engine.call_provider", call)

    state = WorldState(facts=[Fact(content="User just adopted a new puppy.")])
    state.turn_count = 1
    insight = Insight(theme="Avoiding hard conversations", detail="Delays direct feedback with managers.")

    run_response_generator(
        state, Judgment(**_MINIMAL_JUDGMENT), Planner(**_MINIMAL_PLANNER), insights=[insight],
    )

    assert "Insight-triggered" not in captured["messages"]


def test_run_response_generator_defaults_insights_to_no_callback(monkeypatch):
    """Every existing caller that doesn't pass `insights` at all (the
    vast majority of tests in this suite) must still work exactly as
    before -- no callback, no error."""
    call, captured = _capture_call_provider()
    monkeypatch.setattr("src.response.engine.call_provider", call)

    state = WorldState(facts=[Fact(content="User is considering a job offer.")])
    state.turn_count = 1
    response = run_response_generator(state, Judgment(**_MINIMAL_JUDGMENT), Planner(**_MINIMAL_PLANNER))

    assert response.response_text == "ok"
    assert "Insight-triggered" not in captured["messages"]
