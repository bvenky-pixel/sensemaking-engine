"""
Tests for src/orchestrator/modes.py -- Counseling modes (see
engine/decisions.md). Pure functions/data, no LLM calls -- same category
as the other schema-level tests.
"""

from __future__ import annotations

from src.insight.schema import Insight
from src.orchestrator.modes import (
    MODE_COPY,
    PLANNER_MODE_FOCUS,
    RESPONSE_MODE_FOCUS,
    _insight_callback_note,
    _pom_dimension_is_thin,
    _POM_SEED_CLAUSES,
    _realign_concept_for_turn,
    _should_seed_pom,
    planner_mode_focus_note,
    response_mode_focus_note,
)
from src.pom.schema import (
    LearningStyleSystem,
    MotivationSystem,
    PersonalOperatingModel,
    StressSystem,
)

_INSIGHT = Insight(theme="Avoiding hard conversations", detail="Tends to delay direct feedback with managers.")

_POM_SEEDED_MODES = ["vent", "strategize", "commit", "explore"]

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
    """Realign is a special case (2026-07-18, see engine/decisions.md
    "Realign rotation precomputed in Python"): its raw RESPONSE_MODE_FOCUS
    entry contains a literal `{concept}` format placeholder, filled in by
    response_mode_focus_note itself rather than matching the raw dict
    entry verbatim. Vent/Strategize/Commit/Explore (2026-07-18, see
    "POM early seeding: thinnest-system-aware targeting") only match
    the raw dict entry exactly on a turn_count that doesn't qualify for
    the POM-seeding cadence (turn_count % 3 != 0) -- passing 1 here
    guarantees that regardless of pom state, since _should_seed_pom
    short-circuits on the cadence check first."""
    for mode in _ALL_MODES:
        note = response_mode_focus_note(mode, turn_count=1)
        if mode == "realign":
            assert "{concept}" not in note
            assert note != RESPONSE_MODE_FOCUS[mode]
        else:
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


def test_realign_response_focus_bans_the_overused_word_family():
    """Regression guard for a THIRD live-dispatch round on Realign: given
    a free-choice list of 5 templates, the model still converged --
    verbatim reuse of whichever 2-3 templates it favored (3x "year from
    now", 2x "cost you" back-to-back), while 2 of 5 templates were never
    sampled at all, and off-template turns re-derived the exact banned
    "vision"/"trajectory" language unprompted. The whole
    "vision"/"trajectory"/"envision"/"aspiration" word family is banned,
    not just the two specific retired phrases -- this survived the
    round-four rewrite below unchanged."""
    assert "trajectory" in RESPONSE_MODE_FOCUS["realign"]
    assert "envision" in RESPONSE_MODE_FOCUS["realign"]
    assert "vision for your career" in RESPONSE_MODE_FOCUS["realign"]
    assert "no memory" in RESPONSE_MODE_FOCUS["realign"].lower()


def test_realign_concept_for_turn_rotates_through_five_distinct_concepts():
    """Regression guard for a FOURTH live-dispatch round on Realign
    (2026-07-18, see engine/decisions.md "Realign rotation precomputed
    in Python"): asking the MODEL to compute turn_count % 5 itself and
    pick a concept still converged onto ONE concept (index 1, the
    retrospective framing) in 4 of 6 observed turns once a different
    model became Planner's primary -- the arithmetic/selection step
    itself wasn't reliably followed. Fixed by computing the index in
    Python: `_realign_concept_for_turn` must return 5 genuinely distinct
    strings across turn_count 0-4, and repeat identically every 5 turns
    thereafter (deterministic, not up to the model at all anymore)."""
    concepts = [_realign_concept_for_turn(i) for i in range(5)]
    assert len(set(concepts)) == 5
    for i in range(5):
        assert _realign_concept_for_turn(i) == _realign_concept_for_turn(i + 5)
        assert _realign_concept_for_turn(i) == _realign_concept_for_turn(i + 10)


def test_response_mode_focus_note_embeds_the_resolved_realign_concept():
    """Direct regression test that response_mode_focus_note actually
    fills in Realign's `{concept}` placeholder with the concept
    Python resolved for that specific turn_count, rather than leaving
    the model to compute or choose anything -- the model is only ever
    handed one already-resolved concept per turn now."""
    for turn_count in range(7):
        note = response_mode_focus_note("realign", turn_count)
        assert "{concept}" not in note
        assert _realign_concept_for_turn(turn_count) in note


