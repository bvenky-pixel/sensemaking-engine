"""
Tests for src/orchestrator/modes.py -- Counseling modes (see
engine/decisions.md). Pure functions/data, no LLM calls -- same category
as the other schema-level tests.
"""

from __future__ import annotations

from src.orchestrator.modes import MODE_COPY, MODE_FOCUS, mode_focus_note

_ALL_MODES = ["vent", "strategize", "commit", "explore", "realign"]


def test_five_modes_are_defined_consistently():
    assert set(MODE_COPY.keys()) == set(_ALL_MODES)
    assert set(MODE_FOCUS.keys()) == set(_ALL_MODES)


def test_mode_copy_has_a_label_and_description_for_every_mode():
    for mode in _ALL_MODES:
        assert MODE_COPY[mode]["label"]
        assert MODE_COPY[mode]["description"]


def test_mode_focus_note_returns_empty_string_for_none():
    """A Journey with no mode (every Journey created before this feature
    existed, or one where the person skipped picking one) must produce
    no prompt injection at all -- Planner/Response behave exactly as
    they did before this feature."""
    assert mode_focus_note(None) == ""


def test_mode_focus_note_returns_empty_string_for_unrecognized_mode():
    assert mode_focus_note("not-a-real-mode") == ""


def test_mode_focus_note_returns_the_focus_text_for_each_known_mode():
    for mode in _ALL_MODES:
        note = mode_focus_note(mode)
        assert note == MODE_FOCUS[mode]
        assert mode in note.lower() or MODE_COPY[mode]["label"] in note
