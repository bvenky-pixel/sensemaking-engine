"""
State evolution tests for WorldState v1 (src/state/world_state.py) and the
State Builder (src/state/builder.py), isolated from Interpretation's own
reliability by feeding hand-built Interpretation objects directly into
update_state() across multiple turns.

Purpose (explicit, per the request that produced this file): validate this
layer NOW, before Judgment starts depending on WorldState, so a future
failure can be isolated to a single layer instead of Interpretation / State
Builder / WorldState / Judgment all being entangled.

Each test's docstring says plainly whether it validates working behavior or
documents a known, already-logged deferred gap (see engine/decisions.md).
Tests assert REAL, verified behavior -- none of these were adjusted to force
a pass; where a gap was found, the test documents the gap instead.
"""

from __future__ import annotations

from src.interpretation.schema import (
    DecisionEvent,
    EmotionalSignal,
    EntityAttributeUpdate,
    GoalUpdate,
    Inference,
    Interpretation,
)
from src.judgment.schema import DecisionResolution, Judgment, KnowledgeCorrection
from src.state.builder import apply_judgment_resolutions, apply_knowledge_corrections, update_state
from src.state.world_state import WorldState
from src.understanding.engine import build_tier1_statements


def make_interp(**overrides) -> Interpretation:
    """Minimal-defaults Interpretation builder so each test only sets the
    fields that matter for its scenario."""
    defaults = dict(
        urgency="low",
        impact_domains=[],
        emotional_signals=[],
        surface_complaint="",
        core_question="",
        core_question_confidence=0.0,
        observed_facts=[],
        claims=[],
        goals=[],
        decision_options=[],
        has_assumption=False,
        assumption_check="No framing-embedded assumption detected.",
        assumptions=[],
        inferences=[],
        unknowns=[],
        biases=[],
        entities=[],
        clarity_score=0.5,
        requires_clarification=False,
        has_decision_event=False,
        decision_event_option="",
        decision_event_type="",
    )
    defaults.update(overrides)
    return Interpretation(**defaults)


# ---------------------------------------------------------------------------
# Test 1: Accumulation -- validates working behavior
# ---------------------------------------------------------------------------
def test_accumulation_across_tiers_and_exact_repeat_dedup():
    """
    Turn 1: goal stated. Turn 2: unrelated fact + unknown. Turn 3: the SAME
    goal restated verbatim. Expect: all three tiers accumulate independently
    (goal survives to turn 3, fact/unknown from turn 2 are still present),
    and the exact-repeat in turn 3 does NOT create a duplicate goal.

    This validates the mechanism that's actually implemented: exact
    (case-insensitive) content dedup. It does NOT validate paraphrase-level
    dedup (a goal restated with different wording WOULD create a second
    entry) -- that's a separate, not-yet-implemented capability, kept
    intentionally out of this test so it doesn't imply something the code
    doesn't do.
    """
    state = WorldState()

    state = update_state(state, make_interp(goals=["Move to Product team"]))
    assert [g.content for g in state.goals] == ["Move to Product team"]
    assert state.goals[0].status == "active"

    state = update_state(
        state,
        make_interp(
            observed_facts=["Boss keeps delaying the conversation."],
            unknowns=["Why is the boss delaying?"],
        ),
    )
    assert [g.content for g in state.goals] == ["Move to Product team"]  # goal untouched
    assert [f.content for f in state.facts] == ["Boss keeps delaying the conversation."]
    assert [u.content for u in state.unknowns] == ["Why is the boss delaying?"]

    # Exact verbatim repeat -- must not duplicate
    state = update_state(state, make_interp(goals=["Move to Product team"]))
    assert len(state.goals) == 1, f"expected no duplicate, got {state.goals}"


# ---------------------------------------------------------------------------
# Test 2: Contradiction -- documents a confirmed gap
# ---------------------------------------------------------------------------
def test_contradiction_is_not_detected_known_gap():
    """
    Turn 1: "Boss denied the transfer." Turn 2: "Boss approved the transfer."

    ORIGINALLY HOPED FOR: the first fact gets marked `superseded`, the
    second is `active`, history is preserved.

    ACTUAL, CONFIRMED BEHAVIOR (for update_state alone -- see below):
    _merge_content_items in src/state/builder.py only dedups by exact
    string match. Two textually-different facts are both appended as
    `active` -- nothing in update_state ever sets FactStatus.superseded.
    This test documents that gap concretely for update_state, and its
    assertions remain true and unchanged after 2026-07-12's Fact/Claim
    correction round: the gap is now closable one layer up. See
    apply_knowledge_corrections in src/state/builder.py and
    Judgment.knowledge_corrections in src/judgment/schema.py
    (engine/decisions.md "Fact/Claim correction and near-duplicate
    consolidation") -- that mechanism is called separately, from
    run_turn after run_judgment, never from inside update_state itself,
    so update_state's own behavior in isolation is exactly as documented
    here. See test_apply_knowledge_corrections_retracts_matching_fact
    below for the now-available fix, exercised end to end.
    """
    state = WorldState()
    state = update_state(state, make_interp(observed_facts=["Boss denied the transfer."]))
    state = update_state(state, make_interp(observed_facts=["Boss approved the transfer."]))

    assert len(state.facts) == 2, (
        "confirms the gap: contradiction detection is not implemented -- "
        f"got {[ (f.content, f.status) for f in state.facts ]}"
    )
    assert all(f.status == "active" for f in state.facts), (
        "confirms the gap: nothing ever sets status='superseded'"
    )


# ---------------------------------------------------------------------------
# Test 3: Unknown resolution -- now word-overlap based (was exact substring;
# see engine/decisions.md 2026-07-05 fix entry). Validates the improvement,
# and documents that deep semantic gaps remain out of scope for this layer.
# ---------------------------------------------------------------------------
def test_unknown_resolution_fires_on_high_word_overlap():
    """
    Validates the word-overlap mechanism directly: high shared vocabulary
    between an existing unknown and a new fact resolves the unknown and
    promotes its content into Facts.
    """
    state = WorldState()
    state = update_state(state, make_interp(unknowns=["why hr rejected me"]))
    assert [u.content for u in state.unknowns] == ["why hr rejected me"]

    state = update_state(
        state, make_interp(observed_facts=["HR gave a reason: why hr rejected me was a frozen headcount."])
    )

    assert state.unknowns == [], f"expected the unknown to resolve, got {state.unknowns}"
    assert "why hr rejected me" in [f.content for f in state.facts], (
        f"expected the resolved unknown promoted into facts, got {[f.content for f in state.facts]}"
    )


