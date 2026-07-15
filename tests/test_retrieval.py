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
