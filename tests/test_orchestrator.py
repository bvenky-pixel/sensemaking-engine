"""
Tests for src/orchestrator/engine.py's run_turn -- System Architecture
v2's Orchestrator, first exercised as a real component after
Instrumentation. All deterministic: mocks each Sensemaking Engine stage's
run_X function at src.orchestrator.engine's own import path (not the
underlying LLM providers -- run_turn's job is coordinating those calls,
not making them), no real LLM calls.

The central thing under test is accurate partial-failure reporting: a
real bug existed in conversation_runner.py before Orchestrator existed --
it printed "State unchanged" on ANY failure, which was false whenever
Judgment, Planner, or Response Generator failed, since WorldState had
already been genuinely updated by that point (see engine/decisions.md).
Every test below that fails at judgment/planner/response confirms
`result.state` reflects the real, updated WorldState, not the original
input state.
"""

from __future__ import annotations

import pytest

from src.interpretation.engine import InterpretationError
from src.interpretation.schema import Interpretation
from src.judgment.engine import JudgmentError
from src.judgment.schema import Judgment
from src.orchestrator.engine import run_turn
from src.planner.engine import PlannerError
from src.planner.schema import Planner
from src.response.engine import ResponseGeneratorError
from src.response.schema import Response
from src.state.world_state import WorldState

_INTERP = Interpretation(
    urgency="low",
    impact_domains=["professional"],
    emotional_signals=[],
    surface_complaint="Wants to move teams.",
    core_question="Why is the move stalled?",
    core_question_confidence=0.4,
    observed_facts=["User wants to move to the Product team."],
    claims=[],
    goals=["Move to the Product team."],
    decision_options=[],
    has_assumption=False,
    assumption_check="No framing-embedded assumption detected.",
    assumptions=[],
    inferences=[],
    unknowns=[],
    biases=[],
    entities=[],
    clarity_score=0.5,
    requires_clarification=False,
    has_decision_event=False,
    decision_event_option="",
    decision_event_type="",
)

_JUDGMENT = Judgment(
    primary_problem="Transfer is stalled.",
    primary_goal="Move to the Product team.",
    current_focus="Understanding why it's stalled.",
    key_blockers=[],
    open_unknowns=[],
    active_decisions=[],
    contradictions=[],
    has_risk_signal=False,
    risk_scan="No risk-worthy signal identified.",
    risks=[],
    opportunities=[],
    has_decision_resolution=False,
    decision_resolution_option="",
    decision_resolution_status="",
    confidence=0.4,
    supporting_evidence=[],
)

_PLANNER = Planner(
    primary_objective="clarify uncertainty",
    rationale="Judgment identifies an unresolved blocker.",
    conversational_strategy="ask exploratory questions",
    resolution_blocker="missing information",
    priority_topics=[],
    questions_to_explore=[],
    assumptions_to_test=[],
    planning_constraints=[],
    desired_outcome="user gains clarity",
    temporal_horizon="immediate",
    confidence=0.4,
)

_RESPONSE = Response(response_text="It sounds like this has been unclear for a while.", confidence=0.4)


def test_run_turn_full_success_populates_every_field(monkeypatch):
    monkeypatch.setattr("src.orchestrator.engine.run_interpretation", lambda message, tracker=None: _INTERP)
    monkeypatch.setattr("src.orchestrator.engine.run_judgment", lambda state, tracker=None: _JUDGMENT)
    monkeypatch.setattr("src.orchestrator.engine.run_planner", lambda state, judgment, tracker=None: _PLANNER)
    monkeypatch.setattr(
        "src.orchestrator.engine.run_response_generator",
        lambda state, judgment, planner, tracker=None: _RESPONSE,
    )

    result = run_turn("I want to move teams.", WorldState())

    assert result.interpretation == _INTERP
    assert result.judgment == _JUDGMENT
    assert result.planner == _PLANNER
    assert result.response == _RESPONSE
    assert result.failed_stage is None
    assert result.error is None
    # WorldState was actually updated with the goal from Interpretation.
    assert any(g.content == "Move to the Product team." for g in result.state.goals)