def test_unknown_resolution_word_overlap_catches_reordered_phrasing():
    """
    Demonstrates the actual improvement over the old exact-substring check:
    "Why is HR rejecting applications" is NOT a literal substring of "HR is
    rejecting applications due to budget cuts." (word order differs -- "why
    is hr rejecting" vs "hr is rejecting"), so the OLD mechanism would have
    left this unknown open. The word-overlap check (4 of the unknown's 5
    words -- is/hr/rejecting/applications -- appear in the fact, 0.8 overlap)
    correctly resolves it.
    """
    state = WorldState()
    state = update_state(state, make_interp(unknowns=["Why is HR rejecting applications"]))
    state = update_state(
        state, make_interp(observed_facts=["HR is rejecting applications due to budget cuts."])
    )

    assert state.unknowns == [], f"expected the unknown to resolve, got {state.unknowns}"
    assert "Why is HR rejecting applications" in [f.content for f in state.facts]


def test_unknown_resolution_still_misses_deep_semantic_gap_by_design():
    """
    ORIGINALLY HOPED FOR (per the request that produced this test): "I
    don't know why HR rejected me" -> "HR said the role was frozen" should
    resolve the unknown.

    ACTUAL, CONFIRMED BEHAVIOR, even under the improved word-overlap check:
    the unknown's content words (reason/rejected/application) and the fact's
    content words (role/frozen) share almost nothing but stopwords ("hr",
    "the") -- overlap is well under threshold in both directions, so the
    unknown stays open. This is intentional, not a leftover bug: per
    engine/decisions.md "Confirmed gap 2," resolving a genuine semantic gap
    (a question and its answer sharing no real vocabulary) needs a real
    signal from a richer Interpretation schema or from Judgment -- the State
    Builder is explicitly not meant to compensate for that with string
    heuristics.
    """
    state = WorldState()
    state = update_state(state, make_interp(unknowns=["Why HR rejected the application."]))
    state = update_state(state, make_interp(observed_facts=["HR said the role was frozen."]))

    assert len(state.unknowns) == 1, (
        "expected this deep semantic gap to remain open by design -- "
        f"got {[u.content for u in state.unknowns]}"
    )
    assert state.unknowns[0].content == "Why HR rejected the application."
    assert "HR said the role was frozen." in [f.content for f in state.facts]


# ---------------------------------------------------------------------------
# Test 4: Goal/Decision lifecycle -- v1.1 (see engine/decisions.md and
# engine/specs/interpretation-spec-v1.1.md): this gap is now closed WHEN
# Interpretation emits the typed signal. A co-occurring fact with no typed
# signal still does NOT move status -- that's the correct, unchanged
# behavior (the State Builder never guesses; it only acts on an explicit
# goal_update/decision_event), not a leftover of the old gap.
# ---------------------------------------------------------------------------
def test_goal_status_unchanged_without_an_explicit_goal_update():
    """
    Turn 1: "I want to build Confidant." Turn 2: a plain fact is stated
    ("User launched the MVP.") with NO goal_updates signal.

    CORRECT BEHAVIOR (still, deliberately): the goal stays "active." A
    co-occurring fact alone is not evidence of a lifecycle transition --
    only an explicit GoalUpdate is. This is the "no heuristic
    compensation for a missing signal" principle holding even after the
    signal exists: the builder still never infers a transition from mere
    proximity of a fact to a goal.
    """
    state = WorldState()
    state = update_state(state, make_interp(goals=["Build Confidant"]))
    state = update_state(state, make_interp(observed_facts=["User launched the MVP."]))

    assert len(state.goals) == 1
    assert state.goals[0].content == "Build Confidant"
    assert state.goals[0].status == "active", (
        "a bare co-occurring fact must not move goal status -- only an "
        "explicit GoalUpdate should"
    )
    assert "User launched the MVP." in [f.content for f in state.facts]


def test_goal_status_advances_with_an_explicit_goal_update():
    """
    Turn 1: "I want to build Confidant." Turn 2: Interpretation emits a
    GoalUpdate (the typed v1.1 signal) paraphrasing the same goal with
    status="completed".

    CONFIRMS THE FIX: the matching existing Goal's status now actually
    transitions, closing the gap test_goal_status_unchanged_without_an_
    explicit_goal_update above documents as still-correctly-absent
    without the signal.
    """
    state = WorldState()
    state = update_state(state, make_interp(goals=["Build Confidant"]))
    state = update_state(
        state,
        make_interp(
            goal_updates=[GoalUpdate(goal="launched the MVP for Confidant", status="completed")]
        ),
    )

    assert len(state.goals) == 1
    assert state.goals[0].content == "Build Confidant"
    assert state.goals[0].status == "completed", (
        f"expected the GoalUpdate to transition the matching goal, got {state.goals}"
    )


def test_goal_update_with_no_matching_goal_is_dropped_not_fabricated():
    """
    A GoalUpdate whose text doesn't sufficiently overlap ANY existing goal
    must not fabricate a new Goal -- goal_updates exists only for
    transitions on something already tracked (goals: List[str] is where a
    genuinely new goal belongs).
    """
    state = WorldState()
    state = update_state(state, make_interp(goals=["Move to the Product team"]))
    state = update_state(
        state,
        make_interp(goal_updates=[GoalUpdate(goal="completely unrelated topic", status="completed")]),
    )

    assert len(state.goals) == 1, f"expected no fabricated goal, got {state.goals}"
    assert state.goals[0].status == "active"


def test_decision_events_resolve_chosen_and_rejected_options():
    """
    Turn 1: two decision options stated. Turn 2: Interpretation emits
    DecisionEvents choosing one and rejecting the other.

    CONFIRMS THE FIX: both matching Decisions transition to "resolved" --
    the same "resolved means no longer live," not "resolved means
    approved" reading Decision's own docstring already uses.
    """
    state = WorldState()
    state = update_state(
        state, make_interp(decision_options=["wait for the freeze to lift", "apply externally"])
    )
    state = update_state(
        state,
        make_interp(
            decision_events=[
                DecisionEvent(option="wait for the freeze to lift", event="chosen"),
                DecisionEvent(option="apply externally", event="rejected"),
            ]
        ),
    )

    by_content = {d.content: d.status for d in state.decisions}
    assert by_content["wait for the freeze to lift"] == "resolved"
    assert by_content["apply externally"] == "resolved"


