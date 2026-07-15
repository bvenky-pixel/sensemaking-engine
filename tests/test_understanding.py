"""
Tests for src/understanding/ (Tier 1 -- see engine/decisions.md
"Understanding layer -- Journey-scoped identity"). Pure Python, no LLM
calls -- Tier 1 is a deterministic template, same discipline as
tests/test_executor.py's coverage of build_clarity_brief.
"""

from __future__ import annotations

import json

from src.judgment.engine import run_judgment
from src.judgment.schema import Judgment
from src.planner.engine import run_planner
from src.planner.schema import Planner
from src.response.engine import run_response_generator
from src.state.world_state import (
    Assumption,
    Claim,
    Decision,
    EmotionalSignalItem,
    Entity,
    EntityAttribute,
    Fact,
    Goal,
    Inference,
    Unknown,
    WorldState,
)
from src.understanding.engine import build_tier1_statements


def test_build_tier1_statements_is_byte_identical_across_two_runs_given_identical_worldstate():
    """The whole point of Tier 1: re-rendering an unchanged WorldState
    must not itself introduce wording/identity churn -- including the
    statement's own id, which is derived deterministically from its
    grounding item's id, not a fresh uuid."""
    state = WorldState()
    state.facts.append(Fact(content="User is considering quitting."))
    state.goals.append(Goal(content="Move to the Product team."))

    first = build_tier1_statements(state)
    second = build_tier1_statements(state)
    assert first == second


def test_tier1_grounding_item_ids_reference_real_worldstate_ids():
    state = WorldState()
    state.facts.append(Fact(content="A fact."))
    statements = build_tier1_statements(state)
    assert statements[0].grounding_item_ids == [state.facts[0].id]


def test_tier1_renders_second_person_voice():
    state = WorldState()
    state.facts.append(Fact(content="User is considering quitting."))
    statements = build_tier1_statements(state)
    assert statements[0].text == "You are considering quitting."


def test_tier1_respects_status_filters():
    state = WorldState()
    state.goals.append(Goal(content="An abandoned goal.", status="abandoned"))
    state.goals.append(Goal(content="An active goal.", status="active"))
    state.decisions.append(Decision(content="An expired option.", status="expired"))
    state.decisions.append(Decision(content="An open option.", status="open"))

    statements = build_tier1_statements(state)
    texts = {s.text for s in statements}
    assert "An active goal." in texts
    assert "An abandoned goal." not in texts
    # Decision content is now wrapped in a sentence template (see
    # test_tier1_decision_renders_as_a_full_sentence_not_a_bare_label),
    # so status filtering is checked via substring containment rather
    # than exact text equality.
    assert any("An open option." in t for t in texts)
    assert not any("An expired option." in t for t in texts)


def test_tier1_empty_worldstate_produces_no_statements():
    assert build_tier1_statements(WorldState()) == []


def test_tier1_ids_are_namespaced_by_kind():
    """Two different kinds should never collide on id even if their
    underlying WorldState items happened to share a uuid (astronomically
    unlikely, but the f"tier1:{kind}:{item.id}" scheme should make it
    structurally impossible regardless)."""
    state = WorldState()
    state.facts.append(Fact(content="Same text."))
    state.claims.append(Claim(content="Same text."))
    statements = build_tier1_statements(state)
    ids = [s.id for s in statements]
    assert len(ids) == len(set(ids))


# --- Tier 1 completeness: Unknown/Entity/Assumption/Inference rendering
# and the Decision bare-label fix (see engine/decisions.md "Tier 1
# completeness + has_knowledge_correction calibration") ---


def test_tier1_renders_unknown_as_uncertainty_kind():
    state = WorldState()
    state.unknowns.append(Unknown(content="What is the reason for the delay?"))
    statements = build_tier1_statements(state)
    assert len(statements) == 1
    assert statements[0].kind == "uncertainty"
    assert statements[0].text == "What is the reason for the delay?"
    assert statements[0].grounding_item_ids == [state.unknowns[0].id]


