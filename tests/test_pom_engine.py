"""
Tests for src/pom/engine.py -- Personal Operating Model (see
engine/decisions.md "Personal Operating Model").

Mechanical systems (Belief, Relationship) are pure, deterministic
functions -- tested directly, no mocking, same category as
tests/test_learning.py. The LLM-inferred half (run_inferred_pom) is
mocked at src.pom.engine's own import path, same pattern as
tests/test_insight.py -- focus is the engine-level grounding enforcement
(never trust the model's own evidence quotes uncritically).
"""

from __future__ import annotations

import json

import pytest

from src.pom.engine import (
    POMEngineError,
    compute_belief_system,
    compute_relationship_system,
    run_inferred_pom,
)
from src.state.world_state import Entity, EntityAttribute


def _always_returns(payload):
    def _call(provider_name, system_prompt, messages, schema, temperature, component="unknown", tracker=None):
        return json.dumps(payload)
    return _call


# --- Mechanical systems ---

def test_compute_belief_system_deduplicates_preserving_first_occurrence_order():
    result = compute_belief_system(
        claims=["The market is competitive.", "Leaving without a backup is risky."],
        assumptions=["The market is competitive.", "Manager will approve the transfer."],
    )
    assert result.beliefs == [
        "The market is competitive.",
        "Leaving without a backup is risky.",
        "Manager will approve the transfer.",
    ]


def test_compute_belief_system_empty_inputs_produce_empty_list():
    assert compute_belief_system([], []).beliefs == []


def test_compute_relationship_system_skips_entity_with_no_attributes_or_relationships():
    entities = [Entity(name="friend", status="active")]
    assert compute_relationship_system(entities).relationships == []


def test_compute_relationship_system_renders_entity_with_attributes():
    entities = [
        Entity(
            name="Manager", status="active",
            attributes=[EntityAttribute(attribute="role", value="manager")],
            relationships=["has final say on transfers"],
        )
    ]
    result = compute_relationship_system(entities)
    assert len(result.relationships) == 1
    assert "Manager" in result.relationships[0]
    assert "role is manager" in result.relationships[0]
    assert "has final say on transfers" in result.relationships[0]


# --- LLM-inferred systems ---

def test_run_inferred_pom_returns_empty_default_for_empty_aggregated_content():
    result = run_inferred_pom("")
    assert result.identity.self_concept == ""
    assert result.motivation.autonomy == "unclear"


def test_run_inferred_pom_short_circuits_without_calling_the_provider_when_empty(monkeypatch):
    def _fail_if_called(*args, **kwargs):
        raise AssertionError("call_provider should never be reached for empty aggregated_content")

    monkeypatch.setattr("src.pom.engine.call_provider", _fail_if_called)
    run_inferred_pom("")


def test_grounding_filters_evidence_with_no_word_overlap(monkeypatch):
    """The model's own evidence quote for autonomy has zero word overlap
    with what was actually sent -- must be dropped, and since it's the
    ONLY evidence for that field, the level itself must downgrade to
    'unclear' rather than assert a score with no surviving grounding."""
    payload = {
        "identity": {"self_concept": "", "evidence": []},
        "motivation": {
            "autonomy": "high", "autonomy_evidence": ["Completely fabricated sentence about spaceships."],
            "competence": "unclear", "competence_evidence": [],
            "relatedness": "unclear", "relatedness_evidence": [],
        },
        "learning_style": {"style": "", "evidence": []},
        "stress": {"level": "unclear", "evidence": []},
        "narrative": {"arc": "unclear", "summary": "", "evidence": []},
        "theory_of_mind": {"entries": []},
    }
    monkeypatch.setattr("src.pom.engine.call_provider", _always_returns(payload))

    result = run_inferred_pom("Fact: User chose their own project timeline without any pushback.")

    assert result.motivation.autonomy == "unclear"
    assert result.motivation.autonomy_evidence == []


def test_grounding_keeps_evidence_with_real_word_overlap(monkeypatch):
    payload = {
        "identity": {"self_concept": "Someone who values independence at work.", "evidence": ["chose their own project timeline"]},
        "motivation": {
            "autonomy": "high", "autonomy_evidence": ["chose their own project timeline without any pushback"],
            "competence": "unclear", "competence_evidence": [],
            "relatedness": "unclear", "relatedness_evidence": [],
        },
        "learning_style": {"style": "", "evidence": []},
        "stress": {"level": "unclear", "evidence": []},
        "narrative": {"arc": "unclear", "summary": "", "evidence": []},
        "theory_of_mind": {"entries": []},
    }
    monkeypatch.setattr("src.pom.engine.call_provider", _always_returns(payload))

    result = run_inferred_pom("Fact: User chose their own project timeline without any pushback.")

    assert result.motivation.autonomy == "high"
    assert result.identity.self_concept == "Someone who values independence at work."


def test_theory_of_mind_entry_with_ungrounded_evidence_is_dropped_entirely(monkeypatch):
    payload = {
        "identity": {"self_concept": "", "evidence": []},
        "motivation": {
            "autonomy": "unclear", "autonomy_evidence": [],
            "competence": "unclear", "competence_evidence": [],
            "relatedness": "unclear", "relatedness_evidence": [],
        },
        "learning_style": {"style": "", "evidence": []},
        "stress": {"level": "unclear", "evidence": []},
        "narrative": {"arc": "unclear", "summary": "", "evidence": []},
        "theory_of_mind": {
            "entries": [
                {"entity_name": "manager", "inferred_perspective": "Wants the merger to fail.", "evidence": ["completely unrelated fabricated text"]},
            ]
        },
    }
    monkeypatch.setattr("src.pom.engine.call_provider", _always_returns(payload))

    result = run_inferred_pom("Entity: manager -- role is manager")

    assert result.theory_of_mind.entries == []


def test_raises_when_every_provider_fails(monkeypatch):
    def _always_invalid_json(*args, **kwargs):
        return "not valid json"

    monkeypatch.setattr("src.pom.engine.call_provider", _always_invalid_json)

    with pytest.raises(POMEngineError):
        run_inferred_pom("Fact: something real happened.")
