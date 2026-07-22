"""
Tests for src/planner/engine.py::apply_repeated_question_filter -- the
mechanical backstop against Planner re-selecting a question it (or a
prior turn) already asked. Added 2026-07-22 after a live 11-turn
walkthrough dispatch showed the prompt-only mandatory rule (see
src/planner/prompt.py) was followed inconsistently: the same question
recurred verbatim across several turns regardless. Pure Python, fully
unit-testable without a live LLM call -- same category as
tests/test_judgment_stagnation.py.
"""

from __future__ import annotations

from src.planner.engine import (
    REPEATED_QUESTION_OVERLAP_THRESHOLD,
    RECENT_QUESTIONS_WINDOW,
    apply_repeated_question_filter,
    strip_leaked_ids,
)
from src.planner.schema import Planner
from src.state.world_state import WorldState

_MINIMAL_PLANNER_FIELDS = dict(
    primary_objective="clarify uncertainty",
    rationale="Judgment identifies open unknowns blocking progress.",
    conversational_strategy="ask exploratory questions",
    resolution_blocker="missing information",
    desired_outcome="User identifies what they've tried and what's missing.",
    temporal_horizon="immediate",
    confidence=0.35,
)


def _planner(questions):
    return Planner(questions_to_explore=questions, **_MINIMAL_PLANNER_FIELDS)


def test_no_recent_questions_keeps_everything():
    state = WorldState()
    planner = _planner(["What steps has the user taken to move to the Product team?"])

    filtered, recent = apply_repeated_question_filter(state, planner)

    assert filtered.questions_to_explore == planner.questions_to_explore
    assert recent == planner.questions_to_explore


def test_exact_repeat_of_a_recent_question_is_dropped():
    """Regression test for the real, live-observed failure: the exact
    same question string recurred verbatim across several turns."""
    state = WorldState(recent_planner_questions=["What steps has the user taken to move to the Product team?"])
    planner = _planner([
        "What steps has the user taken to move to the Product team?",
        "What is preventing the user from moving to the Product team?",
    ])

    filtered, recent = apply_repeated_question_filter(state, planner)

    assert filtered.questions_to_explore == ["What is preventing the user from moving to the Product team?"]
    assert recent == [
        "What steps has the user taken to move to the Product team?",
        "What is preventing the user from moving to the Product team?",
    ]


def test_reworded_near_duplicate_is_also_dropped():
    """Not just exact string matches -- a heavily-overlapping rewording
    of the same question is caught too (see _question_overlap's own
    "larger of either direction" definition)."""
    state = WorldState(recent_planner_questions=["What are Sarah's potential reasons for not giving a clear explanation?"])
    planner = _planner(["What might be Sarah's reasons for not giving a clear explanation?"])

    filtered, _ = apply_repeated_question_filter(state, planner)

    assert filtered.questions_to_explore == []


def test_genuinely_different_question_is_kept():
    state = WorldState(recent_planner_questions=["What are Sarah's potential reasons for not giving a clear explanation?"])
    planner = _planner(["What is the nature of the freeze (e.g., hiring, promotion, project)?"])

    filtered, _ = apply_repeated_question_filter(state, planner)

    assert filtered.questions_to_explore == planner.questions_to_explore


def test_recent_questions_window_is_capped():
    state = WorldState(recent_planner_questions=[f"Old question {i}?" for i in range(RECENT_QUESTIONS_WINDOW)])
    planner = _planner(["A brand new question?"])

    _, recent = apply_repeated_question_filter(state, planner)

    assert len(recent) == RECENT_QUESTIONS_WINDOW
    assert recent[-1] == "A brand new question?"
    # The oldest entry fell off the window to make room for the new one.
    assert "Old question 0?" not in recent


def test_threshold_is_a_real_fraction():
    assert 0.0 < REPEATED_QUESTION_OVERLAP_THRESHOLD <= 1.0


def test_strip_leaked_ids_removes_a_real_observed_leak():
    """Regression test for a real, live-observed leak (2026-07-22): a
    live 11-turn walkthrough dispatch showed Planner echoing a raw
    WorldState item id back into questions_to_explore verbatim, despite
    src/planner/prompt.py's own explicit law against it."""
    planner = _planner([
        "What are Sarah's potential reasons for not giving a clear explanation? "
        "(id: 51eef282-70f4-45db-97fa-58270a357492)",
        "Has the user asked for a clear reason directly? (id: 2037e579-7562-42b6-a0f1-9ce6c8e384a4)",
    ])

    cleaned = strip_leaked_ids(planner)

    assert cleaned.questions_to_explore == [
        "What are Sarah's potential reasons for not giving a clear explanation?",
        "Has the user asked for a clear reason directly?",
    ]


def test_strip_leaked_ids_is_a_noop_when_nothing_leaked():
    planner = _planner(["What is the nature of the freeze?"])

    cleaned = strip_leaked_ids(planner)

    assert cleaned.questions_to_explore == planner.questions_to_explore


def test_strip_leaked_ids_covers_every_free_text_field():
    planner = Planner(
        primary_objective="clarify uncertainty (id: 8875d786-f352-4953-a586-2ceb465645f5)",
        rationale="Judgment identifies open unknowns. (id: 8875d786-f352-4953-a586-2ceb465645f5)",
        conversational_strategy="ask exploratory questions",
        resolution_blocker="missing information (id: 8875d786-f352-4953-a586-2ceb465645f5)",
        priority_topics=["Topic one (id: 8875d786-f352-4953-a586-2ceb465645f5)"],
        assumptions_to_test=["Assumes X (id: 8875d786-f352-4953-a586-2ceb465645f5)"],
        planning_constraints=["Preserve user agency (id: 8875d786-f352-4953-a586-2ceb465645f5)"],
        desired_outcome="User gains clarity. (id: 8875d786-f352-4953-a586-2ceb465645f5)",
        temporal_horizon="immediate",
        confidence=0.35,
    )

    cleaned = strip_leaked_ids(planner)

    assert "id:" not in cleaned.primary_objective
    assert "id:" not in cleaned.rationale
    assert "id:" not in cleaned.resolution_blocker
    assert "id:" not in cleaned.priority_topics[0]
    assert "id:" not in cleaned.assumptions_to_test[0]
    assert "id:" not in cleaned.planning_constraints[0]
    assert "id:" not in cleaned.desired_outcome
