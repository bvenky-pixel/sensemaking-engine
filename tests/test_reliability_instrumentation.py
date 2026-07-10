"""
Confirms every engine.py (Interpretation, Judgment, Planner, Response)
actually records an AttemptRecord at each of its four decision points
(provider_call_error, invalid_json, schema_validation_failed, success) --
System Architecture v2's Instrumentation component (see
engine/specs/system-architecture-v2-specification.md and
engine/decisions.md). All deterministic: call_provider is mocked at each
engine module's own import path, no real HTTP or LLM calls, same pattern
already used in tests/test_evaluation_harness.py.

Interpretation has a genuinely different control flow from the other
three (it breaks the provider loop on the first successful raw response
and does NOT retry across providers for JSON/schema failures -- see its
own module docstring) -- covered with its own full set of four tests.
Judgment is covered fully as the representative of the shared
Judgment/Planner/Response loop shape; Planner and Response get one
success + one failure test each, since their instrumentation wiring is
otherwise identical to Judgment's.
"""

from __future__ import annotations

import json
import os

import pytest
from pydantic import ValidationError

from src.instrumentation.usage import UsageTracker
from src.judgment.schema import Judgment
from src.llm.providers import ProviderCallError
from src.planner.schema import Planner
from src.response.schema import Response
from src.state.world_state import WorldState


@pytest.fixture(autouse=True)
def _clear_tracking_env():
    original = os.environ.pop("CONFIDANT_TRACK_USAGE", None)
    os.environ["CONFIDANT_TRACK_USAGE"] = "1"
    yield
    if original is not None:
        os.environ["CONFIDANT_TRACK_USAGE"] = original
    else:
        os.environ.pop("CONFIDANT_TRACK_USAGE", None)


_MINIMAL_JUDGMENT = {
    "primary_problem": "Transfer to Product team is stalled.",
    "primary_goal": "Move to the Product team.",
    "current_focus": "Understanding why the transfer stalled.",
    "key_blockers": [],
    "open_unknowns": [],
    "active_decisions": [],
    "contradictions": [],
    "has_risk_signal": False,
    "risk_scan": "No risk-worthy signal identified.",
    "risks": [],
    "opportunities": [],
    "confidence": 0.4,
    "supporting_evidence": [],
}

_MINIMAL_PLANNER = {
    "primary_objective": "clarify uncertainty",
    "rationale": "Judgment identifies an unresolved blocker.",
    "conversational_strategy": "ask exploratory questions",
    "resolution_blocker": "missing information",
    "priority_topics": [],
    "questions_to_explore": [],
    "assumptions_to_test": [],
    "planning_constraints": [],
    "desired_outcome": "user gains clarity",
    "temporal_horizon": "immediate",
    "confidence": 0.4,
}

_MINIMAL_RESPONSE = {
    "response_text": "It sounds like this has been unclear for a while.",
    "confidence": 0.4,
}


def _always_succeeds(payload):
    def _call(provider_name, system_prompt, messages, schema, temperature, component="unknown", tracker=None):
        return json.dumps(payload)
    return _call


def _always_raises_provider_call_error():
    def _call(provider_name, system_prompt, messages, schema, temperature, component="unknown", tracker=None):
        raise ProviderCallError(f"{provider_name} unreachable")
    return _call


def _always_returns_invalid_json():
    def _call(provider_name, system_prompt, messages, schema, temperature, component="unknown", tracker=None):
        return "not valid json {{"
    return _call


def _always_returns_schema_invalid():
    def _call(provider_name, system_prompt, messages, schema, temperature, component="unknown", tracker=None):
        return json.dumps({"unexpected": "shape"})
    return _call


# --- Judgment: representative of the shared Judgment/Planner/Response loop ---

def test_judgment_records_success_outcome(monkeypatch):
    from src.judgment.engine import run_judgment

    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setattr("src.judgment.engine.call_provider", _always_succeeds(_MINIMAL_JUDGMENT))
    tracker = UsageTracker()

    result = run_judgment(WorldState(), tracker=tracker)

    assert isinstance(result, Judgment)
    assert len(tracker.outcomes) == 1
    assert tracker.outcomes[0].component == "Judgment"
    assert tracker.outcomes[0].provider == "openrouter"
    assert tracker.outcomes[0].outcome == "success"
    assert tracker.outcomes[0].model is None


def test_judgment_records_provider_call_error_outcome_for_every_provider(monkeypatch):
    from src.judgment.engine import JudgmentError, run_judgment

    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setattr("src.judgment.engine.call_provider", _always_raises_provider_call_error())
    tracker = UsageTracker()

    with pytest.raises(JudgmentError):
        run_judgment(WorldState(), tracker=tracker)

    assert len(tracker.outcomes) == 1  # openrouter is the only registered provider
    assert all(o.outcome == "provider_call_error" for o in tracker.outcomes)
    assert {o.provider for o in tracker.outcomes} == {"openrouter"}


def test_judgment_records_invalid_json_outcome(monkeypatch):
    from src.judgment.engine import JudgmentError, run_judgment

    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setattr("src.judgment.engine.call_provider", _always_returns_invalid_json())
    tracker = UsageTracker()

    with pytest.raises(JudgmentError):
        run_judgment(WorldState(), tracker=tracker)

    assert len(tracker.outcomes) == 1
    assert all(o.outcome == "invalid_json" for o in tracker.outcomes)


def test_judgment_records_schema_validation_failed_outcome(monkeypatch):
    from src.judgment.engine import JudgmentError, run_judgment

    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setattr("src.judgment.engine.call_provider", _always_returns_schema_invalid())
    tracker = UsageTracker()

    with pytest.raises(JudgmentError):
        run_judgment(WorldState(), tracker=tracker)

    assert len(tracker.outcomes) == 1
    assert all(o.outcome == "schema_validation_failed" for o in tracker.outcomes)


