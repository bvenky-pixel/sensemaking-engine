"""
Structural tests for the Personal Operating Model schema
(src/pom/schema.py) -- same category as tests/test_planner_schema.py:
Pydantic validation guarantees that hold regardless of what any model
outputs.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.pom.schema import (
    BeliefSystem,
    IdentitySystem,
    InferredPOMBatch,
    MotivationSystem,
    NarrativeSystem,
    PersonalOperatingModel,
    RelationshipSystem,
    StressSystem,
    TheoryOfMindEntry,
    TheoryOfMindSystem,
)


def test_personal_operating_model_defaults_to_empty_everything():
    pom = PersonalOperatingModel()
    assert pom.belief.beliefs == []
    assert pom.relationship.relationships == []
    assert pom.identity.self_concept == ""
    assert pom.motivation.autonomy == "unclear"
    assert pom.motivation.competence == "unclear"
    assert pom.motivation.relatedness == "unclear"
    assert pom.learning_style.style == ""
    assert pom.stress.level == "unclear"
    assert pom.narrative.arc == "unclear"
    assert pom.theory_of_mind.entries == []


def test_inferred_pom_batch_defaults_to_empty_everything():
    batch = InferredPOMBatch()
    assert batch.identity == IdentitySystem()
    assert batch.motivation == MotivationSystem()
    assert batch.stress == StressSystem()
    assert batch.narrative == NarrativeSystem()
    assert batch.theory_of_mind == TheoryOfMindSystem()


@pytest.mark.parametrize("level", ["low", "moderate", "high", "unclear"])
def test_motivation_accepts_all_four_confidence_levels(level):
    m = MotivationSystem(autonomy=level, competence=level, relatedness=level)
    assert m.autonomy == level


def test_motivation_rejects_out_of_enum_value():
    with pytest.raises(ValidationError):
        MotivationSystem(autonomy="extremely high")


@pytest.mark.parametrize("arc", ["redemptive", "contamination", "stable", "unclear"])
def test_narrative_accepts_all_four_arc_values(arc):
    n = NarrativeSystem(arc=arc)
    assert n.arc == arc


def test_narrative_rejects_out_of_enum_arc():
    with pytest.raises(ValidationError):
        NarrativeSystem(arc="heroic")


def test_theory_of_mind_entry_requires_entity_name_and_perspective():
    with pytest.raises(ValidationError):
        TheoryOfMindEntry()


def test_theory_of_mind_system_holds_multiple_entries():
    tom = TheoryOfMindSystem(entries=[
        TheoryOfMindEntry(entity_name="manager", inferred_perspective="Wants the project to ship on time."),
        TheoryOfMindEntry(entity_name="partner", inferred_perspective="Wants more time together."),
    ])
    assert len(tom.entries) == 2


def test_belief_system_holds_a_plain_list_of_strings():
    b = BeliefSystem(beliefs=["The market is competitive.", "Leaving without a backup is risky."])
    assert len(b.beliefs) == 2


def test_relationship_system_holds_a_plain_list_of_strings():
    r = RelationshipSystem(relationships=["Manager -- role is manager; has final say on transfers."])
    assert len(r.relationships) == 1
