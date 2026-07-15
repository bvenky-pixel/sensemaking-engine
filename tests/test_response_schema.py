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
    assert response.options == []


def test_options_defaults_to_empty_list():
    """options is new (Response v3 -- real choice buttons) -- omitting it
    entirely must still construct cleanly, since most turns are
    genuinely open-ended (see engine/decisions.md)."""
    response = Response(**REQUIRED_FIELDS)
    assert response.options == []


@pytest.mark.parametrize("options", [["The MBA"], ["The MBA", "The home loan"], ["A", "B", "C"]])
def test_options_accepts_one_to_three_items(options):
    response = Response(**{**REQUIRED_FIELDS, "options": options})
    assert response.options == options


def test_options_rejects_more_than_three_items():
    """Regression guard for prompt drift toward an exhaustive menu
    instead of 2-3 real choices -- see src/response/schema.py's own
    docstring on why this fails loud rather than silently truncating."""
    with pytest.raises(ValidationError):
        Response(**{**REQUIRED_FIELDS, "options": ["A", "B", "C", "D"]})


@pytest.mark.parametrize("bad_options", [[""], ["   "], ["The MBA", ""]])
def test_options_rejects_blank_entries(bad_options):
    with pytest.raises(ValidationError):
        Response(**{**REQUIRED_FIELDS, "options": bad_options})


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


@pytest.mark.parametrize("empty_value", ["", "   ", "\n\t"])
def test_empty_or_whitespace_response_text_is_rejected(empty_value):
    """Regression test: a live Ollama/llama3.2:3b dispatch returned an
    empty response_text and it passed validation silently -- see
    engine/decisions.md. response_text is the one artifact the user
    actually sees, so empty must be rejected, not treated as a valid
    (if sparse) answer the way empty lists are upstream."""
    with pytest.raises(ValidationError):
        Response(**{**REQUIRED_FIELDS, "response_text": empty_value})
