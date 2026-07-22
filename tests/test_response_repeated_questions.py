"""
Tests for the Response-level repeated-question fix (2026-07-22, second
live regression on the same conversation shape -- direct founder bug
report: "same issues again reverting back to asking about hardest part
when better questions exist"). Root cause: the earlier fix
(apply_repeated_question_filter, src/planner/engine.py) only filtered
Planner's OWN candidate list; Response is never required to reuse that
wording verbatim, and state.recent_planner_questions was itself excluded
from Response's prompt -- so Response could (and did, live) reinvent the
same generic "what's been the hardest part" shape in its own words, with
no memory of having just asked it.

The fix: extract_asked_question (src/response/engine.py) pulls the real
question sentence out of each turn's own response_text, and
run_response_generator threads state.recent_response_questions into
build_messages so Response can see its own recent phrasing. Same
call_provider-mocking pattern as tests/test_response_engine.py.
"""

from __future__ import annotations

import json

from src.judgment.schema import Judgment
from src.planner.schema import Planner
from src.response.engine import RECENT_RESPONSE_QUESTIONS_WINDOW, extract_asked_question, run_response_generator
from src.state.world_state import Fact, WorldState

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


# --- extract_asked_question -------------------------------------------------

def test_extract_asked_question_pulls_the_trailing_question_sentence():
    text = (
        "The lack of communication from your boss seems to be really "
        "compounding the frustration you're feeling right now. Has this "
        "been building up over time, or did something specific today "
        "make it feel heavier than usual?"
    )
    assert extract_asked_question(text) == (
        "Has this been building up over time, or did something specific "
        "today make it feel heavier than usual?"
    )


def test_extract_asked_question_returns_none_when_there_is_no_question_mark():
    text = "It would help to know what type of advice you're looking for. Let me know whenever you're ready."
    assert extract_asked_question(text) is None


def test_extract_asked_question_handles_a_single_sentence_response():
    assert extract_asked_question("What's on your mind?") == "What's on your mind?"


# --- run_response_generator threading ---------------------------------------

def test_run_response_generator_passes_recent_response_questions_to_the_prompt(monkeypatch):
    call, captured = _capture_call_provider()
    monkeypatch.setattr("src.response.engine.call_provider", call)

    state = WorldState(facts=[Fact(content="User is considering a job offer.")])
    state = state.model_copy(update={
        "recent_response_questions": ["What's been the hardest part of this situation for you lately?"],
    })

    run_response_generator(state, Judgment(**_MINIMAL_JUDGMENT), Planner(**_MINIMAL_PLANNER))

    assert "What's been the hardest part of this situation for you lately?" in captured["messages"]
    assert "already asked in recent prior" in captured["messages"]


def test_run_response_generator_omits_the_recent_questions_block_when_empty(monkeypatch):
    call, captured = _capture_call_provider()
    monkeypatch.setattr("src.response.engine.call_provider", call)

    state = WorldState(facts=[Fact(content="User is considering a job offer.")])

    run_response_generator(state, Judgment(**_MINIMAL_JUDGMENT), Planner(**_MINIMAL_PLANNER))

    assert "already asked in recent prior" not in captured["messages"]


def test_run_response_generator_only_passes_the_most_recent_window(monkeypatch):
    call, captured = _capture_call_provider()
    monkeypatch.setattr("src.response.engine.call_provider", call)

    many_questions = [f"Old question number {i}?" for i in range(RECENT_RESPONSE_QUESTIONS_WINDOW + 3)]
    state = WorldState(facts=[Fact(content="User is considering a job offer.")])
    state = state.model_copy(update={"recent_response_questions": many_questions})

    run_response_generator(state, Judgment(**_MINIMAL_JUDGMENT), Planner(**_MINIMAL_PLANNER))

    assert "Old question number 0?" not in captured["messages"]
    assert f"Old question number {RECENT_RESPONSE_QUESTIONS_WINDOW + 2}?" in captured["messages"]
