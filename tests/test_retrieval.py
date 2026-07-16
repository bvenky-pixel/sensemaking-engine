"""
Tests for src/retrieval/engine.py -- Retrieval v1 (see engine/decisions.md
"Retrieval"). Pure formatting function, no mocking needed, same style as
tests/test_learning.py.
"""

from __future__ import annotations

from src.insight.schema import Insight
from src.learning.engine import Pattern
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
