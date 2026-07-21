"""
Tests for src/understanding/tier2_engine.py (see engine/decisions.md
"Tier 2 design" and the module's own docstring). call_provider is
mocked at src.understanding.tier2_engine's own import path, same
pattern as tests/test_insight.py -- no real LLM calls.

Three groups: candidate-pool selection and signature computation (pure,
no LLM), should_recompute_tier2's gating logic (pure), and
run_tier2_synthesis/update_tier2's LLM-call behavior (mocked).
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from src.state.world_state import (
    Decision,
    Fact,
    Goal,
    Provenance,
    Unknown,
    WorldState,
)
from src.understanding.schema import Tier2Batch
from src.understanding.tier2_engine import (
    MIN_GROUNDING_ITEMS,
    TIER2_RECENCY_WINDOW_TURNS,
    TIER2_STALENESS_TURNS,
    Tier2EngineError,
    compute_tier2_grounding_signature,
    run_tier2_synthesis,
    select_tier2_candidates,
    should_recompute_tier2,
    update_tier2,
)


def _always_returns(payload):
    def _call(provider_name, system_prompt, messages, schema, temperature, component="unknown", tracker=None):
        return json.dumps(payload)
    return _call


# ---------------------------------------------------------------------------
# select_tier2_candidates
# ---------------------------------------------------------------------------

def test_open_goal_stays_a_candidate_regardless_of_recency():
    state = WorldState(turn_count=100)
    state.goals.append(Goal(
        content="Move to the Product team.", status="active",
        provenance=Provenance(source="interpretation", first_seen=1, last_updated=1),
    ))
    candidates = select_tier2_candidates(state)
    assert len(candidates) == 1
    assert candidates[0].kind == "goal"


def test_completed_goal_is_excluded_even_if_recent():
    """Thread kinds use a STRICTER non-terminal filter than Tier 1's own
    visibility filter -- Tier 1 still shows a completed Goal (complete
    record); Tier 2's pool does not (that thread is closed)."""
    state = WorldState(turn_count=2)
    state.goals.append(Goal(
        content="Move to the Product team.", status="completed",
        provenance=Provenance(source="interpretation", first_seen=1, last_updated=2),
    ))
    assert select_tier2_candidates(state) == []


def test_open_decision_and_open_unknown_also_stay_candidates_regardless_of_recency():
    state = WorldState(turn_count=50)
    state.decisions.append(Decision(
        content="House", status="open",
        provenance=Provenance(source="interpretation", first_seen=1, last_updated=1),
    ))
    state.unknowns.append(Unknown(
        content="Has the user discussed this with their manager?", status="open",
        provenance=Provenance(source="interpretation", first_seen=1, last_updated=1),
    ))
    kinds = {c.kind for c in select_tier2_candidates(state)}
    assert kinds == {"decision", "uncertainty"}


def test_resolved_decision_is_excluded():
    state = WorldState(turn_count=2)
    state.decisions.append(Decision(
        content="House", status="resolved",
        provenance=Provenance(source="interpretation", first_seen=1, last_updated=2),
    ))
    assert select_tier2_candidates(state) == []


def test_recent_fact_is_a_candidate():
    state = WorldState(turn_count=5)
    state.facts.append(Fact(
        content="User has a manager named Sarah.", status="active",
        provenance=Provenance(source="interpretation", first_seen=5, last_updated=5),
    ))
    candidates = select_tier2_candidates(state)
    assert len(candidates) == 1
    assert candidates[0].kind == "fact"


def test_stale_fact_outside_recency_window_is_excluded():
    """Detail kinds (Fact/Claim/Assumption/Inference/Entity/emotion) are
    recency-windowed -- confirmed unbounded growth per the validation
    report, unlike thread kinds."""
    state = WorldState(turn_count=1 + TIER2_RECENCY_WINDOW_TURNS + 1)
    state.facts.append(Fact(
        content="User has a manager named Sarah.", status="active",
        provenance=Provenance(source="interpretation", first_seen=1, last_updated=1),
    ))
    assert select_tier2_candidates(state) == []


