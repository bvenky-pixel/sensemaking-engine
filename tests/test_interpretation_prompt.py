"""
Tests for src/interpretation/prompt.py -- specifically the INFERENCES
section's own example (2026-07-18, see engine/decisions.md "Interpretation
prompt: fix the ambiguous inference confidence example"). Pure function
of strings, no mocking needed.
"""

from __future__ import annotations

from src.interpretation.prompt import build_messages


def test_inferences_good_example_never_embeds_confidence_in_the_reading_text():
    """Direct regression test for a real live-dispatch failure: the
    prompt's own GOOD example used to read
    `"Conversation reflects a stalled internal negotiation (confidence=0.5)"`
    -- confidence written as parenthetical text INSIDE the quoted reading
    string, rather than as its own separate field. Qwen3-32B (once pinned
    as Interpretation's primary model) took this literally, omitting the
    real `confidence` field entirely and writing the number into `reading`
    instead, which fails Pydantic's `Interpretation` validation outright
    (`inferences.0.confidence: Field required`). The example must never
    show a `(confidence=...)` suffix inside a bare quoted string again."""
    system_prompt, _ = build_messages("test message")
    # The old bare-string GOOD example is gone entirely -- it only survives
    # now as part of a BAD example inside an object literal (reading: "...").
    assert 'GOOD: "Conversation reflects a stalled internal negotiation (confidence=0.5)"' not in system_prompt


def test_inferences_good_example_shows_confidence_as_a_separate_field():
    """The corrected example must show reading/confidence as two
    distinct object fields (matching EMOTIONAL SIGNALS' own already-
    correct notation just above it), and explicitly warn against writing
    the confidence number twice."""
    system_prompt, _ = build_messages("test message")
    assert "GOOD: {reading:" in system_prompt
    assert "confidence: 0.5}" in system_prompt
    assert "TWO SEPARATE fields" in system_prompt
    assert "written twice" in system_prompt.lower()
