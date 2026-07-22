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

Major update (2026-07-22, see engine/decisions.md and
engine/specs/clarity-brief-specification-v1.md "The Eight Sections"):
four new sections (known_facts, competing_priorities, contradictions,
emerging_patterns), and situation's SOURCE changes from
WorldState.surface_complaint to Judgment.situation_assessment (falling
back to primary_problem) -- the five original fields and their mappings
are otherwise unchanged. `_JUDGMENT` below deliberately leaves
situation_assessment at its default ("") so existing tests exercise the
fallback path; a dedicated test below confirms situation_assessment
takes precedence when populated.
"""

from __future__ import annotations

from src.executor.engine import build_clarity_brief, diff_clarity_briefs, render_clarity_brief
from src.executor.schema import ClarityBrief
from src.executor.voice import to_second_person
from src.judgment.schema import Judgment
from src.planner.schema import Planner
from src.state.world_state import Decision, Fact, Provenance, WorldState
from src.understanding.schema import UnderstandingState, UnderstandingStatement

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

    # situation falls back to primary_problem since _JUDGMENT.situation_assessment
    # is "" -- surface_complaint is NO LONGER the source at all (see module
    # docstring above).
    assert brief.situation == to_second_person(_JUDGMENT.primary_problem)
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


def test_build_clarity_brief_sources_situation_from_situation_assessment_when_present():
    """situation_assessment takes precedence over primary_problem when
    populated -- the whole point of the v2 source change (see engine.py's
    module docstring's `situation` mapping entry)."""
    judgment = _JUDGMENT.model_copy(
        update={"situation_assessment": "A stalled internal career transition."}
    )
    brief = build_clarity_brief(WorldState(), judgment, _PLANNER)
    assert brief.situation == to_second_person("A stalled internal career transition.")


def test_build_clarity_brief_suppresses_situation_that_echoes_the_last_message():
    """Regression test for a real, live-observed issue (see
    engine/decisions.md "Frontend UX pass"): situation used to be, by
    construction, always a light paraphrase of the most recent message.
    The echo-suppression check still runs defensively against whichever
    text ends up in `situation`, regardless of source."""
    judgment = _JUDGMENT.model_copy(
        update={"situation_assessment": "You want to move to the Product team."}
    )
    brief = build_clarity_brief(
        WorldState(), judgment, _PLANNER, last_user_message="I want to move teams."
    )
    assert brief.situation == ""


def test_build_clarity_brief_keeps_situation_when_it_does_not_echo_the_last_message():
    judgment = _JUDGMENT.model_copy(
        update={"situation_assessment": "You want to move to the Product team."}
    )
    brief = build_clarity_brief(
        WorldState(), judgment, _PLANNER, last_user_message="Ugh, today was a rough day."
    )
    assert brief.situation == "You want to move to the Product team."


def test_build_clarity_brief_keeps_situation_when_no_last_user_message_given():
    """Callers that don't pass last_user_message (e.g. every other test
    in this file) get the old, unconditional behavior -- the parameter
    is additive, not a breaking change to the existing mapping."""
    brief = build_clarity_brief(WorldState(), _JUDGMENT, _PLANNER)
    assert brief.situation == to_second_person(_JUDGMENT.primary_problem)


def test_build_clarity_brief_excludes_resolved_and_expired_decisions():
    """Regression test: build_clarity_brief used to render state.decisions
    with no status filter at all, so a resolved or expired decision never
    left the "In play" section -- it just accumulated there forever
    alongside genuinely open ones. Only "open"/"deferred" belong here;
    "resolved"/"expired" no longer read as something still being weighed."""
    state = WorldState(
        decisions=[
            Decision(content="Still open option", status="open"),
            Decision(content="Deferred option", status="deferred"),
            Decision(content="Already resolved option", status="resolved"),
            Decision(content="Expired option", status="expired"),
        ],
    )
    brief = build_clarity_brief(state, _JUDGMENT, _PLANNER)

    assert brief.decisions == [
        "You're weighing Still open option as an option.",
        "You're weighing Deferred option as an option.",
    ]


def test_build_clarity_brief_never_touches_judgment_key_blockers_or_active_decisions():
    """The template is a specific, documented mapping -- confirms fields
    NOT in the mapping (key_blockers, active_decisions) don't leak into
    the brief just because they exist on Judgment. contradictions IS now
    in the mapping (see test_build_clarity_brief_maps_contradictions_and_significance
    below) -- this test no longer claims otherwise."""
    state = WorldState()
    brief = build_clarity_brief(state, _JUDGMENT, _PLANNER)

    for field_value in brief.key_insights:
        assert field_value not in _JUDGMENT.key_blockers


def test_build_clarity_brief_maps_known_facts_capped_and_recency_ordered():
    """known_facts <- WorldState.facts, filtered to status="active" and
    capped to the _KNOWN_FACTS_CAP most-recently-updated -- a new
    Executor-level template, not a Judgment field."""
    state = WorldState(
        facts=[
            Fact(
                content="Oldest active fact.",
                status="active",
                provenance=Provenance(source="interpretation", first_seen=1, last_updated=1),
            ),
            Fact(
                content="Newest active fact.",
                status="active",
                provenance=Provenance(source="interpretation", first_seen=2, last_updated=5),
            ),
            Fact(
                content="Retracted fact, should not appear.",
                status="retracted",
                provenance=Provenance(source="interpretation", first_seen=1, last_updated=10),
            ),
        ],
    )
    brief = build_clarity_brief(state, _JUDGMENT, _PLANNER)

    assert brief.known_facts == [
        to_second_person("Newest active fact."),
        to_second_person("Oldest active fact."),
    ]


def test_build_clarity_brief_caps_known_facts():
    state = WorldState(
        facts=[
            Fact(
                content=f"Active fact {i}.",
                status="active",
                provenance=Provenance(source="interpretation", first_seen=1, last_updated=i),
            )
            for i in range(10)
        ],
    )
    brief = build_clarity_brief(state, _JUDGMENT, _PLANNER)
    assert len(brief.known_facts) == 5
    # Most-recently-updated (highest last_updated) survive the cap.
    assert brief.known_facts[0] == to_second_person("Active fact 9.")


def test_build_clarity_brief_maps_competing_priorities():
    judgment = _JUDGMENT.model_copy(
        update={
            "competing_priorities": [
                "Pushing harder for the Product team move risks straining "
                "the relationship with Sarah that the user also wants to protect."
            ]
        }
    )
    brief = build_clarity_brief(WorldState(), judgment, _PLANNER)
    assert brief.competing_priorities == [
        to_second_person(
            "Pushing harder for the Product team move risks straining "
            "the relationship with Sarah that the user also wants to protect."
        )
    ]


def test_build_clarity_brief_maps_contradictions_and_significance():
    """contradictions <- Judgment.contradictions, with
    contradiction_significance appended as the final entry when
    non-empty. Previously NEVER mapped at all -- see engine.py's module
    docstring for why this is the highest-leverage change in this
    rollout."""
    judgment = _JUDGMENT.model_copy(
        update={
            "contradictions": [
                "Manager says user is doing great, but user was passed over "
                "for the promotion."
            ],
            "contradiction_significance": (
                "Career advancement appears blocked despite positive "
                "performance signals."
            ),
        }
    )
    brief = build_clarity_brief(WorldState(), judgment, _PLANNER)
    assert brief.contradictions == [
        to_second_person(
            "Manager says user is doing great, but user was passed over "
            "for the promotion."
        ),
        to_second_person(
            "Career advancement appears blocked despite positive "
            "performance signals."
        ),
    ]


def test_build_clarity_brief_omits_significance_when_empty():
    judgment = _JUDGMENT.model_copy(
        update={"contradictions": ["A vs. B contradiction."], "contradiction_significance": ""}
    )
    brief = build_clarity_brief(WorldState(), judgment, _PLANNER)
    assert brief.contradictions == [to_second_person("A vs. B contradiction.")]


def test_build_clarity_brief_maps_emerging_patterns_from_tier2():
    """emerging_patterns <- WorldState.understanding.tier2 -- a reframe
    of the existing "Putting it together" content, not a new build."""
    state = WorldState(
        understanding=UnderstandingState(
            tier2=[
                UnderstandingStatement(
                    id="tier2:synthesis:abc123",
                    tier=2,
                    kind="synthesis",
                    text="A pattern connecting two goals.",
                    grounding_item_ids=["goal:1", "goal:2"],
                )
            ]
        )
    )
    brief = build_clarity_brief(state, _JUDGMENT, _PLANNER)
    assert brief.emerging_patterns == [to_second_person("A pattern connecting two goals.")]


def test_render_clarity_brief_produces_all_nine_sections():
    judgment = _JUDGMENT.model_copy(update={"situation_assessment": "x"})
    brief = build_clarity_brief(
        WorldState(decisions=[Decision(content="y")]),
        judgment,
        _PLANNER,
    )
    rendered = render_clarity_brief(brief)

    assert "# Clarity Brief" in rendered
    assert "## Situation" in rendered
    assert "## Key Insights" in rendered
    assert "## Current Direction" in rendered
    assert "## Known Facts" in rendered
    assert "## Remaining Unknowns" in rendered
    assert "## Competing Priorities" in rendered
    assert "## Contradictions" in rendered
    assert "## Decisions" in rendered
    assert "## Emerging Patterns" in rendered
    assert "x" in rendered
    assert "- You're weighing y as an option." in rendered


def test_render_clarity_brief_shows_none_for_empty_sections_not_a_blank_gap():
    empty_brief = ClarityBrief(
        situation="",
        key_insights=[],
        current_direction="",
        remaining_unknowns=[],
        decisions=[],
        known_facts=[],
        competing_priorities=[],
        contradictions=[],
        emerging_patterns=[],
    )
    rendered = render_clarity_brief(empty_brief)

    # Every section still reads as a complete, deliberate "(none)", not a
    # blank that looks broken -- sparse-by-default, same as upstream.
    # (situation, key_insights, current_direction, known_facts,
    # remaining_unknowns, competing_priorities, contradictions, decisions,
    # emerging_patterns)
    assert rendered.count("(none)") == 9


def _brief(**overrides) -> ClarityBrief:
    defaults = dict(
        situation="",
        key_insights=[],
        current_direction="",
        remaining_unknowns=[],
        decisions=[],
        known_facts=[],
        competing_priorities=[],
        contradictions=[],
        emerging_patterns=[],
    )
    defaults.update(overrides)
    return ClarityBrief(**defaults)


def test_diff_clarity_briefs_returns_empty_list_when_no_previous_brief():
    """A session's first completed turn has nothing to have changed FROM
    yet -- previous=None is a real, common case, not a degenerate one."""
    assert diff_clarity_briefs(None, _brief(contradictions=["X vs. Y."])) == []


def test_diff_clarity_briefs_reports_new_contradiction():
    previous = _brief()
    current = _brief(contradictions=["Manager says great, but passed over."])
    assert diff_clarity_briefs(previous, current) == [
        "A new contradiction surfaced: Manager says great, but passed over."
    ]


def test_diff_clarity_briefs_reports_resolved_decision():
    previous = _brief(decisions=["You're weighing House as an option."])
    current = _brief(decisions=[])
    assert diff_clarity_briefs(previous, current) == [
        "No longer weighing this: You're weighing House as an option."
    ]


def test_diff_clarity_briefs_reports_resolved_unknown():
    previous = _brief(remaining_unknowns=["Why hasn't it moved forward?"])
    current = _brief(remaining_unknowns=[])
    assert diff_clarity_briefs(previous, current) == [
        "This has been resolved: Why hasn't it moved forward?"
    ]


def test_diff_clarity_briefs_reports_new_competing_priority():
    previous = _brief()
    current = _brief(competing_priorities=["Autonomy vs. protecting the relationship."])
    assert diff_clarity_briefs(previous, current) == [
        "A new competing priority emerged: Autonomy vs. protecting the relationship."
    ]


def test_diff_clarity_briefs_does_not_report_new_emerging_patterns():
    """emerging_patterns deliberately does NOT feed "what changed"
    (2026-07-22, direct founder redirect: "putting it together is not
    as valuable... we are literally putting together my words") -- same
    reason the frontend no longer renders a "Putting it together" card."""
    previous = _brief()
    current = _brief(emerging_patterns=["A pattern connecting two goals."])
    assert diff_clarity_briefs(previous, current) == []


def test_diff_clarity_briefs_ignores_mere_reordering():
    """Compared by membership, not position -- Judgment listing the same
    content in a different order is never reported as a change."""
    previous = _brief(contradictions=["A vs. B.", "C vs. D."])
    current = _brief(contradictions=["C vs. D.", "A vs. B."])
    assert diff_clarity_briefs(previous, current) == []


def test_diff_clarity_briefs_returns_empty_list_when_nothing_changed():
    previous = _brief(situation="x", key_insights=["y"], decisions=["z"])
    current = _brief(situation="x", key_insights=["y"], decisions=["z"])
    assert diff_clarity_briefs(previous, current) == []


def test_diff_clarity_briefs_combines_multiple_kinds_of_change_in_one_call():
    previous = _brief(
        remaining_unknowns=["Q1?"],
        decisions=["You're weighing House as an option."],
    )
    current = _brief(
        contradictions=["New contradiction."],
        competing_priorities=["New tension."],
    )
    assert diff_clarity_briefs(previous, current) == [
        "A new contradiction surfaced: New contradiction.",
        "No longer weighing this: You're weighing House as an option.",
        "This has been resolved: Q1?",
        "A new competing priority emerged: New tension.",
    ]
