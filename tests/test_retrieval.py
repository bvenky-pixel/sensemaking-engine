"""
Tests for src/retrieval/engine.py -- Retrieval v1 (see engine/decisions.md
"Retrieval"). Pure formatting function, no mocking needed, same style as
tests/test_learning.py.
"""

from __future__ import annotations

from src.insight.schema import Insight
from src.learning.engine import Pattern
from src.pom.schema import (
    IdentitySystem,
    MotivationSystem,
    NarrativeSystem,
    PersonalOperatingModel,
    StressSystem,
    TheoryOfMindEntry,
    TheoryOfMindSystem,
)
from src.retrieval.engine import build_retrieved_context


def _pattern(pattern_type="decision_reversal", detail="Often reopens closed decisions", evidence_count=3):
    return Pattern(pattern_type=pattern_type, detail=detail, evidence_count=evidence_count)


def _insight(theme="Career anxiety", detail="Recurring worry about job security"):
    return Insight(theme=theme, detail=detail, evidence_session_ids=["s1", "s2"])


def test_empty_inputs_produce_empty_string():
    assert build_retrieved_context([], []) == ""


def test_patterns_only_renders_pattern_section_and_omits_insight_section():
    text = build_retrieved_context([_pattern()], [])
    assert "Known behavioral patterns" in text
    assert "decision_reversal" in text
    assert "Often reopens closed decisions" in text
    assert "evidence_count=3" in text
    assert "Recurring cross-session themes" not in text


def test_insights_only_renders_insight_section_and_omits_pattern_section():
    text = build_retrieved_context([], [_insight()])
    assert "Recurring cross-session themes" in text
    assert "Career anxiety" in text
    assert "Recurring worry about job security" in text
    assert "Known behavioral patterns" not in text


def test_both_patterns_and_insights_render_both_sections():
    text = build_retrieved_context([_pattern()], [_insight()])
    assert "Known behavioral patterns" in text
    assert "Recurring cross-session themes" in text


def test_multiple_patterns_each_get_their_own_line():
    patterns = [
        _pattern(pattern_type="decision_reversal", detail="Reopens closed decisions"),
        _pattern(pattern_type="goal_abandonment", detail="Drops goals without resolution"),
    ]
    text = build_retrieved_context(patterns, [])
    assert "Reopens closed decisions" in text
    assert "Drops goals without resolution" in text


def test_need_state_general_is_omitted_even_with_no_patterns_or_insights():
    """Need State Inference (see engine/decisions.md "Need State
    Inference"): "general" conveys nothing actionable, so it must not
    produce a hollow "Retrieved Context" section on its own."""
    assert build_retrieved_context([], [], need_state="general") == ""


def test_need_state_decision_produces_a_visible_label_even_with_no_evidence():
    """A meaningful need state is worth surfacing on its own, even with
    no patterns/insights to attach it to."""
    text = build_retrieved_context([], [], need_state="decision")
    assert text != ""
    assert "decision" in text


def test_need_state_label_appears_alongside_patterns_and_insights():
    text = build_retrieved_context([_pattern()], [_insight()], need_state="accountability")
    assert "accountability" in text
    assert "Known behavioral patterns" in text
    assert "Recurring cross-session themes" in text


def test_need_state_none_is_equivalent_to_general():
    assert build_retrieved_context([], []) == build_retrieved_context([], [], need_state=None)
    assert build_retrieved_context([], []) == build_retrieved_context([], [], need_state="general")


def test_need_state_label_is_label_only_never_filters_patterns_or_insights():
    """Label-only design (see engine/decisions.md "Need State
    Inference"): a need state that doesn't match a pattern's own
    pattern_type/theme text must NOT hide it -- Retrieval stays
    unfiltered regardless of the inferred need."""
    patterns = [_pattern(pattern_type="unrelated_pattern_type")]
    insights = [_insight(theme="Unrelated theme")]
    text = build_retrieved_context(patterns, insights, need_state="decision")
    assert "unrelated_pattern_type" in text
    assert "Unrelated theme" in text


def test_default_pom_produces_no_additional_content():
    """Personal Operating Model (see engine/decisions.md "Personal
    Operating Model"): a fresh PersonalOperatingModel() with everything
    at its default ("unclear"/empty) must not add any lines -- same
    "omit rather than show a hollow signal" discipline as need_state."""
    assert build_retrieved_context([], [], pom=PersonalOperatingModel()) == ""


def test_pom_with_beliefs_and_relationships_renders_both_sections():
    pom = PersonalOperatingModel(
        belief={"beliefs": ["The market is competitive."]},
        relationship={"relationships": ["Manager -- role is manager."]},
    )
    text = build_retrieved_context([], [], pom=pom)
    assert "Beliefs" in text
    assert "The market is competitive." in text
    assert "Relationships" in text
    assert "Manager -- role is manager." in text


def test_pom_identity_only_renders_when_self_concept_is_set():
    pom = PersonalOperatingModel(identity=IdentitySystem(self_concept="Values independence at work."))
    text = build_retrieved_context([], [], pom=pom)
    assert "Identity" in text
    assert "Values independence at work." in text


def test_pom_motivation_only_renders_when_at_least_one_dimension_is_not_unclear():
    pom = PersonalOperatingModel(motivation=MotivationSystem(autonomy="high"))
    text = build_retrieved_context([], [], pom=pom)
    assert "Motivation" in text
    assert "autonomy=high" in text


def test_pom_stress_only_renders_when_not_unclear():
    pom = PersonalOperatingModel(stress=StressSystem(level="high"))
    text = build_retrieved_context([], [], pom=pom)
    assert "Stress level: high" in text


def test_pom_narrative_only_renders_when_arc_is_not_unclear():
    pom = PersonalOperatingModel(narrative=NarrativeSystem(arc="redemptive", summary="Grew from a hard year."))
    text = build_retrieved_context([], [], pom=pom)
    assert "Narrative arc: redemptive" in text
    assert "Grew from a hard year." in text


def test_pom_theory_of_mind_renders_each_entry():
    pom = PersonalOperatingModel(theory_of_mind=TheoryOfMindSystem(entries=[
        TheoryOfMindEntry(entity_name="Manager", inferred_perspective="Wants the transfer approved quickly."),
    ]))
    text = build_retrieved_context([], [], pom=pom)
    assert "Theory of mind" in text
    assert "Manager: Wants the transfer approved quickly." in text


def test_pom_renders_alongside_patterns_insights_and_need_state():
    pom = PersonalOperatingModel(identity=IdentitySystem(self_concept="Values independence."))
    text = build_retrieved_context([_pattern()], [_insight()], need_state="decision", pom=pom)
    assert "Known behavioral patterns" in text
    assert "Recurring cross-session themes" in text
    assert "This turn's inferred need: decision" in text
    assert "Identity" in text