def test_fact_exactly_at_recency_window_boundary_is_still_included():
    state = WorldState(turn_count=1 + TIER2_RECENCY_WINDOW_TURNS)
    state.facts.append(Fact(
        content="User has a manager named Sarah.", status="active",
        provenance=Provenance(source="interpretation", first_seen=1, last_updated=1),
    ))
    assert len(select_tier2_candidates(state)) == 1


# ---------------------------------------------------------------------------
# compute_tier2_grounding_signature
# ---------------------------------------------------------------------------

def test_signature_is_deterministic_for_the_same_pool():
    state = WorldState(turn_count=1)
    state.facts.append(Fact(content="A fact.", provenance=Provenance(source="interpretation", first_seen=1, last_updated=1)))
    candidates = select_tier2_candidates(state)
    assert (
        compute_tier2_grounding_signature(candidates, state)
        == compute_tier2_grounding_signature(candidates, state)
    )


def test_signature_changes_when_a_new_thread_candidate_is_added():
    """The core Tier 2 design fix (see engine/decisions.md "Tier 2
    design" Q1, narrowed 2026-07-19 by backlog #295): a NEW thread-kind
    item (goal/decision/uncertainty) arriving must change the signature,
    not just a change to an already-cited item."""
    state = WorldState(turn_count=1)
    state.goals.append(Goal(content="A goal.", status="active", provenance=Provenance(source="interpretation", first_seen=1, last_updated=1)))
    sig_before = compute_tier2_grounding_signature(select_tier2_candidates(state), state)

    state.goals.append(Goal(content="A second, new goal.", status="active", provenance=Provenance(source="interpretation", first_seen=1, last_updated=1)))
    sig_after = compute_tier2_grounding_signature(select_tier2_candidates(state), state)

    assert sig_before != sig_after


def test_signature_is_unaffected_by_a_new_detail_candidate():
    """Backlog #295 (2026-07-19, see engine/decisions.md "Understanding:
    Tier 2 recompute gated to thread-item status changes only"): a live
    walkthrough found the ORIGINAL full-pool signature fired on nearly
    every turn because ordinary fact/claim/entity accumulation changed
    the hash just as much as a real thread transition -- detail kinds
    are now excluded from the signature entirely, so a new fact must
    NOT change it, even though it's still a real, included candidate
    (see select_tier2_candidates, unaffected by this narrowing)."""
    state = WorldState(turn_count=1)
    state.facts.append(Fact(content="A fact.", provenance=Provenance(source="interpretation", first_seen=1, last_updated=1)))
    sig_before = compute_tier2_grounding_signature(select_tier2_candidates(state), state)

    state.facts.append(Fact(content="A second, new fact.", provenance=Provenance(source="interpretation", first_seen=1, last_updated=1)))
    candidates_after = select_tier2_candidates(state)
    sig_after = compute_tier2_grounding_signature(candidates_after, state)

    assert sig_before == sig_after
    # The new fact is still a real candidate Tier 2 would see once a
    # recompute is triggered by something else -- it's just not what
    # triggers the recompute itself.
    assert len(candidates_after) == 2


def test_signature_changes_when_a_pooled_items_status_changes_with_text_unchanged():
    """A Decision moving open -> deferred keeps the same rendered text
    but must still invalidate the signature -- status is hashed
    explicitly, not inferred from text."""
    state = WorldState(turn_count=1)
    state.decisions.append(Decision(content="House", status="open", provenance=Provenance(source="interpretation", first_seen=1, last_updated=1)))
    sig_open = compute_tier2_grounding_signature(select_tier2_candidates(state), state)

    state.decisions[0].status = "deferred"
    sig_deferred = compute_tier2_grounding_signature(select_tier2_candidates(state), state)

    assert sig_open != sig_deferred