def test_decision_event_deferred_moves_status_off_open():
    """
    A "deferred" DecisionEvent (added 2026-07-10, see engine/decisions.md
    -- the 10-turn WorldState walkthrough surfaced a real "wait and see"
    case that is neither a permanent resolution nor a true no-op) must
    move the matching Decision's status to "deferred", not leave it
    silently stuck at "open" the way it did before this status existed.
    """
    state = WorldState()
    state = update_state(state, make_interp(decision_options=["apply externally"]))
    state = update_state(
        state,
        make_interp(
            decision_events=[DecisionEvent(option="apply externally", event="deferred")]
        ),
    )

    assert state.decisions[0].status == "deferred"


def test_has_decision_event_auto_repairs_empty_decision_events_list():
    """
    Boolean-gate for decision_events (added 2026-07-10, see
    engine/decisions.md "decision lifecycle boolean-gate"): across two
    live samples, the model either invented a fresh option label
    (unmatchable downstream) or emitted no decision_events entry at all
    for a turn that plainly resolved an existing option -- the same
    silent-omission shape has_assumption/has_risk_signal were built to
    fix. If has_decision_event=True but decision_events is still empty,
    the auto-repair must reconstruct one from decision_event_option/
    decision_event_type (both already-structured fields, not parsed free
    text) rather than leaving the two signals contradicting each other.
    """
    interp = make_interp(
        decision_options=["applying externally"],
        has_decision_event=True,
        decision_event_option="applying externally",
        decision_event_type="deferred",
        decision_events=[],
    )

    assert interp.decision_events == [DecisionEvent(option="applying externally", event="deferred")]


def test_has_decision_event_false_leaves_decision_events_empty():
    """has_decision_event=False must never fabricate a decision_events entry."""
    interp = make_interp(has_decision_event=False, decision_event_option="", decision_event_type="")

    assert interp.decision_events == []


def make_judgment(**overrides) -> Judgment:
    """Minimal-defaults Judgment builder, same pattern as make_interp."""
    defaults = dict(
        primary_problem="",
        primary_goal="",
        current_focus="",
        key_blockers=[],
        secondary_issues=[],
        open_unknowns=[],
        active_decisions=[],
        contradictions=[],
        has_knowledge_correction=False,
        knowledge_correction_target="",
        knowledge_correction_kind="",
        knowledge_correction_corrected_content="",
        has_risk_signal=False,
        risk_scan="No risk-worthy signal identified.",
        risks=[],
        opportunities=[],
        has_decision_resolution=False,
        decision_resolution_option="",
        decision_resolution_status="",
        stagnation_notes=[],
        confidence=0.5,
        supporting_evidence=[],
    )
    defaults.update(overrides)
    return Judgment(**defaults)


def test_judgment_secondary_issues_defaults_empty_and_accepts_grounded_entries():
    """
    Salience v1 (2026-07-10, see engine/decisions.md "Judgment salience --
    first reasoning-depth v2 increment"): secondary_issues has no
    boolean-gate/auto-repair (unlike has_risk_signal/has_decision_resolution
    above) -- there's no evidence yet of the detects-but-fails-to-transcribe
    failure mode that justified those gates for a brand-new field. This is
    a plain schema round-trip check: empty by default, and a populated list
    survives construction untouched.
    """
    empty = make_judgment()
    assert empty.secondary_issues == []

    populated = make_judgment(
        primary_problem="Founder's resistance is blocking the move to Product.",
        secondary_issues=["Strained relationship with their current manager."],
    )
    assert populated.secondary_issues == ["Strained relationship with their current manager."]


def test_judgment_stagnation_notes_defaults_empty_and_accepts_grounded_entries():
    """
    Trajectory/stagnation v1 (2026-07-11, see engine/decisions.md
    "Judgment trajectory/stagnation assessment"): same shape as
    secondary_issues above -- no boolean-gate, plain schema round-trip.
    The actual turn-gap computation is tested separately in
    tests/test_judgment_stagnation.py (compute_stagnation_signals); this
    only confirms the field itself round-trips correctly.
    """
    empty = make_judgment()
    assert empty.stagnation_notes == []

    populated = make_judgment(
        stagnation_notes=["The goal of moving to the Product team has had no movement in 4 turns."]
    )
    assert populated.stagnation_notes == [
        "The goal of moving to the Product team has had no movement in 4 turns."
    ]


def test_apply_judgment_resolutions_moves_decision_off_open():
    """
    Decision lifecycle, round 3 (2026-07-10, see engine/decisions.md):
    Interpretation's decision_events kept failing for a structural
    reason -- it's a stateless, single-message function that never sees
    WorldState, so it can only guess at a prior turn's exact
    decision_option text. Judgment reads the full WorldState verbatim
    every turn, so it can quote the real option directly instead of
    inventing a label. `apply_judgment_resolutions` is the one exception
    to "Judgment never writes to WorldState" -- confirms the mechanism
    moves a real Decision's status off "open" using Judgment's own
    exact-quote output, not Interpretation's decision_events at all.
    """
    state = WorldState()
    state = update_state(state, make_interp(decision_options=["applying externally"]))

    judgment = make_judgment(
        has_decision_resolution=True,
        decision_resolution_option="applying externally",
        decision_resolution_status="deferred",
        decision_resolutions=[DecisionResolution(option="applying externally", status="deferred")],
    )
    new_state = apply_judgment_resolutions(state, judgment)

    assert new_state.decisions[0].status == "deferred"
    # never mutates the caller's state
    assert state.decisions[0].status == "open"


def test_has_decision_resolution_auto_repairs_empty_decision_resolutions_list():
    """
    Same boolean-gate auto-repair pattern as has_assumption/
    has_risk_signal/has_decision_event, at the Judgment layer this time.
    Unlike decision_events, this one is expected to actually hold live:
    Judgment already has the exact WorldState.decisions text in front of
    it, so this is a transcription-compliance gap, not a retrieval one.
    """
    judgment = make_judgment(
        has_decision_resolution=True,
        decision_resolution_option="applying externally",
        decision_resolution_status="deferred",
        decision_resolutions=[],
    )

    assert judgment.decision_resolutions == [
        DecisionResolution(option="applying externally", status="deferred")
    ]


def test_has_decision_resolution_false_leaves_decision_resolutions_empty():
    """has_decision_resolution=False must never fabricate a resolution."""
    judgment = make_judgment(
        has_decision_resolution=False, decision_resolution_option="", decision_resolution_status=""
    )

    assert judgment.decision_resolutions == []


