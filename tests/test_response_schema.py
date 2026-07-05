"""
Structural tests for the Response schema (src/response/schema.py).

Response Generator itself is a live LLM call (run_response_generator),
same category as run_interpretation/run_judgment/run_planner -- not
unit-tested here. What IS testable without any LLM call are the schema's
structural guarantees: Pydantic validation that holds regardless of what
any model outputs. Same category of test as the Judgment/Planner schema
tests.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.response.schema import Response

REQUIRED_FIELDS = dict(
    response_text="It sounds like the timing here has been genuinely unclear for you.",
    confidence=0.5,
)


def test_minimal_response_constructs():
    response = Response(**REQUIRED_FIELDS)
    assert response.response_text == REQUIRED_FIELDS["response_text"]
    assert response.confidence == 0.5


@pytest.mark.parametrize("bad_confidence", [-0.01, 1.01, 2.0, -5.0])
def test_confidence_rejects_out_of_range_values(bad_confidence):
    with pytest.raises(ValidationError):
        Response(**{**REQUIRED_FIELDS, "confidence": bad_confidence})


@pytest.mark.parametrize("value", [0.0, 0.5, 1.0])
def test_confidence_accepts_boundary_values(value):
    response = Response(**{**REQUIRED_FIELDS, "confidence": value})
    assert response.confidence == value


@pytest.mark.parametrize("missing_field", ["response_text", "confidence"])
def test_required_fields_are_actually_required(missing_field):
    fields = {k: v for k, v in REQUIRED_FIELDS.items() if k != missing_field}
    with pytest.raises(ValidationError):
        Response(**fields)
