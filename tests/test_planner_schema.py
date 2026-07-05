"""
Structural tests for the Planner schema (src/planner/schema.py).

Planner itself is a live LLM call (run_planner), same category as
run_interpretation/run_judgment -- not unit-tested here. What IS
testable without any LLM call are the schema's structural guarantees:
Pydantic validation that holds regardless of what any model outputs.
Same category of test as Interpretation's urgency/impact_domains enum
checks and Judgment's confidence bounds.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.planner.schema import Planner

REQUIRED_FIELDS = dict(
    primary_objective="clarify uncertainty",
    rationale="Judgment's primary_problem is still unresolved.",
    conversational_strategy="ask exploratory questions",
    resolution_blocker="unresolved uncertainty",
    desired_outcome="user understands the primary blocker",
    temporal_horizon="near_term",
    confidence=0.5,
)


def test_minimal_planner_constructs_with_defaulted_lists():
    plan = Planner(**REQUIRED_FIELDS)
    assert plan.priority_topics == []
    assert plan.questions_to_explore == []
    assert plan.assumptions_to_test == []
    assert plan.planning_constraints == []


@pytest.mark.parametrize("value", ["immediate", "near_term", "long_term"])
def test_temporal_horizon_accepts_all_three_spec_values(value):
    plan = Planner(**{**REQUIRED_FIELDS, "temporal_horizon": value})
    assert plan.temporal_horizon == value


def test_temporal_horizon_rejects_out_of_enum_value():
    with pytest.raises(ValidationError):
        Planner(**{**REQUIRED_FIELDS, "temporal_horizon": "eventually"})


@pytest.mark.parametrize("bad_confidence", [-0.01, 1.01, 2.0, -5.0])
def test_confidence_rejects_out_of_range_values(bad_confidence):
    with pytest.raises(ValidationError):
        Planner(**{**REQUIRED_FIELDS, "confidence": bad_confidence})


@pytest.mark.parametrize(
    "missing_field",
    [
        "primary_objective",
        "rationale",
        "conversational_strategy",
        "resolution_blocker",
        "desired_outcome",
        "temporal_horizon",
        "confidence",
    ],
)
def test_required_scalar_fields_are_actually_required(missing_field):
    fields = {k: v for k, v in REQUIRED_FIELDS.items() if k != missing_field}
    with pytest.raises(ValidationError):
        Planner(**fields)


def test_list_fields_accept_populated_values():
    plan = Planner(
        **REQUIRED_FIELDS,
        priority_topics=["topic a", "topic b"],
        questions_to_explore=["what does X mean?"],
        assumptions_to_test=["user believes Y"],
        planning_constraints=["preserve user agency"],
    )
    assert plan.priority_topics == ["topic a", "topic b"]
    assert plan.questions_to_explore == ["what does X mean?"]
    assert plan.assumptions_to_test == ["user believes Y"]
    assert plan.planning_constraints == ["preserve user agency"]
