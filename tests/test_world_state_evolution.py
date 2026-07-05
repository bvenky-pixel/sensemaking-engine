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

from src.interpretation.schema import Inference, Interpretation
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
        assumptions=[],
        inferences=[],
        unknowns=[],
        biases=[],
        entities=[],
        clarity_score=0.5,
        requires_clarification=False,
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
# Test 4: Goal lifecycle -- documents a confirmed gap (explicitly framed by
# the request as "depending on your current merge logic")
# ---------------------------------------------------------------------------
def test_goal_lifecycle_never_advances_known_gap():
    """
    Turn 1: "I want to build Confidant." Turn 2: "I launched the MVP."

    ACTUAL, CONFIRMED BEHAVIOR: there is no signal path from a new
    fact/claim to an existing Goal's status. The goal stays "active"
    forever; "launched the MVP" becomes an independent Fact/Claim with no
    link back to the Goal. Matches the KNOWN LIMITATION already documented
    in src/state/world_state.py's module docstring -- this test confirms it
    against a concrete example rather than leaving it as prose.
    """
    state = WorldState()
    state = update_state(state, make_interp(goals=["Build Confidant"]))
    state = update_state(state, make_interp(observed_facts=["User launched the MVP."]))

    assert len(state.goals) == 1
    assert state.goals[0].content == "Build Confidant"
    assert state.goals[0].status == "active", (
        "confirms the gap: goal status never advances even when a plausibly "
        "relevant fact arrives"
    )
    assert "User launched the MVP." in [f.content for f in state.facts]


# ---------------------------------------------------------------------------
# Test 5: Entity enrichment -- validates dedup, documents a confirmed gap
# for attribute enrichment
# ---------------------------------------------------------------------------
def test_entity_dedup_works_but_attribute_enrichment_has_no_data_source():
    """
    Turn 1: "My manager is Rahul." Turn 2: "Rahul now heads Product."

    PART THAT WORKS (validates intended behavior): _merge_entities dedups
    by name (case-insensitive) -- "Rahul" mentioned in both turns yields
    exactly one Entity, not two.

    PART THAT DOESN'T (confirmed gap): Interpretation.entities is a flat
    list of name strings only -- there is no structured data ("Rahul's new
    role is Head of Product") flowing into Entity.attributes anywhere in
    the pipeline. "Rahul now heads Product" lands only as a separate
    Fact/Claim string; the Entity object's attributes stay empty regardless.
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
        "confirms the gap: entity attribute enrichment has no data source yet -- "
        f"got {matching[0].attributes}"
    )
    assert "Rahul now heads Product." in [f.content for f in state.facts]


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