def test_tier1_respects_unknown_status_filter():
    """Unknown.status is never actually "resolved" in practice (builder.py
    deletes a resolved Unknown rather than marking it), but the filter is
    still tested defensively, same as every other kind's status filter."""
    state = WorldState()
    state.unknowns.append(Unknown(content="An open question.", status="open"))
    state.unknowns.append(Unknown(content="A resolved question.", status="resolved"))
    texts = {s.text for s in build_tier1_statements(state)}
    assert "An open question." in texts
    assert "A resolved question." not in texts


def test_tier1_skips_entity_with_no_attributes_or_relationships():
    """A bare Entity mention with nothing else to say would just
    redundantly restate what a Fact already says -- deliberately skipped,
    not a gap."""
    state = WorldState()
    state.entities.append(Entity(name="friend"))
    assert build_tier1_statements(state) == []


def test_tier1_renders_entity_with_attributes():
    state = WorldState()
    state.entities.append(Entity(
        name="Sarah",
        attributes=[EntityAttribute(attribute="role", value="Head of Product")],
    ))
    statements = build_tier1_statements(state)
    assert len(statements) == 1
    assert statements[0].kind == "entity"
    assert "Sarah" in statements[0].text
    assert "Head of Product" in statements[0].text
    assert statements[0].grounding_item_ids == [state.entities[0].id]


def test_tier1_respects_entity_status_filter():
    state = WorldState()
    state.entities.append(Entity(
        name="Active", status="active",
        attributes=[EntityAttribute(attribute="role", value="X")],
    ))
    state.entities.append(Entity(
        name="Retracted", status="retracted",
        attributes=[EntityAttribute(attribute="role", value="Y")],
    ))
    texts = " ".join(s.text for s in build_tier1_statements(state))
    assert "Active" in texts
    assert "Retracted" not in texts


def test_tier1_renders_assumption_items():
    state = WorldState()
    state.assumption_items.append(Assumption(content="User assumes the freeze is temporary."))
    statements = build_tier1_statements(state)
    assert len(statements) == 1
    assert statements[0].kind == "assumption"
    assert statements[0].text == "You assume the freeze is temporary."
    assert statements[0].grounding_item_ids == [state.assumption_items[0].id]


def test_tier1_renders_inference_items():
    state = WorldState()
    state.inference_items.append(Inference(content="User seems anxious about the timeline.", confidence=0.6))
    statements = build_tier1_statements(state)
    assert len(statements) == 1
    assert statements[0].kind == "inference"
    assert statements[0].text == "You seem anxious about the timeline."
    assert statements[0].grounding_item_ids == [state.inference_items[0].id]


def test_tier1_renders_emotional_signal_items():
    """Regression test for validation report Failure Mode #4:
    Interpretation's emotional_signals had no home in WorldState at all,
    let alone in Tier 1 -- see engine/decisions.md "Tier 1 completeness
    + has_knowledge_correction calibration"."""
    state = WorldState()
    state.emotional_signal_items.append(
        EmotionalSignalItem(emotion="disenchantment", intensity=0.8, confidence=0.9, source="explicit")
    )
    statements = build_tier1_statements(state)
    assert len(statements) == 1
    assert statements[0].kind == "emotion"
    assert statements[0].text == "You're experiencing disenchantment (intensity 8/10)."
    assert statements[0].grounding_item_ids == [state.emotional_signal_items[0].id]


def test_tier1_respects_emotional_signal_status_filter():
    state = WorldState()
    state.emotional_signal_items.append(
        EmotionalSignalItem(emotion="relief", intensity=0.5, confidence=0.7, source="explicit", status="active")
    )
    state.emotional_signal_items.append(
        EmotionalSignalItem(emotion="dread", intensity=0.6, confidence=0.7, source="inferred", status="retracted")
    )
    texts = " ".join(s.text for s in build_tier1_statements(state))
    assert "relief" in texts
    assert "dread" not in texts


def test_tier1_decision_renders_as_a_full_sentence_not_a_bare_label():
    """Regression test for the bare-label bug: real Interpretation output
    extracts decision_options as bare noun-phrase labels (e.g. "House",
    "MBA" -- see experiments/confidant-validation/log.md case D01), and
    to_second_person is a documented no-op on text with no "user"/"they"
    token, so a naive passthrough rendered as an isolated single-word
    bullet."""
    state = WorldState()
    state.decisions.append(Decision(content="House", status="open"))
    statements = build_tier1_statements(state)
    assert len(statements) == 1
    assert statements[0].text != "House"
    assert "House" in statements[0].text
    assert len(statements[0].text.split()) > 1