def test_apply_judgment_resolutions_no_match_leaves_decisions_unchanged():
    """
    A resolution whose option doesn't sufficiently overlap ANY existing
    Decision must not fabricate or corrupt a Decision -- same "no match
    -> dropped, never used to fabricate" discipline as
    _apply_goal_updates/_apply_decision_events.
    """
    state = WorldState()
    state = update_state(state, make_interp(decision_options=["applying externally"]))

    judgment = make_judgment(
        has_decision_resolution=True,
        decision_resolution_option="completely unrelated topic",
        decision_resolution_status="deferred",
        decision_resolutions=[DecisionResolution(option="completely unrelated topic", status="deferred")],
    )
    new_state = apply_judgment_resolutions(state, judgment)

    assert new_state.decisions[0].status == "open"


# ---------------------------------------------------------------------------
# Fact/Claim correction and near-duplicate consolidation (2026-07-12, see
# engine/decisions.md "Fact/Claim correction and near-duplicate
# consolidation"). apply_knowledge_corrections closes the gap
# test_contradiction_is_not_detected_known_gap documents above, one layer
# up from update_state -- see that test's docstring for why its own
# assertions still hold unchanged.
# ---------------------------------------------------------------------------
def test_has_knowledge_correction_auto_repairs_for_retracted():
    """Same boolean-gate auto-repair pattern as has_decision_resolution --
    "retracted" needs no corrected_content to repair."""
    judgment = make_judgment(
        has_knowledge_correction=True,
        knowledge_correction_target="Boss denied the transfer.",
        knowledge_correction_kind="retracted",
        knowledge_correction_corrected_content="",
    )
    assert judgment.knowledge_corrections == [
        KnowledgeCorrection(target="Boss denied the transfer.", kind="retracted", corrected_content="")
    ]


def test_has_knowledge_correction_auto_repairs_for_superseded_with_content():
    judgment = make_judgment(
        has_knowledge_correction=True,
        knowledge_correction_target="User wants to move into the Product team.",
        knowledge_correction_kind="superseded",
        knowledge_correction_corrected_content="User wants to move to the Product team.",
    )
    assert judgment.knowledge_corrections == [
        KnowledgeCorrection(
            target="User wants to move into the Product team.",
            kind="superseded",
            corrected_content="User wants to move to the Product team.",
        )
    ]


def test_has_knowledge_correction_does_not_repair_superseded_with_blank_corrected_content():
    """A "superseded" correction with no replacement text can't be
    mechanically repaired -- the repair intentionally does NOT fabricate
    corrected_content, same discipline as every _apply_* function in
    src/state/builder.py never fabricating content."""
    judgment = make_judgment(
        has_knowledge_correction=True,
        knowledge_correction_target="Boss denied the transfer.",
        knowledge_correction_kind="superseded",
        knowledge_correction_corrected_content="",
    )
    assert judgment.knowledge_corrections == []


def test_has_knowledge_correction_false_leaves_knowledge_corrections_empty():
    judgment = make_judgment(
        has_knowledge_correction=False,
        knowledge_correction_target="",
        knowledge_correction_kind="",
        knowledge_correction_corrected_content="",
    )
    assert judgment.knowledge_corrections == []


def test_apply_knowledge_corrections_retracts_matching_fact():
    """The Boss denied/approved fixture, now actually correctable: the
    stale fact is retracted, the untargeted sibling is untouched, nothing
    new is fabricated."""
    state = WorldState()
    state = update_state(state, make_interp(
        observed_facts=["Boss denied the transfer.", "Boss approved the transfer."]
    ))
    judgment = make_judgment(
        has_knowledge_correction=True,
        knowledge_correction_target="Boss denied the transfer.",
        knowledge_correction_kind="retracted",
        knowledge_corrections=[KnowledgeCorrection(target="Boss denied the transfer.", kind="retracted")],
    )
    new_state = apply_knowledge_corrections(state, judgment)

    denied = next(f for f in new_state.facts if f.content == "Boss denied the transfer.")
    approved = next(f for f in new_state.facts if f.content == "Boss approved the transfer.")
    assert denied.status == "retracted"
    assert approved.status == "active"
    assert len(new_state.facts) == 2  # nothing fabricated


def test_apply_knowledge_corrections_supersedes_and_creates_one_consolidated_fact():
    """Two near-duplicate facts, both corrections pointing at the SAME
    corrected_content -> both superseded, exactly ONE new active fact
    created, not two -- the within-call anti-duplication guard."""
    state = WorldState()
    state = update_state(state, make_interp(observed_facts=[
        "User wants to move to the Product team.",
        "User wants to move into the Product team.",
    ]))
    judgment = make_judgment(
        has_knowledge_correction=True,
        knowledge_correction_target="User wants to move to the Product team.",
        knowledge_correction_kind="superseded",
        knowledge_correction_corrected_content="User wants to transfer to the Product team.",
        knowledge_corrections=[
            KnowledgeCorrection(
                target="User wants to move to the Product team.", kind="superseded",
                corrected_content="User wants to transfer to the Product team.",
            ),
            KnowledgeCorrection(
                target="User wants to move into the Product team.", kind="superseded",
                corrected_content="User wants to transfer to the Product team.",
            ),
        ],
    )
    new_state = apply_knowledge_corrections(state, judgment)

    active = [f for f in new_state.facts if f.status == "active"]
    superseded = [f for f in new_state.facts if f.status == "superseded"]
    assert len(new_state.facts) == 3  # 2 superseded originals + exactly 1 new consolidated fact
    assert len(superseded) == 2
    assert len(active) == 1
    assert active[0].content == "User wants to transfer to the Product team."


def test_apply_knowledge_corrections_no_duplicate_when_corrected_content_matches_an_existing_active_fact():
    """Superseding a near-duplicate into text that's already an active
    Fact must not create a redundant third item -- the pre-existing
    active fact IS the consolidated result."""
    state = WorldState()
    state = update_state(state, make_interp(observed_facts=[
        "User wants to move to the Product team.",
        "User wants to move into the Product team.",
    ]))
    judgment = make_judgment(
        has_knowledge_correction=True,
        knowledge_correction_target="User wants to move into the Product team.",
        knowledge_correction_kind="superseded",
        knowledge_correction_corrected_content="User wants to move to the Product team.",
        knowledge_corrections=[KnowledgeCorrection(
            target="User wants to move into the Product team.", kind="superseded",
            corrected_content="User wants to move to the Product team.",
        )],
    )
    new_state = apply_knowledge_corrections(state, judgment)

    assert len(new_state.facts) == 2  # no third fact created
    active = [f for f in new_state.facts if f.status == "active"]
    assert len(active) == 1
    assert active[0].content == "User wants to move to the Product team."