def test_response_mode_focus_note_ignores_turn_count_when_pom_is_not_thin():
    """turn_count only matters to Vent/Strategize/Commit/Explore's own
    POM-seeding clause (2026-07-18, see engine/decisions.md "POM early
    seeding: thinnest-system-aware targeting") THROUGH whether the
    mapped dimension is still thin -- once an account's own POM already
    has a confident, evidenced reading for every mapped dimension, the
    note must be byte-identical regardless of what turn_count is passed,
    same as before per-account POM targeting existed."""
    rich_pom = PersonalOperatingModel(
        stress=StressSystem(level="moderate", evidence=["feeling stretched thin lately"]),
        motivation=MotivationSystem(
            autonomy="high", autonomy_evidence=["chose the project alone"],
            competence="high", competence_evidence=["delivered it solo"],
            relatedness="moderate", relatedness_evidence=["checks in with the team"],
        ),
        learning_style=LearningStyleSystem(
            style="learns by doing", evidence=["tried it before reading the docs"]
        ),
    )
    for mode in _POM_SEEDED_MODES:
        notes = {response_mode_focus_note(mode, tc, rich_pom) for tc in range(6)}
        assert len(notes) == 1
        assert notes.pop() == RESPONSE_MODE_FOCUS[mode]


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


def test_vent_response_focus_seeds_stress_evidence_only_while_thin():
    """POM early seeding, thinnest-system-aware (2026-07-18, see
    engine/decisions.md "POM early seeding: thinnest-system-aware
    targeting") -- Vent maps to POM's Stress system. Deep probe fires on
    turn_count % 3 == 0 ONLY while this account's own Stress reading is
    still thin (None counts as thin); once evidenced, it stops firing
    even on a qualifying turn."""
    assert "feels right to you" not in _POM_SEED_CLAUSES["vent"]
    assert "Has this been building" in _POM_SEED_CLAUSES["vent"]
    assert _should_seed_pom("vent", 3, None) is True
    thin_pom = PersonalOperatingModel(stress=StressSystem(level="unclear", evidence=[]))
    assert _should_seed_pom("vent", 3, thin_pom) is True
    evidenced_pom = PersonalOperatingModel(
        stress=StressSystem(level="moderate", evidence=["feeling stretched thin lately"])
    )
    assert _should_seed_pom("vent", 3, evidenced_pom) is False
    # Cadence still applies even while thin -- not every single turn.
    assert _should_seed_pom("vent", 4, None) is False
    note = response_mode_focus_note("vent", 3, None)
    assert _POM_SEED_CLAUSES["vent"] in note


def test_strategize_response_focus_seeds_motivation_evidence_only_while_thin():
    """POM early seeding, thinnest-system-aware -- Strategize maps to
    POM's Motivation (SDT) system, asking WHY an option appeals rather
    than just which one. Thin if EITHER autonomy or competence still
    lacks a confident, evidenced reading."""
    assert "feels right to you" in _POM_SEED_CLAUSES["strategize"]
    assert _should_seed_pom("strategize", 3, None) is True
    half_evidenced = PersonalOperatingModel(
        motivation=MotivationSystem(
            autonomy="high", autonomy_evidence=["chose it alone"],
            competence="unclear", competence_evidence=[],
        )
    )
    assert _should_seed_pom("strategize", 3, half_evidenced) is True
    fully_evidenced = PersonalOperatingModel(
        motivation=MotivationSystem(
            autonomy="high", autonomy_evidence=["chose it alone"],
            competence="high", competence_evidence=["delivered it solo"],
        )
    )
    assert _should_seed_pom("strategize", 3, fully_evidenced) is False


def test_commit_response_focus_seeds_motivation_competence_evidence_only_while_thin():
    """POM early seeding, thinnest-system-aware -- Commit maps
    specifically to Motivation's competence dimension (not autonomy, the
    way Strategize does), asking what's making follow-through hard
    rather than only the dated commitment itself."""
    assert "set up to pull this off" in _POM_SEED_CLAUSES["commit"]
    assert _should_seed_pom("commit", 3, None) is True
    # Autonomy evidenced but competence still thin -- Commit only cares
    # about competence, so this must still count as thin for Commit.
    autonomy_only = PersonalOperatingModel(
        motivation=MotivationSystem(autonomy="high", autonomy_evidence=["chose it alone"])
    )
    assert _should_seed_pom("commit", 3, autonomy_only) is True
    competence_evidenced = PersonalOperatingModel(
        motivation=MotivationSystem(competence="high", competence_evidence=["delivered it solo"])
    )
    assert _should_seed_pom("commit", 3, competence_evidenced) is False


