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
from src.insight.schema import Insight
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
    has_knowledge_correction=False,
    knowledge_correction_target="",
    knowledge_correction_kind="",
    knowledge_correction_corrected_content="",
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
    monkeypatch.setattr("src.orchestrator.engine.run_judgment", lambda state, tracker=None, retrieved_context="": _JUDGMENT)
    monkeypatch.setattr("src.orchestrator.engine.run_planner", lambda state, judgment, tracker=None, mode=None: _PLANNER)
    monkeypatch.setattr(
        "src.orchestrator.engine.run_response_generator",
        lambda state, judgment, planner, tracker=None, mode=None, pom=None, insights=None: _RESPONSE,
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


def test_run_turn_threads_mode_to_planner_and_response(monkeypatch):
    """Counseling modes (see engine/decisions.md, src/orchestrator/modes.py):
    run_turn's own `mode` parameter must reach both run_planner and
    run_response_generator -- the two stages whose prompts reference it --
    unchanged, not just be accepted and dropped."""
    seen = {}

    def _planner(state, judgment, tracker=None, mode=None):
        seen["planner_mode"] = mode
        return _PLANNER

    def _response(state, judgment, planner, tracker=None, mode=None, pom=None, insights=None):
        seen["response_mode"] = mode
        return _RESPONSE

    monkeypatch.setattr("src.orchestrator.engine.run_interpretation", lambda message, tracker=None: _INTERP)
    monkeypatch.setattr("src.orchestrator.engine.run_judgment", lambda state, tracker=None, retrieved_context="": _JUDGMENT)
    monkeypatch.setattr("src.orchestrator.engine.run_planner", _planner)
    monkeypatch.setattr("src.orchestrator.engine.run_response_generator", _response)

    run_turn("I want to move teams.", WorldState(), mode="vent")

    assert seen["planner_mode"] == "vent"
    assert seen["response_mode"] == "vent"


def test_run_turn_threads_insights_to_response_only(monkeypatch):
    """Insight-triggered conversational callback (2026-07-19, backlog
    #210): run_turn's own `insights` parameter must reach
    run_response_generator unchanged -- the one stage that resolves a
    callback from it (see src.insight.engine.select_relevant_insight);
    run_judgment/run_planner never receive it directly."""
    seen = {}
    insights = [Insight(theme="Avoidance", detail="Delays hard conversations.")]

    def _response(state, judgment, planner, tracker=None, mode=None, pom=None, insights=None):
        seen["response_insights"] = insights
        return _RESPONSE

    monkeypatch.setattr("src.orchestrator.engine.run_interpretation", lambda message, tracker=None: _INTERP)
    monkeypatch.setattr("src.orchestrator.engine.run_judgment", lambda state, tracker=None, retrieved_context="": _JUDGMENT)
    monkeypatch.setattr("src.orchestrator.engine.run_planner", lambda state, judgment, tracker=None, mode=None: _PLANNER)
    monkeypatch.setattr("src.orchestrator.engine.run_response_generator", _response)

    run_turn("I want to move teams.", WorldState(), insights=insights)

    assert seen["response_insights"] == insights


def test_run_turn_defaults_insights_to_none(monkeypatch):
    """Every existing caller that doesn't pass `insights` at all must
    still work, seeing None -- same no-op default discipline as `pom`."""
    seen = {}

    def _response(state, judgment, planner, tracker=None, mode=None, pom=None, insights=None):
        seen["response_insights"] = insights
        return _RESPONSE

    monkeypatch.setattr("src.orchestrator.engine.run_interpretation", lambda message, tracker=None: _INTERP)
    monkeypatch.setattr("src.orchestrator.engine.run_judgment", lambda state, tracker=None, retrieved_context="": _JUDGMENT)
    monkeypatch.setattr("src.orchestrator.engine.run_planner", lambda state, judgment, tracker=None, mode=None: _PLANNER)
    monkeypatch.setattr("src.orchestrator.engine.run_response_generator", _response)

    run_turn("I want to move teams.", WorldState())

    assert seen["response_insights"] is None


def test_run_turn_resolves_adaptive_mode_to_planners_chosen_lens_for_response(monkeypatch):
    """Synthesis (see engine/decisions.md "Synthesis"): when mode is
    "adaptive", Planner itself picks which concrete lens fits this turn
    and reports it on Planner.active_lens -- run_turn must pass THAT
    concrete lens to Response, not the literal string "adaptive" (which
    has no RESPONSE_MODE_FOCUS entry of its own)."""
    seen = {}

    def _planner(state, judgment, tracker=None, mode=None):
        seen["planner_mode"] = mode
        return _PLANNER.model_copy(update={"active_lens": "commit"})

    def _response(state, judgment, planner, tracker=None, mode=None, pom=None, insights=None):
        seen["response_mode"] = mode
        return _RESPONSE

    monkeypatch.setattr("src.orchestrator.engine.run_interpretation", lambda message, tracker=None: _INTERP)
    monkeypatch.setattr("src.orchestrator.engine.run_judgment", lambda state, tracker=None, retrieved_context="": _JUDGMENT)
    monkeypatch.setattr("src.orchestrator.engine.run_planner", _planner)
    monkeypatch.setattr("src.orchestrator.engine.run_response_generator", _response)

    run_turn("I said I'd do this weeks ago.", WorldState(), mode="adaptive")

    assert seen["planner_mode"] == "adaptive"
    assert seen["response_mode"] == "commit"


def test_run_turn_falls_back_to_raw_mode_when_adaptive_planner_sets_no_lens(monkeypatch):
    """If Planner fails to set active_lens on an Adaptive-mode turn (e.g.
    a provider that ignores the instruction), Response must still get
    SOME value -- falling back to the raw "adaptive" string, which
    response_mode_focus_note gracefully turns into "" (no focus note),
    rather than crashing or silently reusing a stale prior lens."""
    seen = {}

    def _planner(state, judgment, tracker=None, mode=None):
        return _PLANNER  # active_lens defaults to None

    def _response(state, judgment, planner, tracker=None, mode=None, pom=None, insights=None):
        seen["response_mode"] = mode
        return _RESPONSE

    monkeypatch.setattr("src.orchestrator.engine.run_interpretation", lambda message, tracker=None: _INTERP)
    monkeypatch.setattr("src.orchestrator.engine.run_judgment", lambda state, tracker=None, retrieved_context="": _JUDGMENT)
    monkeypatch.setattr("src.orchestrator.engine.run_planner", _planner)
    monkeypatch.setattr("src.orchestrator.engine.run_response_generator", _response)

    run_turn("I want to move teams.", WorldState(), mode="adaptive")

    assert seen["response_mode"] == "adaptive"


def test_run_turn_threads_retrieved_context_to_judgment_only(monkeypatch):
    """Retrieval v1 (see engine/decisions.md "Retrieval",
    src/retrieval/engine.py): run_turn's own `retrieved_context` parameter
    must reach run_judgment, the one stage whose prompt references it --
    Planner/Response never receive it directly."""
    seen = {}

    def _judgment(state, tracker=None, retrieved_context=""):
        seen["judgment_retrieved_context"] = retrieved_context
        return _JUDGMENT

    monkeypatch.setattr("src.orchestrator.engine.run_interpretation", lambda message, tracker=None: _INTERP)
    monkeypatch.setattr("src.orchestrator.engine.run_judgment", _judgment)
    monkeypatch.setattr("src.orchestrator.engine.run_planner", lambda state, judgment, tracker=None, mode=None: _PLANNER)
    monkeypatch.setattr(
        "src.orchestrator.engine.run_response_generator",
        lambda state, judgment, planner, tracker=None, mode=None, pom=None, insights=None: _RESPONSE,
    )

    run_turn("I want to move teams.", WorldState(), retrieved_context="Known pattern: reopens closed decisions.")

    assert seen["judgment_retrieved_context"] == "Known pattern: reopens closed decisions."


def test_run_turn_defaults_retrieved_context_to_empty_string(monkeypatch):
    """Every existing caller that doesn't pass `retrieved_context` at all
    must still work, seeing "" -- same no-op default discipline as
    `mode` above."""
    seen = {}

    def _judgment(state, tracker=None, retrieved_context=""):
        seen["judgment_retrieved_context"] = retrieved_context
        return _JUDGMENT

    monkeypatch.setattr("src.orchestrator.engine.run_interpretation", lambda message, tracker=None: _INTERP)
    monkeypatch.setattr("src.orchestrator.engine.run_judgment", _judgment)
    monkeypatch.setattr("src.orchestrator.engine.run_planner", lambda state, judgment, tracker=None, mode=None: _PLANNER)
    monkeypatch.setattr(
        "src.orchestrator.engine.run_response_generator",
        lambda state, judgment, planner, tracker=None, mode=None, pom=None, insights=None: _RESPONSE,
    )

    run_turn("I want to move teams.", WorldState())

    assert seen["judgment_retrieved_context"] == ""


def test_run_turn_defaults_mode_to_none(monkeypatch):
    """Every existing caller (conversation_runner.py, the walkthrough
    script, every other test in this file) never passes `mode` at all --
    must default to None, not break or require it."""
    seen = {}

    def _planner(state, judgment, tracker=None, mode=None):
        seen["planner_mode"] = mode
        return _PLANNER

    monkeypatch.setattr("src.orchestrator.engine.run_interpretation", lambda message, tracker=None: _INTERP)
    monkeypatch.setattr("src.orchestrator.engine.run_judgment", lambda state, tracker=None, retrieved_context="": _JUDGMENT)
    monkeypatch.setattr("src.orchestrator.engine.run_planner", _planner)
    monkeypatch.setattr(
        "src.orchestrator.engine.run_response_generator",
        lambda state, judgment, planner, tracker=None, mode=None, pom=None, insights=None: _RESPONSE,
    )

    run_turn("I want to move teams.", WorldState())

    assert seen["planner_mode"] is None


def test_run_turn_calls_update_tier2_after_corrections_before_planner(monkeypatch):
    """Wiring regression guard for engine/decisions.md "Tier 2 design":
    update_tier2 must run as part of the real turn sequence, after
    WorldState is fully updated (including Judgment-driven corrections)
    but the actual recompute decision/LLM call is update_tier2's own
    responsibility (see tests/test_tier2.py), not asserted here."""
    monkeypatch.setattr("src.orchestrator.engine.run_interpretation", lambda message, tracker=None: _INTERP)
    monkeypatch.setattr("src.orchestrator.engine.run_judgment", lambda state, tracker=None, retrieved_context="": _JUDGMENT)
    monkeypatch.setattr("src.orchestrator.engine.run_planner", lambda state, judgment, tracker=None, mode=None: _PLANNER)
    monkeypatch.setattr(
        "src.orchestrator.engine.run_response_generator",
        lambda state, judgment, planner, tracker=None, mode=None, pom=None, insights=None: _RESPONSE,
    )

    calls = []

    def _fake_update_tier2(state, tracker=None):
        calls.append(state)
        return state

    monkeypatch.setattr("src.orchestrator.engine.update_tier2", _fake_update_tier2)

    result = run_turn("I want to move teams.", WorldState())

    assert len(calls) == 1
    # The state update_tier2 saw already has the goal from Interpretation
    # -- i.e. it ran after update_state, not before.
    assert any(g.content == "Move to the Product team." for g in calls[0].goals)
    assert result.failed_stage is None


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
    def _raise(state, tracker=None, retrieved_context=""):
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
    def _raise(state, judgment, tracker=None, mode=None):
        raise PlannerError("all providers failed")

    monkeypatch.setattr("src.orchestrator.engine.run_interpretation", lambda message, tracker=None: _INTERP)
    monkeypatch.setattr("src.orchestrator.engine.run_judgment", lambda state, tracker=None, retrieved_context="": _JUDGMENT)
    monkeypatch.setattr("src.orchestrator.engine.run_planner", _raise)

    result = run_turn("I want to move teams.", WorldState())

    assert result.failed_stage == "planner"
    assert result.interpretation == _INTERP
    assert result.judgment == _JUDGMENT
    assert result.planner is None
    assert result.response is None
    assert any(g.content == "Move to the Product team." for g in result.state.goals)


def test_run_turn_response_failure_still_reports_planner_and_updated_state(monkeypatch):
    def _raise(state, judgment, planner, tracker=None, mode=None, pom=None, insights=None):
        raise ResponseGeneratorError("all providers failed")

    monkeypatch.setattr("src.orchestrator.engine.run_interpretation", lambda message, tracker=None: _INTERP)
    monkeypatch.setattr("src.orchestrator.engine.run_judgment", lambda state, tracker=None, retrieved_context="": _JUDGMENT)
    monkeypatch.setattr("src.orchestrator.engine.run_planner", lambda state, judgment, tracker=None, mode=None: _PLANNER)
    monkeypatch.setattr("src.orchestrator.engine.run_response_generator", _raise)

    result = run_turn("I want to move teams.", WorldState())

    assert result.failed_stage == "response"
    assert result.interpretation == _INTERP
    assert result.judgment == _JUDGMENT
    assert result.planner == _PLANNER
    assert result.response is None
    assert any(g.content == "Move to the Product team." for g in result.state.goals)


def test_run_turn_retries_a_failed_stage_once_and_succeeds_on_the_second_attempt(monkeypatch):
    """Bounded single-stage retry (2026-07-19, backlog #250, see
    engine/decisions.md "Orchestrator: bounded single-stage retry") --
    the founder's own explicit choice. A stage that fails on its first
    attempt but succeeds on an independent second attempt must recover
    the turn, not report failed_stage."""
    calls = {"n": 0}

    def _judgment(state, tracker=None, retrieved_context=""):
        calls["n"] += 1
        if calls["n"] == 1:
            raise JudgmentError("transient failure")
        return _JUDGMENT

    monkeypatch.setattr("src.orchestrator.engine.run_interpretation", lambda message, tracker=None: _INTERP)
    monkeypatch.setattr("src.orchestrator.engine.run_judgment", _judgment)
    monkeypatch.setattr("src.orchestrator.engine.run_planner", lambda state, judgment, tracker=None, mode=None: _PLANNER)
    monkeypatch.setattr(
        "src.orchestrator.engine.run_response_generator",
        lambda state, judgment, planner, tracker=None, mode=None, pom=None, insights=None: _RESPONSE,
    )

    result = run_turn("I want to move teams.", WorldState())

    assert calls["n"] == 2
    assert result.failed_stage is None
    assert result.judgment == _JUDGMENT


def test_run_turn_gives_up_after_exactly_two_attempts_at_a_failing_stage(monkeypatch):
    """The retry is bounded to exactly one extra attempt, never a loop --
    a stage that fails twice in a row must report failed_stage after
    precisely 2 calls, not retry indefinitely."""
    calls = {"n": 0}

    def _raise(message, tracker=None):
        calls["n"] += 1
        raise InterpretationError("still failing")

    monkeypatch.setattr("src.orchestrator.engine.run_interpretation", _raise)

    result = run_turn("I want to move teams.", WorldState())

    assert calls["n"] == 2
    assert result.failed_stage == "interpretation"
    assert result.error == "still failing"


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