def test_apply_knowledge_corrections_no_match_leaves_facts_unchanged():
    """A target with no sufficient overlap with anything -> dropped
    silently, same "no match -> dropped, never fabricated" discipline as
    _apply_goal_updates/_apply_decision_events/apply_judgment_resolutions."""
    state = WorldState()
    state = update_state(state, make_interp(observed_facts=["Completely unrelated fact."]))
    judgment = make_judgment(
        has_knowledge_correction=True,
        knowledge_correction_target="Something not present at all.",
        knowledge_correction_kind="retracted",
        knowledge_corrections=[KnowledgeCorrection(target="Something not present at all.", kind="retracted")],
    )
    new_state = apply_knowledge_corrections(state, judgment)

    assert new_state.facts[0].status == "active"
    assert len(new_state.facts) == 1


def test_apply_knowledge_corrections_does_not_rematch_already_corrected_item():
    """Chain-prevention guard: Judgment is stateless-per-turn and sees the
    FULL WorldState (including already-superseded items) every turn, so
    it could plausibly re-flag the same now-inactive text on a later
    turn. Re-applying the SAME correction must be a no-op the second
    time -- the already-superseded target is never rematched, so no
    second duplicate "consolidated" fact is fabricated."""
    state = WorldState()
    state = update_state(state, make_interp(
        observed_facts=["User wants to move into the Product team."]
    ))
    judgment = make_judgment(
        has_knowledge_correction=True,
        knowledge_correction_target="User wants to move into the Product team.",
        knowledge_correction_kind="superseded",
        knowledge_correction_corrected_content="User wants to move to the Product team.",
        knowledge_corrections=[KnowledgeCorrection(
            target="User wants to move into the Product team.", kind="superseded",
            corrected_content="User wants to move to the Product team.",
        )],
    )
    once = apply_knowledge_corrections(state, judgment)
    assert len(once.facts) == 2  # original superseded + one new active

    twice = apply_knowledge_corrections(once, judgment)
    assert len(twice.facts) == 2  # unchanged -- target is no longer active, never rematched


def test_apply_knowledge_corrections_claim_target_stays_a_claim():
    """A "superseded" correction targeting a Claim appends to
    state.claims, not state.facts -- type preservation."""
    state = WorldState()
    state = update_state(state, make_interp(claims=["User believes their boss is upset."]))
    judgment = make_judgment(
        has_knowledge_correction=True,
        knowledge_correction_target="User believes their boss is upset.",
        knowledge_correction_kind="superseded",
        knowledge_correction_corrected_content="User no longer believes their boss is upset.",
        knowledge_corrections=[KnowledgeCorrection(
            target="User believes their boss is upset.", kind="superseded",
            corrected_content="User no longer believes their boss is upset.",
        )],
    )
    new_state = apply_knowledge_corrections(state, judgment)

    assert len(new_state.claims) == 2
    assert len(new_state.facts) == 0
    active_claim = next(c for c in new_state.claims if c.status == "active")
    assert active_claim.content == "User no longer believes their boss is upset."


def test_apply_knowledge_corrections_deep_copy_does_not_mutate_caller():
    state = WorldState()
    state = update_state(state, make_interp(observed_facts=["Boss denied the transfer."]))
    judgment = make_judgment(
        has_knowledge_correction=True,
        knowledge_correction_target="Boss denied the transfer.",
        knowledge_correction_kind="retracted",
        knowledge_corrections=[KnowledgeCorrection(target="Boss denied the transfer.", kind="retracted")],
    )
    new_state = apply_knowledge_corrections(state, judgment)

    assert new_state.facts[0].status == "retracted"
    assert state.facts[0].status == "active"  # caller's original object untouched


def test_apply_knowledge_corrections_bumps_last_updated_not_first_seen():
    state = WorldState()
    state = update_state(state, make_interp(observed_facts=["Boss denied the transfer."]))  # turn 1
    state = update_state(state, make_interp())  # turn 2, no new content
    judgment = make_judgment(
        has_knowledge_correction=True,
        knowledge_correction_target="Boss denied the transfer.",
        knowledge_correction_kind="retracted",
        knowledge_corrections=[KnowledgeCorrection(target="Boss denied the transfer.", kind="retracted")],
    )
    new_state = apply_knowledge_corrections(state, judgment)

    assert new_state.facts[0].provenance.first_seen == 1
    assert new_state.facts[0].provenance.last_updated == 2
    assert new_state.turn_count == 2  # apply_knowledge_corrections never increments it


def test_apply_knowledge_corrections_new_item_gets_fresh_provenance_source_judgment_and_tier_confidence():
    state = WorldState()
    state = update_state(state, make_interp(
        observed_facts=["User wants to move into the Product team."]
    ))  # turn 1
    judgment = make_judgment(
        has_knowledge_correction=True,
        knowledge_correction_target="User wants to move into the Product team.",
        knowledge_correction_kind="superseded",
        knowledge_correction_corrected_content="User wants to move to the Product team.",
        knowledge_corrections=[KnowledgeCorrection(
            target="User wants to move into the Product team.", kind="superseded",
            corrected_content="User wants to move to the Product team.",
        )],
    )
    new_state = apply_knowledge_corrections(state, judgment)

    new_fact = next(f for f in new_state.facts if f.status == "active")
    assert new_fact.provenance.source == "judgment"
    assert new_fact.provenance.first_seen == new_state.turn_count == 1
    assert new_fact.provenance.last_updated == new_state.turn_count
    assert new_fact.confidence == 1.0  # FACT_TIER_CONFIDENCE


def test_apply_knowledge_corrections_superseded_with_blank_corrected_content_is_dropped_even_when_hand_built():
    """The builder's own defensive check, independent of Judgment's
    schema-level auto-repair: a KnowledgeCorrection(kind="superseded",
    corrected_content="") that arrives having bypassed the repair path
    entirely (constructed directly, as if the model emitted the list
    itself) is still dropped -- never fabricates a blank replacement."""
    state = WorldState()
    state = update_state(state, make_interp(observed_facts=["Boss denied the transfer."]))
    judgment = make_judgment(
        has_knowledge_correction=True,
        knowledge_correction_target="Boss denied the transfer.",
        knowledge_correction_kind="superseded",
        knowledge_correction_corrected_content="",
        knowledge_corrections=[KnowledgeCorrection(
            target="Boss denied the transfer.", kind="superseded", corrected_content=""
        )],
    )
    new_state = apply_knowledge_corrections(state, judgment)

    assert new_state.facts[0].status == "active"  # never touched
    assert len(new_state.facts) == 1  # nothing fabricated


