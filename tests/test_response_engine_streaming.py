"""Tests for src/response/engine.py's `on_token` wiring (2026-07-22,
backlog #233, see engine/decisions.md "Stream Response text
token-by-token"). Same minimal fixtures as tests/test_response_engine.py,
duplicated per that file's own stated "small fixtures duplicated across
test files" convention."""

from __future__ import annotations

import json

from src.judgment.schema import Judgment
from src.planner.schema import Planner
from src.response.engine import run_response_generator
from src.state.world_state import WorldState

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


def _streaming_call_provider(full_payload: dict, chunk_size: int = 3):
    """Fake call_provider that simulates streaming by feeding the given
    payload's JSON to on_delta in fixed-size chunks (when on_delta is
    given), same as a real OpenRouter streaming call would via
    _consume_openrouter_stream -- but returns the full accumulated text
    either way, matching the real function's contract."""
    full_json = json.dumps(full_payload)

    def _call(provider_name, system_prompt, messages, schema, temperature, component="unknown", tracker=None, on_delta=None):
        if on_delta is not None:
            for i in range(0, len(full_json), chunk_size):
                on_delta(full_json[i : i + chunk_size])
        return full_json

    return _call


def test_on_token_receives_streamed_response_text_fragments(monkeypatch):
    monkeypatch.setattr(
        "src.response.engine.call_provider",
        _streaming_call_provider({"response_text": "Hello there, friend.", "confidence": 0.6, "options": []}),
    )
    seen = []
    result = run_response_generator(
        WorldState(), Judgment(**_MINIMAL_JUDGMENT), Planner(**_MINIMAL_PLANNER), on_token=seen.append,
    )
    assert "".join(seen) == "Hello there, friend."
    assert result.response_text == "Hello there, friend."


def test_on_token_never_called_when_not_given(monkeypatch):
    """Every existing caller (conversation_runner.py, the offline
    scripts, every other test) never passes on_token -- must never
    request streaming or invoke any callback."""
    calls_saw_on_delta = []

    def _call(provider_name, system_prompt, messages, schema, temperature, component="unknown", tracker=None, **kwargs):
        calls_saw_on_delta.append("on_delta" in kwargs)
        return json.dumps({"response_text": "ok", "confidence": 0.5})

    monkeypatch.setattr("src.response.engine.call_provider", _call)
    result = run_response_generator(WorldState(), Judgment(**_MINIMAL_JUDGMENT), Planner(**_MINIMAL_PLANNER))
    assert calls_saw_on_delta == [False]
    assert result.response_text == "ok"


def test_on_token_still_streams_correctly_even_if_response_text_is_not_the_first_field(monkeypatch):
    """The extractor scans for the `"response_text"` key substring
    wherever it appears (see ResponseTextStreamExtractor's own
    docstring) -- it doesn't require the key to be literally first, only
    that it appears. Confirms streaming still works even against a
    model that ordered fields differently than the schema hint suggests."""
    monkeypatch.setattr(
        "src.response.engine.call_provider",
        _streaming_call_provider(
            {"confidence": 0.6, "response_text": "Still correct in the end.", "options": []}
        ),
    )
    seen = []
    result = run_response_generator(
        WorldState(), Judgment(**_MINIMAL_JUDGMENT), Planner(**_MINIMAL_PLANNER), on_token=seen.append,
    )
    assert "".join(seen) == "Still correct in the end."
    assert result.response_text == "Still correct in the end."
