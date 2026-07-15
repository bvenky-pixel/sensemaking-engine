"""
Tests for src/orchestrator/modes.py -- Counseling modes (see
engine/decisions.md). Pure functions/data, no LLM calls -- same category
as the other schema-level tests.
"""

from __future__ import annotations

from src.orchestrator.modes import (
    MODE_COPY,
    PLANNER_MODE_FOCUS,
    RESPONSE_MODE_FOCUS,
    planner_mode_focus_note,
    response_mode_focus_note,
)

_ALL_MODES = ["vent", "strategize", "commit", "explore", "realign"]


def test_five_modes_are_defined_consistently():
    assert set(MODE_COPY.keys()) == set(_ALL_MODES)
    assert set(PLANNER_MODE_FOCUS.keys()) == set(_ALL_MODES)
    assert set(RESPONSE_MODE_FOCUS.keys()) == set(_ALL_MODES)


def test_mode_copy_has_a_label_and_description_for_every_mode():
    for mode in _ALL_MODES:
        assert MODE_COPY[mode]["label"]
        assert MODE_COPY[mode]["description"]


def test_planner_and_response_focus_notes_return_empty_string_for_none():
    """A Journey with no mode (every Journey created before this feature
    existed, or one where the person skipped picking one) must produce
    no prompt injection at all -- Planner/Response behave exactly as
    they did before this feature."""
    assert planner_mode_focus_note(None) == ""
    assert response_mode_focus_note(None) == ""


def test_planner_and_response_focus_notes_return_empty_string_for_unrecognized_mode():
    assert planner_mode_focus_note("not-a-real-mode") == ""
    assert response_mode_focus_note("not-a-real-mode") == ""


def test_planner_focus_note_returns_the_focus_text_for_each_known_mode():
    for mode in _ALL_MODES:
        note = planner_mode_focus_note(mode)
        assert note == PLANNER_MODE_FOCUS[mode]
        assert MODE_COPY[mode]["label"] in note


def test_response_focus_note_returns_the_focus_text_for_each_known_mode():
    for mode in _ALL_MODES:
        note = response_mode_focus_note(mode)
        assert note == RESPONSE_MODE_FOCUS[mode]
        assert MODE_COPY[mode]["label"] in note


def test_planner_and_response_focus_notes_are_worded_differently_per_mode():
    """Regression guard for the "distinct character per mode" round --
    Planner's and Response's focus notes for the same mode must not be
    identical strings; each layer's job (deciding what vs. phrasing it)
    genuinely diverges."""
    for mode in _ALL_MODES:
        assert planner_mode_focus_note(mode) != response_mode_focus_note(mode)


def test_strategize_response_focus_explicitly_mentions_options():
    """Regression guard for the explicit "rattle out choices" request --
    Strategize is the one mode that should actively lean into populating
    Response's `options` field, not just discuss tradeoffs abstractly."""
    assert "`options`" in RESPONSE_MODE_FOCUS["strategize"]


def test_explore_response_focus_frames_a_challenge_not_a_neutral_question():
    """Regression guard for the explicit "push back and challenge"
    request -- Explore's Response focus must instruct an actual
    challenge, not just an open-ended question."""
    assert "challenge" in RESPONSE_MODE_FOCUS["explore"].lower()
