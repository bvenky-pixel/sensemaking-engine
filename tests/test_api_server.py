"""
Tests for the MVP API layer (src/api/). Deterministic: call_provider is
mocked at each engine module's own import path (same pattern as
tests/test_reliability_instrumentation.py, tests/test_evaluation_harness.py),
no real HTTP or LLM calls.

The one genuinely new thing this codebase has never exercised before
this file: WorldState surviving a round trip through SQLite
(model_dump_json -> stored -> model_validate_json on the next request).
Every other existing test only ever holds WorldState in-process for the
life of one function call. test_second_message_reflects_accumulated_state
below is built specifically to fail if that round trip is broken (each
turn's Interpretation mock introduces a DIFFERENT fact; if persistence
were silently starting fresh every request, only the second fact would
ever appear).
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api import db, server

_MINIMAL_JUDGMENT = {
    "primary_problem": "",
    "primary_goal": "",
    "current_focus": "",
    "key_blockers": [],
    "secondary_issues": [],
    "open_unknowns": [],
    "active_decisions": [],
    "contradictions": [],
    "has_risk_signal": False,
    "risk_scan": "No risk-worthy signal identified.",
    "risks": [],
    "opportunities": [],
    "has_decision_resolution": False,
    "decision_resolution_option": "",
    "decision_resolution_status": "",
    "stagnation_notes": [],
    "confidence": 0.5,
    "supporting_evidence": [],
}

_MINIMAL_PLANNER = {
    "primary_objective": "build understanding",
    "rationale": "Early turn, still gathering context.",
    "conversational_strategy": "ask exploratory questions",
    "resolution_blocker": "",
    "priority_topics": [],
    "questions_to_explore": [],
    "assumptions_to_test": [],
    "planning_constraints": [],
    "desired_outcome": "user shares more context",
    "temporal_horizon": "immediate",
    "confidence": 0.5,
}

_MINIMAL_RESPONSE = {
    "response_text": "Thanks for sharing that.",
    "confidence": 0.5,
}


def _minimal_interp(fact: str) -> dict:
    return {
        "urgency": "low",
        "impact_domains": [],
        "emotional_signals": [],
        "surface_complaint": fact,
        "core_question": "",
        "core_question_confidence": 0.0,
        "observed_facts": [fact],
        "claims": [],
        "goals": [],
        "decision_options": [],
        "has_assumption": False,
        "assumption_check": "No framing-embedded assumption detected.",
        "assumptions": [],
        "inferences": [],
        "unknowns": [],
        "biases": [],
        "entities": [],
        "clarity_score": 0.5,
        "requires_clarification": False,
        "has_decision_event": False,
        "decision_event_option": "",
        "decision_event_type": "",
    }


def _always_returns(payload_or_list):
    """
    If given a list, returns each element in order across successive
    calls (used to make Interpretation's mock introduce a different
    fact per turn); otherwise always returns the same payload.
    """
    if isinstance(payload_or_list, list):
        state = {"calls": iter(payload_or_list)}

        def _call(provider_name, system_prompt, messages, schema, temperature, component="unknown", tracker=None):
            return json.dumps(next(state["calls"]))
        return _call

    def _call(provider_name, system_prompt, messages, schema, temperature, component="unknown", tracker=None):
        return json.dumps(payload_or_list)
    return _call


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(
        "src.judgment.engine.call_provider", _always_returns(_MINIMAL_JUDGMENT)
    )
    monkeypatch.setattr(
        "src.planner.engine.call_provider", _always_returns(_MINIMAL_PLANNER)
    )
    monkeypatch.setattr(
        "src.response.engine.call_provider", _always_returns(_MINIMAL_RESPONSE)
    )
    with TestClient(server.app) as c:
        yield c


def test_create_session_returns_id(client):
    res = client.post("/sessions")
    assert res.status_code == 200
    assert "id" in res.json()


def test_send_message_returns_response_text(client, monkeypatch):
    monkeypatch.setattr(
        "src.interpretation.engine.call_provider",
        _always_returns(_minimal_interp("User wants to move to the Product team.")),
    )
    session_id = client.post("/sessions").json()["id"]

    res = client.post(f"/sessions/{session_id}/messages", json={"content": "I want to move teams."})

    assert res.status_code == 200
    body = res.json()
    assert body["response_text"] == "Thanks for sharing that."
    assert body["failed_stage"] is None


def test_second_message_reflects_accumulated_state(client, monkeypatch):
    """
    Turn 1's Interpretation mock introduces Fact A; turn 2's introduces
    Fact B. If the session's WorldState didn't actually survive the
    SQLite round trip between requests, turn 2 would start from a blank
    WorldState and only Fact B would ever have existed -- this fails
    loudly in that case rather than silently passing.
    """
    monkeypatch.setattr(
        "src.interpretation.engine.call_provider",
        _always_returns([
            _minimal_interp("User wants to move to the Product team."),
            _minimal_interp("Sarah keeps deferring the transfer."),
        ]),
    )
    session_id = client.post("/sessions").json()["id"]

    client.post(f"/sessions/{session_id}/messages", json={"content": "I want to move teams."})
    client.post(f"/sessions/{session_id}/messages", json={"content": "Sarah keeps deferring."})

    debug = client.get(f"/sessions/{session_id}/debug").json()
    fact_contents = [f["content"] for f in debug["state"]["facts"]]

    assert "User wants to move to the Product team." in fact_contents
    assert "Sarah keeps deferring the transfer." in fact_contents


def test_list_messages_returns_transcript_in_order(client, monkeypatch):
    monkeypatch.setattr(
        "src.interpretation.engine.call_provider",
        _always_returns(_minimal_interp("User wants to move to the Product team.")),
    )
    session_id = client.post("/sessions").json()["id"]
    client.post(f"/sessions/{session_id}/messages", json={"content": "I want to move teams."})

    messages = client.get(f"/sessions/{session_id}/messages").json()

    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "I want to move teams."
    assert messages[1]["content"] == "Thanks for sharing that."


def test_unknown_session_returns_404(client):
    res = client.get("/sessions/does-not-exist/messages")
    assert res.status_code == 404


def test_list_sessions_returns_summaries_ordered_by_recency(client, monkeypatch):
    """Backs the real frontend's Home screen (a list of a person's
    Journeys) -- see frontend/decisions.md "Build the real Confidant
    frontend". Session B is created after A but never touched again, so
    sending a message to A (which bumps its updated_at) must move A back
    to the front of the list."""
    monkeypatch.setattr(
        "src.interpretation.engine.call_provider",
        _always_returns(_minimal_interp("User wants to move to the Product team.")),
    )
    session_a = client.post("/sessions").json()["id"]
    session_b = client.post("/sessions").json()["id"]

    client.post(f"/sessions/{session_a}/messages", json={"content": "I want to move teams."})

    summaries = client.get("/sessions").json()
    ids_in_order = [s["id"] for s in summaries]

    assert ids_in_order[0] == session_a
    assert session_b in ids_in_order
    matching = [s for s in summaries if s["id"] == session_a][0]
    assert matching["surface_complaint"] == "User wants to move to the Product team."


def test_clarity_brief_returns_404_before_any_completed_turn(client):
    session_id = client.post("/sessions").json()["id"]
    res = client.get(f"/sessions/{session_id}/clarity-brief")
    assert res.status_code == 404


def test_clarity_brief_reflects_completed_turn(client, monkeypatch):
    """Exercises the Executor's fixed template (src/executor/engine.py)
    through the live endpoint -- situation/current_direction/decisions
    come from WorldState/Planner directly, key_insights/remaining_unknowns
    are Judgment's curated subset, not a raw WorldState dump."""
    monkeypatch.setattr(
        "src.interpretation.engine.call_provider",
        _always_returns(_minimal_interp("User wants to move to the Product team.")),
    )
    populated_judgment = dict(_MINIMAL_JUDGMENT)
    populated_judgment.update(
        {
            "primary_problem": "Founder resists the move.",
            "risks": ["Founder may block the transfer."],
            "opportunities": ["A new manager could sponsor it."],
            "open_unknowns": ["What does the user want next?"],
            "secondary_issues": ["Strained relationship with their current manager."],
            "stagnation_notes": ["No movement on this goal in 4 turns."],
        }
    )
    monkeypatch.setattr("src.judgment.engine.call_provider", _always_returns(populated_judgment))
    populated_planner = dict(_MINIMAL_PLANNER)
    populated_planner["desired_outcome"] = "user gains clarity on next steps"
    monkeypatch.setattr("src.planner.engine.call_provider", _always_returns(populated_planner))

    session_id = client.post("/sessions").json()["id"]
    client.post(f"/sessions/{session_id}/messages", json={"content": "I want to move teams."})

    res = client.get(f"/sessions/{session_id}/clarity-brief")

    assert res.status_code == 200
    body = res.json()
    assert body["situation"] == "User wants to move to the Product team."
    assert body["key_insights"] == [
        "Founder resists the move.",
        "Founder may block the transfer.",
        "A new manager could sponsor it.",
    ]
    assert body["current_direction"] == "user gains clarity on next steps"
    assert body["remaining_unknowns"] == ["What does the user want next?"]
    assert body["decisions"] == []
    assert "# Clarity Brief" in body["rendered_markdown"]
    # Passed through directly from Judgment (not part of Executor's own
    # fixed template) -- see src/api/schema.py's ClarityBriefResponse docstring.
    assert body["secondary_issues"] == ["Strained relationship with their current manager."]
    assert body["stagnation_notes"] == ["No movement on this goal in 4 turns."]