def test_correction_target_exact_match_wins_over_fuzzy_similar_candidate_regardless_of_list_order():
    """The direct regression test for the antonym-collision fix: "Boss
    denied the transfer." and "Boss approved the transfer." score 0.67
    fuzzy overlap against EACH OTHER (see _find_active_correction_target
    in src/state/builder.py). Confirms the exact-quoted target is always
    the one corrected, never the fuzzy-similar neighbor, in BOTH list
    orders."""
    judgment = make_judgment(
        has_knowledge_correction=True,
        knowledge_correction_target="Boss denied the transfer.",
        knowledge_correction_kind="retracted",
        knowledge_corrections=[KnowledgeCorrection(target="Boss denied the transfer.", kind="retracted")],
    )

    state_denied_first = WorldState()
    state_denied_first = update_state(state_denied_first, make_interp(
        observed_facts=["Boss denied the transfer.", "Boss approved the transfer."]
    ))
    result_a = apply_knowledge_corrections(state_denied_first, judgment)
    denied_a = next(f for f in result_a.facts if f.content == "Boss denied the transfer.")
    approved_a = next(f for f in result_a.facts if f.content == "Boss approved the transfer.")
    assert denied_a.status == "retracted"
    assert approved_a.status == "active"

    state_approved_first = WorldState()
    state_approved_first = update_state(state_approved_first, make_interp(
        observed_facts=["Boss approved the transfer.", "Boss denied the transfer."]
    ))
    result_b = apply_knowledge_corrections(state_approved_first, judgment)
    denied_b = next(f for f in result_b.facts if f.content == "Boss denied the transfer.")
    approved_b = next(f for f in result_b.facts if f.content == "Boss approved the transfer.")
    assert denied_b.status == "retracted"
    assert approved_b.status == "active"


def test_lexically_similar_but_distinct_facts_are_never_conflated_without_an_explicit_correction():
    """Negative control: two genuinely distinct facts that happen to
    share most of their words ("User can afford a house." / "User can
    afford an MBA.", 0.75 word overlap by the same formula used above)
    must never be touched by this mechanism absent an explicit,
    Judgment-authored correction naming one of them as a target -- no
    code path in apply_knowledge_corrections can spontaneously conflate
    two distinct facts on its own."""
    state = WorldState()
    state = update_state(state, make_interp(observed_facts=[
        "User can afford a house.", "User can afford an MBA.",
    ]))
    judgment = make_judgment(has_knowledge_correction=False)
    new_state = apply_knowledge_corrections(state, judgment)

    assert new_state.facts[0].status == "active"
    assert new_state.facts[1].status == "active"
    assert len(new_state.facts) == 2


def test_tier1_excludes_retracted_and_superseded_after_a_correction():
    """End-to-end through build_tier1_statements: after a correction, the
    stale item is excluded from Tier 1 and the new active replacement is
    included -- exercises src/understanding/engine.py's
    _FACT_CLAIM_VISIBLE_STATUSES concretely (it already excludes
    "retracted"/"superseded" with zero code change needed there)."""
    state = WorldState()
    state = update_state(state, make_interp(observed_facts=["Boss denied the transfer."]))
    judgment = make_judgment(
        has_knowledge_correction=True,
        knowledge_correction_target="Boss denied the transfer.",
        knowledge_correction_kind="superseded",
        knowledge_correction_corrected_content="Boss approved the transfer.",
        knowledge_corrections=[KnowledgeCorrection(
            target="Boss denied the transfer.", kind="superseded",
            corrected_content="Boss approved the transfer.",
        )],
    )
    new_state = apply_knowledge_corrections(state, judgment)

    fact_texts = [s.text for s in build_tier1_statements(new_state) if s.kind == "fact"]
    assert "Boss denied the transfer." not in fact_texts
    assert "Boss approved the transfer." in fact_texts


# ---------------------------------------------------------------------------
# Test 5: Entity enrichment -- dedup was already correct; v1.1 (see
# engine/decisions.md and engine/specs/interpretation-spec-v1.1.md) closes
# the attribute-enrichment gap WHEN Interpretation emits the typed signal.
# A bare co-occurring fact still does NOT populate attributes -- that
# remains correct, not a leftover gap.
# ---------------------------------------------------------------------------
def test_entity_dedup_and_attributes_stay_empty_without_a_typed_update():
    """
    Turn 1: "My manager is Rahul." Turn 2: "Rahul now heads Product" stated
    only as a plain fact, with NO entity_attribute_updates signal.

    Dedup (validates intended, already-working behavior): "Rahul" mentioned
    in both turns yields exactly one Entity, not two.

    Attributes (correct, deliberate): stay empty -- a bare co-occurring
    fact is not evidence of a specific attribute; only an explicit
    EntityAttributeUpdate should populate Entity.attributes.
    """
    state = WorldState()
    state = update_state(state, make_interp(entities=["Rahul"]))
    state = update_state(
        state,
        make_interp(entities=["Rahul"], observed_facts=["Rahul now heads Product."]),
    )

    matching = [e for e in state.entities if e.name.lower() == "rahul"]
    assert len(matching) == 1, f"expected exactly one Rahul entity, got {state.entities}"
    assert matching[0].status == "active"
    assert matching[0].attributes == [], (
        "a bare co-occurring fact must not populate attributes -- only an "
        f"explicit EntityAttributeUpdate should -- got {matching[0].attributes}"
    )
    assert "Rahul now heads Product." in [f.content for f in state.facts]


def test_entity_attributes_populate_with_an_explicit_attribute_update():
    """
    Turn 1: "My manager is Rahul." Turn 2: Interpretation emits an
    EntityAttributeUpdate for Rahul's new role.

    CONFIRMS THE FIX: the matching Entity's attributes now actually get
    set, closing the gap the previous test documents as still-correctly-
    absent without the signal. Also confirms that a SECOND update to the
    SAME attribute key replaces the value (refine, don't duplicate) rather
    than appending a second entry.
    """
    state = WorldState()
    state = update_state(state, make_interp(entities=["Rahul"]))
    state = update_state(
        state,
        make_interp(
            entity_attribute_updates=[
                EntityAttributeUpdate(entity="Rahul", attribute="role", value="Head of Product")
            ]
        ),
    )

    matching = [e for e in state.entities if e.name.lower() == "rahul"]
    assert len(matching) == 1
    assert [(a.attribute, a.value) for a in matching[0].attributes] == [
        ("role", "Head of Product")
    ], f"expected the attribute update to apply, got {matching[0].attributes}"

    # A later update to the SAME attribute key refines in place, not append.
    state = update_state(
        state,
        make_interp(
            entity_attribute_updates=[
                EntityAttributeUpdate(entity="Rahul", attribute="role", value="VP of Product")
            ]
        ),
    )
    matching = [e for e in state.entities if e.name.lower() == "rahul"]
    assert [(a.attribute, a.value) for a in matching[0].attributes] == [
        ("role", "VP of Product")
    ], f"expected in-place refinement, not a duplicate entry, got {matching[0].attributes}"


