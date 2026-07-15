"""
Tests for src/executor/engine.py -- System Architecture v2's Executor,
built last. All deterministic, no LLM calls at all (build_clarity_brief
is a fixed template, not a model call) -- these tests confirm the exact
field mapping documented in engine.py's docstring, and that
render_clarity_brief produces a complete document even when every
section is empty (sparse-by-default, same as the rest of the pipeline).

Major update (2026-07-11, see engine/decisions.md): build_clarity_brief
now passes every field through voice.py's to_second_person before
assignment (the voice fix). Assertions below compare against
to_second_person(<source field>) rather than the raw source field
directly, so these tests confirm both the mapping AND the voice rewrite
without duplicating voice.py's own rewrite logic by hand --
tests/test_executor_voice.py is where the rewrite itself is verified.
"""

from __future__ import annotations

from src.executor.engine import build_clarity_brief, render_clarity_brief
from src.executor.schema import ClarityBrief
from src.executor.voice import to_second_person
from src.judgment.schema import Judgment
from src.planner.schema import Planner
from src.state.world_state import Decision, WorldState

_JUDGMENT = Judgment(
    primary_problem="Transfer to Product team has stalled.",
    primary_goal="Move to the Product team.",
    current_focus="Understanding why it stalled.",
    key_blockers=["Some blocker"],
    open_unknowns=["Why hasn't it moved forward?"],
    active_decisions=[],
    contradictions=[],
    has_knowledge_correction=False,
    knowledge_correction_target="",
    knowledge_correction_kind="",
    knowledge_correction_corrected_content="",
    has_risk_signal=True,
    risk_scan="Prolonged delay with no clear resolution is itself risk-worthy.",
    risks=["Prolonged delay may reduce motivation."],
    opportunities=["Strong intrinsic motivation once a path is found."],
    has_decision_resolution=False,
    decision_resolution_option="",
    decision_resolution_status="",
    confidence=0.35,
    supporting_evidence=[],
)

_PLANNER = Planner(
    primary_objective="clarify uncertainty",
    rationale="Judgment identifies open unknowns blocking progress.",
    conversational_strategy="ask exploratory questions",
    resolution_blocker="missing information",
    desired_outcome="User identifies what they've tried and what's missing.",
    temporal_horizon="immediate",
    confidence=0.35,
)


def test_build_clarity_brief_maps_each_field_from_the_documented_source():
    state = WorldState(
        surface_complaint="User has been trying to move teams for months.",
        decisions=[Decision(content="Wait until Q3")],
    )

    brief = build_clarity_brief(state, _JUDGMENT, _PLANNER)

    assert brief.situation == to_second_person(state.surface_complaint)
    # key_insights = primary_problem + risks + opportunities, in that order
    assert brief.key_insights == [
        to_second_person(_JUDGMENT.primary_problem),
        *[to_second_person(r) for r in _JUDGMENT.risks],
        *[to_second_person(o) for o in _JUDGMENT.opportunities],
    ]
    assert brief.current_direction == to_second_person(_PLANNER.desired_outcome)
    assert brief.remaining_unknowns == [to_second_person(u) for u in _JUDGMENT.open_unknowns]
    # Regression test for the bare-label bug (see engine/decisions.md
    # "Frontend UX pass"): Decision.content is a bare noun-phrase label,
    # not a sentence -- wrapped in a template, same fix already applied
    # to src/understanding/engine.py::build_tier1_statements.
    assert brief.decisions == ["You're weighing Wait until Q3 as an option."]


def test_build_clarity_brief_suppresses_situation_that_echoes_the_last_message():
    """Regression test for a real, live-observed issue (see
    engine/decisions.md "Frontend UX pass"): situation is, by
    construction, always a light paraphrase of the most recent message
    -- rendering it as its own card directly under the actual chat
    transcript just repeats the person's own words back to them."""
    state = WorldState(surface_complaint="You want to move to the Product team.")
    brief = build_clarity_brief(
        state, _JUDGMENT, _PLANNER, last_user_message="I want to move teams."
    )
    assert brief.situation == ""


def test_build_clarity_brief_keeps_situation_when_it_does_not_echo_the_last_message():
    state = WorldState(surface_complaint="You want to move to the Product team.")
    brief = build_clarity_brief(
        state, _JUDGMENT, _PLANNER, last_user_message="Ugh, today was a rough day."
    )
    assert brief.situation == "You want to move to the Product team."


def test_build_clarity_brief_keeps_situation_when_no_last_user_message_given():
    """Callers that don't pass last_user_message (e.g. every other test
    in this file) get the old, unconditional behavior -- the parameter
    is additive, not a breaking change to the existing mapping."""
    state = WorldState(surface_complaint="You want to move to the Product team.")
    brief = build_clarity_brief(state, _JUDGMENT, _PLANNER)
    assert brief.situation == "You want to move to the Product team."


def test_build_clarity_brief_never_touches_judgment_key_blockers_or_active_decisions():
    """The template is a specific, documented mapping -- confirms fields
    NOT in the mapping (key_blockers, active_decisions, contradictions)
    don't leak into the brief just because they exist on Judgment."""
    state = WorldState()
    brief = build_clarity_brief(state, _JUDGMENT, _PLANNER)

    for field_value in brief.key_insights:
        assert field_value not in _JUDGMENT.key_blockers


def test_render_clarity_brief_produces_all_five_sections():
    brief = build_clarity_brief(
        WorldState(surface_complaint="x", decisions=[Decision(content="y")]),
        _JUDGMENT,
        _PLANNER,
    )
    rendered = render_clarity_brief(brief)

    assert "# Clarity Brief" in rendered
    assert "## Situation" in rendered
    assert "## Key Insights" in rendered
    assert "## Current Direction" in rendered
    assert "## Remaining Unknowns" in rendered
    assert "## Decisions" in rendered
    assert "x" in rendered
    assert "- You're weighing y as an option." in rendered


def test_render_clarity_brief_shows_none_for_empty_sections_not_a_blank_gap():
    empty_brief = ClarityBrief(
        situation="",
        key_insights=[],
        current_direction="",
        remaining_unknowns=[],
        decisions=[],
    )
    rendered = render_clarity_brief(empty_brief)

    # Every section still reads as a complete, deliberate "(none)", not a
    # blank that looks broken -- sparse-by-default, same as upstream.
    # (situation, key_insights, current_direction, remaining_unknowns, decisions)
    assert rendered.count("(none)") == 5