# --- Prompt hygiene regression guard: understanding/assumption_items/
# inference_items must never reach Judgment/Planner/Response's prompts
# (see src/state/world_state.py::PROMPT_EXCLUDED_FIELDS) ---

_MINIMAL_JUDGMENT = {
    "primary_problem": "", "primary_goal": "", "current_focus": "", "key_blockers": [],
    "secondary_issues": [], "open_unknowns": [], "active_decisions": [], "contradictions": [],
    "has_knowledge_correction": False, "knowledge_correction_target": "",
    "knowledge_correction_kind": "", "knowledge_correction_corrected_content": "",
    "has_risk_signal": False, "risk_scan": "No risk-worthy signal identified.", "risks": [],
    "opportunities": [], "has_decision_resolution": False, "decision_resolution_option": "",
    "decision_resolution_status": "", "stagnation_notes": [], "confidence": 0.5,
    "supporting_evidence": [],
}

_MINIMAL_PLANNER = {
    "primary_objective": "clarify uncertainty", "rationale": "Early turn.",
    "conversational_strategy": "ask exploratory questions", "resolution_blocker": "",
    "priority_topics": [], "questions_to_explore": [], "assumptions_to_test": [],
    "planning_constraints": [], "desired_outcome": "user gains clarity",
    "temporal_horizon": "immediate", "confidence": 0.5,
}


def _state_with_shadow_fields() -> WorldState:
    """A WorldState with real content in every field that must NOT reach
    a prompt, so the test would fail loudly (string present) rather than
    trivially pass on an empty list."""
    state = WorldState()
    state.assumption_items.append(Assumption(content="Assumes something."))
    state.inference_items.append(Inference(content="User seems anxious."))
    state.emotional_signal_items.append(
        EmotionalSignalItem(emotion="disenchantment", intensity=0.8, confidence=0.9, source="explicit")
    )
    return state


def _capture_call_provider():
    captured = {}

    def _call(provider_name, system_prompt, messages, schema, temperature, component="unknown", tracker=None):
        captured["messages"] = json.dumps(messages)
        captured["system_prompt"] = system_prompt
        if component == "Judgment":
            return json.dumps(_MINIMAL_JUDGMENT)
        if component == "Planner":
            return json.dumps(_MINIMAL_PLANNER)
        return json.dumps({"response_text": "ok", "confidence": 0.5})

    return _call, captured


def test_judgment_prompt_excludes_understanding_and_shadow_fields(monkeypatch):
    state = _state_with_shadow_fields()
    call, captured = _capture_call_provider()
    monkeypatch.setattr("src.judgment.engine.call_provider", call)
    run_judgment(state)
    assert "understanding" not in captured["messages"]
    assert "assumption_items" not in captured["messages"]
    assert "inference_items" not in captured["messages"]
    assert "emotional_signal_items" not in captured["messages"]
    assert "User seems anxious." not in captured["messages"]
    assert "disenchantment" not in captured["messages"]


def test_planner_prompt_excludes_understanding_and_shadow_fields(monkeypatch):
    state = _state_with_shadow_fields()
    call, captured = _capture_call_provider()
    monkeypatch.setattr("src.planner.engine.call_provider", call)
    run_planner(state, Judgment(**_MINIMAL_JUDGMENT))
    assert "understanding" not in captured["messages"]
    assert "assumption_items" not in captured["messages"]
    assert "inference_items" not in captured["messages"]
    assert "emotional_signal_items" not in captured["messages"]


def test_response_prompt_excludes_understanding_and_shadow_fields(monkeypatch):
    state = _state_with_shadow_fields()
    call, captured = _capture_call_provider()
    monkeypatch.setattr("src.response.engine.call_provider", call)
    run_response_generator(state, Judgment(**_MINIMAL_JUDGMENT), Planner(**_MINIMAL_PLANNER))
    assert "understanding" not in captured["messages"]
    assert "assumption_items" not in captured["messages"]
    assert "inference_items" not in captured["messages"]
    assert "emotional_signal_items" not in captured["messages"]
