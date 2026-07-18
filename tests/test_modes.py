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

# Synthesis (see engine/decisions.md "Synthesis"): "adaptive" is a real,
# selectable mode (in MODE_COPY, and it has its own PLANNER_MODE_FOCUS
# entry) but deliberately has NO entry of its own in RESPONSE_MODE_FOCUS
# -- Response is always given whichever CONCRETE lens Planner actually
# chose that turn (see src/orchestrator/engine.py::run_turn's
# effective_mode resolution), never the literal string "adaptive".
_ALL_MODE_IDS = _ALL_MODES + ["adaptive"]


def test_five_modes_are_defined_consistently():
    assert set(MODE_COPY.keys()) == set(_ALL_MODE_IDS)
    assert set(PLANNER_MODE_FOCUS.keys()) == set(_ALL_MODE_IDS)
    assert set(RESPONSE_MODE_FOCUS.keys()) == set(_ALL_MODES)


def test_mode_copy_has_a_label_and_description_for_every_mode():
    for mode in _ALL_MODE_IDS:
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
    for mode in _ALL_MODE_IDS:
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


def test_commit_focus_notes_reference_stagnation_pattern_not_just_deadlines():
    """Regression guard for round two ("what about the other two") --
    Commit must do more than ask for a deadline; it should name a
    resurfacing pattern when stagnation_notes actually shows one, same
    accountability-coach character in both Planner and Response."""
    assert "stagnation_notes" in PLANNER_MODE_FOCUS["commit"]
    assert "stagnation_notes" in RESPONSE_MODE_FOCUS["commit"]


def test_realign_focus_notes_anchor_in_a_specific_worldstate_value():
    """Regression guard for round two -- Realign must connect to a
    SPECIFIC already-present goal/value, not a generic "what matters to
    you" question with nothing concrete to anchor it."""
    assert "specific" in PLANNER_MODE_FOCUS["realign"].lower()
    assert "specific" in RESPONSE_MODE_FOCUS["realign"].lower()


def test_vent_response_focus_warns_against_verbatim_repetition():
    """Regression guard for a live-dispatch finding: the model was
    quoting Vent's illustrative check-in-question example verbatim every
    turn instead of treating it as a register example."""
    assert "not literal text to reuse" in RESPONSE_MODE_FOCUS["vent"]


def test_realign_response_focus_flags_overused_phrases_and_gives_concrete_alternatives():
    """Regression guard for TWO live-dispatch rounds on Realign: round
    one found the model quoting the illustrative "vision for your
    career"/"long-term career aspirations" phrasing verbatim; round two
    (after telling it to just "vary" wording) found it converged on
    ANOTHER narrow synonym family instead of real variety, since Response
    has no memory of its own prior turns' phrasing and abstract "vary it"
    instructions don't survive that memorylessness. The note must name
    the overused phrases explicitly AND give concrete alternative
    question templates to sample from, not just an abstract instruction
    to vary wording."""
    assert "long-term career aspirations" in RESPONSE_MODE_FOCUS["realign"]


def test_realign_response_focus_uses_turn_count_for_deterministic_rotation():
    """Regression guard for a THIRD live-dispatch round on Realign: given
    a free-choice list of 5 templates, the model still converged --
    verbatim reuse of whichever 2-3 templates it favored (3x "year from
    now", 2x "cost you" back-to-back), while 2 of 5 templates were never
    sampled at all, and off-template turns re-derived the exact banned
    "vision"/"trajectory" language unprompted. Fixed by keying rotation to
    WorldState.turn_count (visible, deterministic, no memory required)
    instead of leaving the choice free, and banning the whole
    "vision"/"trajectory"/"envision"/"aspiration" word family rather than
    just the two specific retired phrases."""
    assert "turn_count % 5" in RESPONSE_MODE_FOCUS["realign"]
    assert "trajectory" in RESPONSE_MODE_FOCUS["realign"]
    assert "envision" in RESPONSE_MODE_FOCUS["realign"]
    assert "vision for your career" in RESPONSE_MODE_FOCUS["realign"]
    assert "no memory" in RESPONSE_MODE_FOCUS["realign"].lower()
    # At least a few concrete alternative question templates present.
    assert RESPONSE_MODE_FOCUS["realign"].count("'") >= 8


def test_commit_focus_notes_use_stagnation_notes_current_wording_not_a_fixed_phrase():
    """Regression guard for a live-dispatch finding: the model froze on
    a literal "third time" example from turn 3 onward instead of
    reflecting stagnation_notes' actual growing count each turn."""
    assert "stale" in PLANNER_MODE_FOCUS["commit"] or "stale" in RESPONSE_MODE_FOCUS["commit"]