def test_entity_attribute_update_creates_entity_if_not_separately_mentioned():
    """
    An EntityAttributeUpdate for a name that never separately appeared in
    `entities` should still create the Entity -- the attribute statement
    itself is evidence the entity exists, not a reason to drop it.
    """
    state = WorldState()
    state = update_state(
        state,
        make_interp(
            entity_attribute_updates=[
                EntityAttributeUpdate(entity="Priya", attribute="role", value="CTO")
            ]
        ),
    )

    matching = [e for e in state.entities if e.name.lower() == "priya"]
    assert len(matching) == 1, f"expected Priya to be created, got {state.entities}"
    assert [(a.attribute, a.value) for a in matching[0].attributes] == [("role", "CTO")]


# ---------------------------------------------------------------------------
# Bonus: confidence-formatting fix -- validates working behavior
# ---------------------------------------------------------------------------
def test_inference_embedded_confidence_annotation_is_stripped():
    """
    The 2026-07-05 WorldState walkthrough surfaced a real doubled-annotation
    case in turn 5: the model wrote its own "(confidence=0.5)" directly into
    an Inference's `reading` text, and update_state then appended its own
    canonical one on top, rendering as
    "...situation (confidence=0.5) (confidence=0.50)". Confirms the fix:
    any model-embedded confidence annotation is stripped before the
    canonical one is appended, so exactly one appears.
    """
    state = WorldState()
    state = update_state(
        state,
        make_interp(
            inferences=[
                Inference(
                    reading="User's previous concern reflects a misunderstanding of the situation (confidence=0.5)",
                    confidence=0.5,
                )
            ]
        ),
    )

    assert len(state.inferences) == 1
    inference_text = state.inferences[0]
    assert inference_text.count("(confidence=") == 1, f"expected exactly one annotation, got {inference_text!r}"
    assert inference_text == (
        "User's previous concern reflects a misunderstanding of the situation (confidence=0.50)"
    )


def test_turn_count_increments_once_per_update_state_call():
    """
    WorldState provenance, v1.1 (2026-07-10, see engine/decisions.md
    "WorldState provenance -- trajectory prerequisite"): turn_count starts
    at 0 for a brand-new session and increments by exactly 1 per
    update_state call, regardless of what the turn's Interpretation
    contains -- this is the single per-turn counter every provenance stamp
    below is stamped against.
    """
    state = WorldState()
    assert state.turn_count == 0

    state = update_state(state, make_interp())
    assert state.turn_count == 1

    state = update_state(state, make_interp())
    assert state.turn_count == 2

    state = update_state(state, make_interp())
    assert state.turn_count == 3


def test_new_fact_stamped_with_provenance_at_creation():
    """A Fact created on turn 1 gets first_seen == last_updated == 1,
    source == "interpretation" -- Facts have no in-place mutation path
    today, so first_seen and last_updated will only ever match for them
    under current merge semantics (see _merge_content_items)."""
    state = WorldState()
    state = update_state(state, make_interp(observed_facts=["Boss denied the transfer."]))

    assert len(state.facts) == 1
    provenance = state.facts[0].provenance
    assert provenance is not None
    assert provenance.source == "interpretation"
    assert provenance.first_seen == 1
    assert provenance.last_updated == 1


def test_goal_status_change_bumps_last_updated_but_not_first_seen():
    """A Goal created on turn 1, left untouched on turn 2, then
    status-changed via goal_updates on turn 3: first_seen stays 1
    (when it was actually created), last_updated moves to 3 (when its
    status actually changed) -- exactly the signal a future trajectory
    assessment needs to tell "just created" apart from "long-stagnant."
    """
    state = WorldState()
    state = update_state(state, make_interp(goals=["Move to the Product team."]))
    assert state.goals[0].provenance.first_seen == 1
    assert state.goals[0].provenance.last_updated == 1

    state = update_state(state, make_interp())  # turn 2, nothing relevant happens
    assert state.goals[0].provenance.last_updated == 1  # untouched, correctly

    state = update_state(
        state,
        make_interp(goal_updates=[GoalUpdate(goal="Move to the Product team.", status="paused")]),
    )

    assert state.turn_count == 3
    assert state.goals[0].status == "paused"
    assert state.goals[0].provenance.first_seen == 1
    assert state.goals[0].provenance.last_updated == 3


def test_decision_resolution_via_judgment_bumps_last_updated_not_first_seen():
    """Same signal as the Goal test above, but through
    apply_judgment_resolutions -- the one write-back exception to
    "Judgment never writes to WorldState" (see engine/decisions.md
    "decision lifecycle, round 3"). Confirms it stamps last_updated using
    state.turn_count rather than incrementing the counter itself -- only
    update_state ever does that."""
    state = WorldState()
    state = update_state(state, make_interp(decision_options=["applying externally"]))
    assert state.decisions[0].provenance.first_seen == 1
    assert state.decisions[0].provenance.last_updated == 1

    state = update_state(state, make_interp())  # turn 2, nothing relevant happens

    judgment = make_judgment(
        has_decision_resolution=True,
        decision_resolution_option="applying externally",
        decision_resolution_status="deferred",
        decision_resolutions=[DecisionResolution(option="applying externally", status="deferred")],
    )
    state = apply_judgment_resolutions(state, judgment)

    assert state.turn_count == 2  # apply_judgment_resolutions never increments it
    assert state.decisions[0].status == "deferred"
    assert state.decisions[0].provenance.first_seen == 1
    assert state.decisions[0].provenance.last_updated == 2


def test_entity_stamped_with_provenance_at_creation():
    """An Entity created via _merge_entities gets the same creation-time
    stamp as Facts/Claims/Goals/Decisions/Unknowns."""
    state = WorldState()
    state = update_state(state, make_interp(entities=["Sarah"]))

    assert len(state.entities) == 1
    provenance = state.entities[0].provenance
    assert provenance is not None
    assert provenance.source == "interpretation"
    assert provenance.first_seen == 1
    assert provenance.last_updated == 1


# --- Understanding layer -- Journey-scoped identity (2026-07-12, see
# engine/decisions.md) ---