# ---------------------------------------------------------------------------
# should_recompute_tier2
# ---------------------------------------------------------------------------

def test_never_computed_before_always_recomputes():
    state = WorldState(turn_count=1)
    assert should_recompute_tier2(state, "any-signature") is True


def test_same_signature_and_recently_computed_does_not_recompute():
    state = WorldState(turn_count=3)
    state.understanding.tier2_grounding_signature = "sig-1"
    state.understanding.tier2_computed_at_turn = 2
    assert should_recompute_tier2(state, "sig-1") is False


def test_different_signature_recomputes_even_if_recently_computed():
    state = WorldState(turn_count=3)
    state.understanding.tier2_grounding_signature = "sig-1"
    state.understanding.tier2_computed_at_turn = 2
    assert should_recompute_tier2(state, "sig-2") is True


def test_staleness_backstop_recomputes_even_with_matching_signature():
    state = WorldState(turn_count=2 + TIER2_STALENESS_TURNS)
    state.understanding.tier2_grounding_signature = "sig-1"
    state.understanding.tier2_computed_at_turn = 2
    assert should_recompute_tier2(state, "sig-1") is True


# ---------------------------------------------------------------------------
# run_tier2_synthesis / update_tier2 (mocked LLM)
# ---------------------------------------------------------------------------

def test_tier2_batch_defaults_to_empty_list():
    assert Tier2Batch().statements == []


def test_below_grounding_floor_short_circuits_without_calling_the_provider(monkeypatch):
    def _fail_if_called(*args, **kwargs):
        raise AssertionError("call_provider should never be reached below the grounding floor")

    monkeypatch.setattr("src.understanding.tier2_engine.call_provider", _fail_if_called)

    state = WorldState(turn_count=1)
    state.facts.append(Fact(content="Only one candidate.", provenance=Provenance(source="interpretation", first_seen=1, last_updated=1)))
    candidates = select_tier2_candidates(state)
    assert len(candidates) < MIN_GROUNDING_ITEMS
    assert run_tier2_synthesis(candidates) == []


def test_grounding_filters_hallucinated_ids(monkeypatch):
    state = WorldState(turn_count=1)
    state.facts.append(Fact(content="You have a manager named Sarah.", provenance=Provenance(source="interpretation", first_seen=1, last_updated=1)))
    state.goals.append(Goal(content="Move to the Product team.", provenance=Provenance(source="interpretation", first_seen=1, last_updated=1)))
    candidates = select_tier2_candidates(state)
    real_ids = [c.id for c in candidates]

    payload = {
        "statements": [
            {
                "text": "Synthesized statement.",
                "grounding_item_ids": real_ids + ["hallucinated-id"],
            }
        ]
    }
    monkeypatch.setattr("src.understanding.tier2_engine.call_provider", _always_returns(payload))

    result = run_tier2_synthesis(candidates)
    assert len(result) == 1
    assert result[0].tier == 2
    assert result[0].kind == "synthesis"
    assert set(result[0].grounding_item_ids) == set(real_ids)


def test_statement_dropped_when_surviving_grounding_falls_below_floor(monkeypatch):
    state = WorldState(turn_count=1)
    state.facts.append(Fact(content="Fact one.", provenance=Provenance(source="interpretation", first_seen=1, last_updated=1)))
    state.goals.append(Goal(content="Goal one.", provenance=Provenance(source="interpretation", first_seen=1, last_updated=1)))
    candidates = select_tier2_candidates(state)

    payload = {
        "statements": [
            {"text": "Weakly grounded.", "grounding_item_ids": [candidates[0].id, "hallucinated-1", "hallucinated-2"]},
        ]
    }
    monkeypatch.setattr("src.understanding.tier2_engine.call_provider", _always_returns(payload))

    assert run_tier2_synthesis(candidates) == []