# --- Planner: same loop shape as Judgment, lighter coverage ---

def test_planner_records_success_outcome(monkeypatch):
    from src.planner.engine import run_planner

    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setattr("src.planner.engine.call_provider", _always_succeeds(_MINIMAL_PLANNER))
    tracker = UsageTracker()

    result = run_planner(WorldState(), Judgment(**_MINIMAL_JUDGMENT), tracker=tracker)

    assert isinstance(result, Planner)
    assert len(tracker.outcomes) == 1
    assert tracker.outcomes[0].component == "Planner"
    assert tracker.outcomes[0].outcome == "success"


def test_planner_records_provider_call_error_outcome(monkeypatch):
    from src.planner.engine import PlannerError, run_planner

    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setattr("src.planner.engine.call_provider", _always_raises_provider_call_error())
    tracker = UsageTracker()

    with pytest.raises(PlannerError):
        run_planner(WorldState(), Judgment(**_MINIMAL_JUDGMENT), tracker=tracker)

    assert len(tracker.outcomes) == 1
    assert all(o.component == "Planner" and o.outcome == "provider_call_error" for o in tracker.outcomes)


# --- Response: same loop shape as Judgment, lighter coverage ---

def test_response_records_success_outcome(monkeypatch):
    from src.response.engine import run_response_generator

    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setattr("src.response.engine.call_provider", _always_succeeds(_MINIMAL_RESPONSE))
    tracker = UsageTracker()

    result = run_response_generator(
        WorldState(), Judgment(**_MINIMAL_JUDGMENT), Planner(**_MINIMAL_PLANNER), tracker=tracker
    )

    assert isinstance(result, Response)
    assert len(tracker.outcomes) == 1
    assert tracker.outcomes[0].component == "Response"
    assert tracker.outcomes[0].outcome == "success"


def test_response_records_schema_validation_failed_outcome_for_empty_text(monkeypatch):
    """Regression: this is the exact real gap found via a live Ollama
    dispatch (empty response_text passing validation silently, see
    engine/decisions.md) -- now that response_text rejects empty values,
    confirm the resulting ValidationError is recorded as a reliability
    failure, not silently lost."""
    from src.response.engine import ResponseGeneratorError, run_response_generator

    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setattr(
        "src.response.engine.call_provider",
        _always_succeeds({"response_text": "", "confidence": 0.5}),
    )
    tracker = UsageTracker()

    with pytest.raises(ResponseGeneratorError):
        run_response_generator(
            WorldState(), Judgment(**_MINIMAL_JUDGMENT), Planner(**_MINIMAL_PLANNER), tracker=tracker
        )

    assert len(tracker.outcomes) == 1
    assert all(o.component == "Response" and o.outcome == "schema_validation_failed" for o in tracker.outcomes)


# --- Interpretation: distinct control flow (breaks loop on first raw
# response; does not retry across providers for JSON/schema failures) ---

def test_interpretation_records_success_outcome(monkeypatch):
    from src.interpretation.engine import run_interpretation

    minimal_interp = {
        "urgency": "low",
        "impact_domains": ["professional"],
        "emotional_signals": [],
        "surface_complaint": "Wants to move teams.",
        "core_question": "Why is the move stalled?",
        "core_question_confidence": 0.4,
        "observed_facts": [],
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
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setattr("src.interpretation.engine.call_provider", _always_succeeds(minimal_interp))
    tracker = UsageTracker()

    run_interpretation("I want to move teams.", tracker=tracker)

    assert len(tracker.outcomes) == 1
    assert tracker.outcomes[0].component == "Interpretation"
    assert tracker.outcomes[0].provider == "openrouter"
    assert tracker.outcomes[0].outcome == "success"


def test_interpretation_records_provider_call_error_outcome_for_every_provider(monkeypatch):
    from src.interpretation.engine import InterpretationError, run_interpretation

    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setattr("src.interpretation.engine.call_provider", _always_raises_provider_call_error())
    tracker = UsageTracker()

    with pytest.raises(InterpretationError):
        run_interpretation("I want to move teams.", tracker=tracker)

    assert len(tracker.outcomes) == 1
    assert all(o.outcome == "provider_call_error" for o in tracker.outcomes)


def test_interpretation_records_invalid_json_outcome_once(monkeypatch):
    """Interpretation does NOT retry across providers for a JSON/schema
    failure -- only the ONE provider that returned raw content gets an
    outcome here, unlike Judgment/Planner/Response which retry every
    provider for every failure type."""
    from src.interpretation.engine import InterpretationError, run_interpretation

    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setattr("src.interpretation.engine.call_provider", _always_returns_invalid_json())
    tracker = UsageTracker()

    with pytest.raises(InterpretationError):
        run_interpretation("I want to move teams.", tracker=tracker)

    assert len(tracker.outcomes) == 1
    assert tracker.outcomes[0].provider == "openrouter"
    assert tracker.outcomes[0].outcome == "invalid_json"


def test_interpretation_records_schema_validation_failed_outcome_once(monkeypatch):
    from src.interpretation.engine import InterpretationError, run_interpretation

    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setattr("src.interpretation.engine.call_provider", _always_returns_schema_invalid())
    tracker = UsageTracker()

    with pytest.raises(InterpretationError):
        run_interpretation("I want to move teams.", tracker=tracker)

    assert len(tracker.outcomes) == 1
    assert tracker.outcomes[0].provider == "openrouter"
    assert tracker.outcomes[0].outcome == "schema_validation_failed"