def test_knowledge_item_ids_are_stable_across_repeated_update_state_calls_when_content_unchanged():
    """The exact-dedup path in _merge_content_items returns the SAME
    Goal object (not a new one) when the identical content is restated --
    its id must be the literal same string both times, not just "some
    id"."""
    state = WorldState()
    state = update_state(state, make_interp(goals=["Move to the Product team."]))
    first_id = state.goals[0].id

    state = update_state(state, make_interp(goals=["Move to the Product team."]))
    assert len(state.goals) == 1
    assert state.goals[0].id == first_id


def test_knowledge_item_ids_are_unique_across_items_in_one_turn():
    state = WorldState()
    state = update_state(state, make_interp(
        observed_facts=["Fact one.", "Fact two."], goals=["Goal one.", "Goal two."],
    ))
    ids = [f.id for f in state.facts] + [g.id for g in state.goals]
    assert len(ids) == len(set(ids))


def test_fact_goal_decision_get_highest_tier_confidence():
    state = WorldState()
    state = update_state(state, make_interp(
        observed_facts=["A fact."], goals=["A goal."], decision_options=["An option."],
    ))
    assert state.facts[0].confidence == 1.0
    assert state.goals[0].confidence == 1.0
    assert state.decisions[0].confidence == 1.0


def test_claim_gets_interpretive_tier_confidence():
    state = WorldState()
    state = update_state(state, make_interp(claims=["A claim."]))
    assert state.claims[0].confidence == 0.7


def test_assumption_item_gets_lowest_tier_confidence():
    state = WorldState()
    state = update_state(state, make_interp(assumptions=["Assumes something."]))
    assert len(state.assumption_items) == 1
    assert state.assumption_items[0].confidence == 0.3
    assert state.assumption_items[0].content == "Assumes something."


def test_inference_item_confidence_matches_real_interpretation_confidence_not_a_constant():
    """Unlike Assumption, Inference gets REAL per-item confidence from
    Interpretation's own calibrated Inference.confidence -- not a flat
    tier constant."""
    state = WorldState()
    state = update_state(state, make_interp(
        inferences=[Inference(reading="User seems anxious about this.", confidence=0.62)]
    ))
    assert len(state.inference_items) == 1
    assert state.inference_items[0].confidence == 0.62
    assert state.inference_items[0].content == "User seems anxious about this."


def test_assumptions_and_inferences_flat_lists_unchanged_by_new_parallel_fields():
    """Regression guard for src/judgment/engine.py's phase-transition
    logic, which reads len(state.assumptions) + len(state.biases) --
    the flat lists must stay byte-identical to pre-change behavior."""
    state = WorldState()
    state = update_state(state, make_interp(
        assumptions=["Assumes X."],
        inferences=[Inference(reading="Seems like Y.", confidence=0.5)],
    ))
    assert state.assumptions == ["Assumes X."]
    assert state.inferences == ["Seems like Y. (confidence=0.50)"]


def test_assumption_items_dedup_matches_flat_list_exact_match_semantics():
    """assumption_items merges with case_insensitive=False, mirroring
    _merge_unique's exact-match dedup exactly -- two near-duplicates
    differing only in case both survive, same as the flat assumptions
    list does, unlike _merge_content_items' usual case-insensitive
    default."""
    state = WorldState()
    state = update_state(state, make_interp(assumptions=["Assumes X.", "assumes x."]))
    assert len(state.assumptions) == 2
    assert len(state.assumption_items) == 2


# ---------------------------------------------------------------------------
# emotional_signal_items -- validation report Failure Mode #4 (see
# engine/decisions.md "Tier 1 completeness + has_knowledge_correction
# calibration"): Interpretation's emotional_signals had no home in
# WorldState at all before this.
# ---------------------------------------------------------------------------
def test_emotional_signal_item_created_with_real_interpretation_confidence():
    """Like Inference (and unlike Assumption), confidence is REAL
    per-item data from Interpretation's own calibrated
    EmotionalSignal.confidence, not a flat tier constant."""
    state = WorldState()
    state = update_state(state, make_interp(
        emotional_signals=[EmotionalSignal(emotion="disenchantment", intensity=0.8, confidence=0.9, source="explicit")]
    ))
    assert len(state.emotional_signal_items) == 1
    item = state.emotional_signal_items[0]
    assert item.emotion == "disenchantment"
    assert item.intensity == 0.8
    assert item.confidence == 0.9
    assert item.source == "explicit"


def test_emotional_signal_recurrence_updates_in_place_not_a_new_entry():
    """Unlike every other tier's dedup-by-content merge, a repeat of the
    SAME emotion updates intensity/confidence/source in place rather than
    being dropped as an unchanged duplicate or appended as a fresh entry
    -- see _merge_emotional_signals and EmotionalSignalItem's own
    docstrings for why: intensity is a live reading, not a reaffirmed
    fact, and accumulating a fresh entry per turn would reproduce this
    same report's Failure Mode #3 (unbounded near-duplicate
    accumulation) for emotions specifically."""
    state = WorldState()
    state = update_state(state, make_interp(
        emotional_signals=[EmotionalSignal(emotion="anxiety", intensity=0.4, confidence=0.5, source="inferred")]
    ))
    state = update_state(state, make_interp(
        emotional_signals=[EmotionalSignal(emotion="Anxiety", intensity=0.9, confidence=0.8, source="explicit")]
    ))
    assert len(state.emotional_signal_items) == 1
    item = state.emotional_signal_items[0]
    assert item.intensity == 0.9
    assert item.confidence == 0.8
    assert item.source == "explicit"


def test_emotional_signal_recurrence_preserves_first_seen_bumps_last_updated():
    state = WorldState()
    state = update_state(state, make_interp(
        emotional_signals=[EmotionalSignal(emotion="relief", intensity=0.3, confidence=0.6, source="inferred")]
    ))
    first_seen = state.emotional_signal_items[0].provenance.first_seen
    state = update_state(state, make_interp(
        emotional_signals=[EmotionalSignal(emotion="relief", intensity=0.5, confidence=0.6, source="inferred")]
    ))
    item = state.emotional_signal_items[0]
    assert item.provenance.first_seen == first_seen
    assert item.provenance.last_updated == state.turn_count


def test_distinct_emotions_accumulate_as_separate_items():
    state = WorldState()
    state = update_state(state, make_interp(
        emotional_signals=[
            EmotionalSignal(emotion="anxiety", intensity=0.4, confidence=0.5, source="inferred"),
            EmotionalSignal(emotion="hope", intensity=0.6, confidence=0.7, source="explicit"),
        ]
    ))
    assert len(state.emotional_signal_items) == 2
    emotions = {item.emotion for item in state.emotional_signal_items}
    assert emotions == {"anxiety", "hope"}