def test_strategize_response_focus_warns_against_duplicating_options_in_prose():
    """Regression guard for a live-dispatch finding: options populated
    correctly, but sentence 2 also re-described each option in prose --
    pure duplication now explicitly disallowed."""
    assert "duplicat" in RESPONSE_MODE_FOCUS["strategize"].lower()


def test_vent_response_focus_seeds_stress_evidence_on_a_turn_count_cadence():
    """POM early seeding via mode design (2026-07-18, see
    engine/decisions.md) -- Vent maps to POM's Stress system. Must use
    the same deterministic turn_count % 3 gate as every other mode's own
    clause, not a vague "occasionally" instruction (same lesson Realign's
    own turn_count % 5 rotation already established: free "vary it"
    instructions don't survive a memoryless generator)."""
    assert "turn_count % 3 == 0" in RESPONSE_MODE_FOCUS["vent"]
    assert "POM early seeding" in RESPONSE_MODE_FOCUS["vent"]


def test_strategize_response_focus_seeds_motivation_evidence_on_a_turn_count_cadence():
    """POM early seeding via mode design -- Strategize maps to POM's
    Motivation (SDT) system, asking WHY an option appeals rather than
    just which one."""
    assert "turn_count % 3 == 0" in RESPONSE_MODE_FOCUS["strategize"]
    assert "feels right to you" in RESPONSE_MODE_FOCUS["strategize"]


def test_commit_response_focus_seeds_motivation_competence_evidence_on_a_turn_count_cadence():
    """POM early seeding via mode design -- Commit maps to POM's
    Motivation system's competence dimension, asking what's making
    follow-through hard rather than only the dated commitment itself."""
    assert "turn_count % 3 == 0" in RESPONSE_MODE_FOCUS["commit"]
    assert "set up to pull this off" in RESPONSE_MODE_FOCUS["commit"]


def test_explore_response_focus_seeds_learning_style_evidence_on_a_turn_count_cadence():
    """POM early seeding via mode design -- Explore maps to POM's
    Learning Style system, asking HOW they'd verify an assumption rather
    than only challenging it."""
    assert "turn_count % 3 == 0" in RESPONSE_MODE_FOCUS["explore"]
    assert "how would you actually find out" in RESPONSE_MODE_FOCUS["explore"].lower()


def test_realign_response_focus_has_no_competing_turn_count_seeding_gate():
    """POM early seeding via mode design -- Realign is deliberately left
    without a NEW turn_count % 3 clause: its existing turn_count % 5
    rotation already asks an Identity/Narrative-flavored question every
    turn by design (not occasionally), so a second, competing modulo gate
    in the same prompt would be redundant at best and contradictory at
    worst."""
    assert "turn_count % 3 == 0" not in RESPONSE_MODE_FOCUS["realign"]
    assert "turn_count % 5" in RESPONSE_MODE_FOCUS["realign"]


def test_response_focus_note_returns_empty_string_for_adaptive():
    """Synthesis (see engine/decisions.md "Synthesis"): Adaptive
    deliberately has no RESPONSE_MODE_FOCUS entry of its own -- Response
    is always given whichever concrete lens Planner chose that turn
    instead (see src/orchestrator/engine.py's effective_mode
    resolution), never the literal string "adaptive"."""
    assert response_mode_focus_note("adaptive") == ""


def test_planner_focus_note_for_adaptive_mentions_every_concrete_lens():
    """Adaptive's own Planner focus note must actually offer all five
    concrete lenses to choose between, not just some of them."""
    note = PLANNER_MODE_FOCUS["adaptive"]
    for mode in _ALL_MODES:
        assert mode in note


def test_planner_focus_note_for_adaptive_is_built_from_each_lens_own_text():
    """Regression guard: Adaptive's guidance must be built FROM the five
    lenses' own established PLANNER_MODE_FOCUS text (so editing a lens's
    entry automatically updates what Adaptive offers), not a separate,
    driftable summary written from scratch."""
    note = PLANNER_MODE_FOCUS["adaptive"]
    for mode in _ALL_MODES:
        assert PLANNER_MODE_FOCUS[mode] in note


def test_planner_focus_note_for_adaptive_instructs_setting_active_lens():
    assert "active_lens" in PLANNER_MODE_FOCUS["adaptive"]


def test_planner_focus_note_for_adaptive_frames_choice_as_per_turn_not_whole_journey():
    """Regression guard for the key design difference from the other
    five modes: Adaptive's choice must be allowed to change turn to
    turn, not lock in for the whole Journey the way the other five do."""
    assert "per-turn" in PLANNER_MODE_FOCUS["adaptive"].lower() or "per turn" in PLANNER_MODE_FOCUS["adaptive"].lower()