def test_empty_statements_is_a_valid_correct_response(monkeypatch):
    state = WorldState(turn_count=1)
    state.facts.append(Fact(content="Fact one.", provenance=Provenance(source="interpretation", first_seen=1, last_updated=1)))
    state.goals.append(Goal(content="Goal one.", provenance=Provenance(source="interpretation", first_seen=1, last_updated=1)))
    candidates = select_tier2_candidates(state)

    monkeypatch.setattr("src.understanding.tier2_engine.call_provider", _always_returns({"statements": []}))
    assert run_tier2_synthesis(candidates) == []


def test_raises_when_every_provider_fails(monkeypatch):
    def _always_invalid_json(*args, **kwargs):
        return "not valid json"

    monkeypatch.setattr("src.understanding.tier2_engine.call_provider", _always_invalid_json)

    state = WorldState(turn_count=1)
    state.facts.append(Fact(content="Fact one.", provenance=Provenance(source="interpretation", first_seen=1, last_updated=1)))
    state.goals.append(Goal(content="Goal one.", provenance=Provenance(source="interpretation", first_seen=1, last_updated=1)))
    candidates = select_tier2_candidates(state)

    with pytest.raises(Tier2EngineError):
        run_tier2_synthesis(candidates)


def test_update_tier2_skips_the_llm_call_when_not_due(monkeypatch):
    """should_recompute_tier2 == False -- update_tier2 must not call the
    provider at all, and must return state completely unchanged."""
    def _fail_if_called(*args, **kwargs):
        raise AssertionError("call_provider should never be reached when a recompute isn't due")

    monkeypatch.setattr("src.understanding.tier2_engine.call_provider", _fail_if_called)

    state = WorldState(turn_count=3)
    state.facts.append(Fact(content="Fact one.", provenance=Provenance(source="interpretation", first_seen=1, last_updated=1)))
    state.goals.append(Goal(content="Goal one.", provenance=Provenance(source="interpretation", first_seen=1, last_updated=1)))
    candidates = select_tier2_candidates(state)
    sig = compute_tier2_grounding_signature(candidates, state)
    state.understanding.tier2_grounding_signature = sig
    state.understanding.tier2_computed_at_turn = 3

    result_state = update_tier2(state)
    assert result_state.understanding.tier2 == []
    assert result_state.understanding.tier2_computed_at_turn == 3


def test_update_tier2_recomputes_and_persists_signature_and_turn(monkeypatch):
    state = WorldState(turn_count=1)
    state.facts.append(Fact(content="You have a manager named Sarah.", provenance=Provenance(source="interpretation", first_seen=1, last_updated=1)))
    state.goals.append(Goal(content="Move to the Product team.", provenance=Provenance(source="interpretation", first_seen=1, last_updated=1)))
    candidates = select_tier2_candidates(state)
    real_ids = [c.id for c in candidates]

    payload = {"statements": [{"text": "Synthesized.", "grounding_item_ids": real_ids}]}
    monkeypatch.setattr("src.understanding.tier2_engine.call_provider", _always_returns(payload))

    result_state = update_tier2(state)
    assert len(result_state.understanding.tier2) == 1
    assert result_state.understanding.tier2_computed_at_turn == 1
    assert result_state.understanding.tier2_grounding_signature is not None


def test_update_tier2_is_non_blocking_on_provider_failure(monkeypatch):
    """A Tier 2 failure must never propagate -- state comes back
    unchanged, same as if a recompute simply wasn't due this turn."""
    def _always_invalid_json(*args, **kwargs):
        return "not valid json"

    monkeypatch.setattr("src.understanding.tier2_engine.call_provider", _always_invalid_json)

    state = WorldState(turn_count=1)
    state.facts.append(Fact(content="Fact one.", provenance=Provenance(source="interpretation", first_seen=1, last_updated=1)))
    state.goals.append(Goal(content="Goal one.", provenance=Provenance(source="interpretation", first_seen=1, last_updated=1)))

    result_state = update_tier2(state)
    assert result_state.understanding.tier2 == []
    assert result_state.understanding.tier2_computed_at_turn is None