def test_explore_response_focus_seeds_learning_style_evidence_only_while_thin():
    """POM early seeding, thinnest-system-aware -- Explore maps to POM's
    Learning Style system, asking HOW they'd verify an assumption rather
    than only challenging it."""
    assert "how would you actually find out" in _POM_SEED_CLAUSES["explore"].lower()
    assert _should_seed_pom("explore", 3, None) is True
    evidenced = PersonalOperatingModel(
        learning_style=LearningStyleSystem(
            style="learns by doing", evidence=["tried it before reading the docs"]
        )
    )
    assert _should_seed_pom("explore", 3, evidenced) is False


def test_realign_has_no_pom_seed_clause():
    """Realign is deliberately excluded from _POM_SEED_CLAUSES -- its
    existing turn_count % 5 rotation already asks an Identity/Narrative
    question every turn by design, so it needs no separate seeding
    mechanism (see engine/decisions.md "POM early seeding via mode
    design")."""
    assert "realign" not in _POM_SEED_CLAUSES
    assert _should_seed_pom("realign", 3, None) is False


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


# --- Insight-triggered conversational callback (2026-07-19, backlog #210) ---

def test_insight_callback_note_empty_when_no_insight():
    assert _insight_callback_note(1, None) == ""


def test_insight_callback_note_empty_past_the_first_turn():
    """Only ever fires on turn_count == 1 (the first turn of a brand-new
    Journey) -- a real Insight present on any later turn must not
    resurface the callback."""
    assert _insight_callback_note(2, _INSIGHT) == ""
    assert _insight_callback_note(0, _INSIGHT) == ""


def test_insight_callback_note_fires_on_turn_one_with_a_real_insight():
    note = _insight_callback_note(1, _INSIGHT)
    assert _INSIGHT.theme in note
    assert _INSIGHT.detail in note


def test_response_mode_focus_note_appends_insight_callback_for_every_concrete_mode():
    """Mode-agnostic (2026-07-19, backlog #210) -- unlike POM-seeding,
    the callback must append for EVERY mode, including realign, which
    POM-seeding deliberately skips."""
    for mode in _ALL_MODES:
        note = response_mode_focus_note(mode, 1, None, _INSIGHT)
        assert _INSIGHT.theme in note
        assert _INSIGHT.detail in note
        # The mode's own baseline focus is still present underneath it.
        assert RESPONSE_MODE_FOCUS[mode].split("{concept}")[0] in note or mode == "realign"


def test_response_mode_focus_note_realign_still_resolves_concept_alongside_callback():
    """Realign's own {concept} placeholder must still be filled in even
    when the Insight callback also appends this turn."""
    note = response_mode_focus_note("realign", 1, None, _INSIGHT)
    assert "{concept}" not in note
    assert _realign_concept_for_turn(1) in note
    assert _INSIGHT.theme in note


def test_response_mode_focus_note_omits_insight_callback_when_no_insight_selected():
    for mode in _ALL_MODES:
        note = response_mode_focus_note(mode, 1, None, None)
        assert "Insight-triggered" not in note


def test_response_mode_focus_note_omits_insight_callback_past_turn_one():
    note = response_mode_focus_note("vent", 4, None, _INSIGHT)
    assert "Insight-triggered" not in note


def test_pom_seeding_and_insight_callback_gates_never_actually_overlap():
    """The two guaranteed-injection mechanisms are structurally
    independent gates (POM-seeding needs turn_count % 3 == 0; the
    Insight callback needs turn_count == 1) that can never both be true
    for the same turn_count (1 % 3 != 0) -- so on turn 3, only
    POM-seeding's clause appears even with a real Insight available..."""
    note = response_mode_focus_note("vent", 3, None, _INSIGHT)
    assert _POM_SEED_CLAUSES["vent"] in note
    assert "Insight-triggered" not in note
    # ...and on turn 1, only the Insight callback appears, never a
    # POM-seeding clause (which needs turn_count % 3 == 0).
    note = response_mode_focus_note("vent", 1, None, _INSIGHT)
    assert _POM_SEED_CLAUSES["vent"] not in note
    assert _INSIGHT.theme in note
