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
    EntityAttributeUpdate,
    GoalUpdate,
    Inference,
    Interpretation,
)
from src.state.builder import update_state
from src.state.world_state import WorldState


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

    ACTUAL, CONFIRMED BEHAVIOR: _merge_content_items in src/state/builder.py
    only dedups by exact string match. Two textually-different facts are
    both appended as `active` -- nothing ever sets FactStatus.superseded, an
    enum value that exists in src/state/world_state.py but is unused by any
    code path today. This test documents that gap concretely rather than
    asserting the originally-hoped-for (currently unimplemented) behavior.
    Proposed fix discussed separately, not implemented here without
    confirmation.
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