def test_run_turn_interpretation_failure_leaves_state_genuinely_unchanged(monkeypatch):
    def _raise(message, tracker=None):
        raise InterpretationError("all providers failed")

    monkeypatch.setattr("src.orchestrator.engine.run_interpretation", _raise)

    original_state = WorldState()
    result = run_turn("I want to move teams.", original_state)

    assert result.failed_stage == "interpretation"
    assert result.error == "all providers failed"
    assert result.interpretation is None
    assert result.judgment is None
    # The one case where "state unchanged" is actually true -- Interpretation
    # never succeeded, so update_state was never called.
    assert result.state is original_state
    assert result.state.goals == []


def test_run_turn_judgment_failure_still_reports_the_real_updated_state(monkeypatch):
    """Regression test for the actual bug found while building Orchestrator:
    conversation_runner.py used to print "State unchanged" here even
    though WorldState HAD already been updated with Interpretation's
    content before Judgment ran and failed."""
    def _raise(state, tracker=None):
        raise JudgmentError("all providers failed")

    monkeypatch.setattr("src.orchestrator.engine.run_interpretation", lambda message, tracker=None: _INTERP)
    monkeypatch.setattr("src.orchestrator.engine.run_judgment", _raise)

    result = run_turn("I want to move teams.", WorldState())

    assert result.failed_stage == "judgment"
    assert result.error == "all providers failed"
    assert result.interpretation == _INTERP
    assert result.judgment is None
    assert result.planner is None
    assert result.response is None
    # The real bug: state DID change here, and must be reported as such.
    assert any(g.content == "Move to the Product team." for g in result.state.goals)


def test_run_turn_planner_failure_still_reports_judgment_and_updated_state(monkeypatch):
    def _raise(state, judgment, tracker=None):
        raise PlannerError("all providers failed")

    monkeypatch.setattr("src.orchestrator.engine.run_interpretation", lambda message, tracker=None: _INTERP)
    monkeypatch.setattr("src.orchestrator.engine.run_judgment", lambda state, tracker=None: _JUDGMENT)
    monkeypatch.setattr("src.orchestrator.engine.run_planner", _raise)

    result = run_turn("I want to move teams.", WorldState())

    assert result.failed_stage == "planner"
    assert result.interpretation == _INTERP
    assert result.judgment == _JUDGMENT
    assert result.planner is None
    assert result.response is None
    assert any(g.content == "Move to the Product team." for g in result.state.goals)


def test_run_turn_response_failure_still_reports_planner_and_updated_state(monkeypatch):
    def _raise(state, judgment, planner, tracker=None):
        raise ResponseGeneratorError("all providers failed")

    monkeypatch.setattr("src.orchestrator.engine.run_interpretation", lambda message, tracker=None: _INTERP)
    monkeypatch.setattr("src.orchestrator.engine.run_judgment", lambda state, tracker=None: _JUDGMENT)
    monkeypatch.setattr("src.orchestrator.engine.run_planner", lambda state, judgment, tracker=None: _PLANNER)
    monkeypatch.setattr("src.orchestrator.engine.run_response_generator", _raise)

    result = run_turn("I want to move teams.", WorldState())

    assert result.failed_stage == "response"
    assert result.interpretation == _INTERP
    assert result.judgment == _JUDGMENT
    assert result.planner == _PLANNER
    assert result.response is None
    assert any(g.content == "Move to the Product team." for g in result.state.goals)


def test_run_turn_never_raises_on_any_stage_failure(monkeypatch):
    """Orchestrator's whole point: a stage failure is data (a TurnResult),
    never an exception the caller has to catch."""
    def _raise(message, tracker=None):
        raise InterpretationError("boom")

    monkeypatch.setattr("src.orchestrator.engine.run_interpretation", _raise)

    try:
        result = run_turn("I want to move teams.", WorldState())
    except Exception as exc:  # pragma: no cover -- this is exactly what must NOT happen
        pytest.fail(f"run_turn raised instead of returning a TurnResult: {exc}")

    assert result.failed_stage == "interpretation"
