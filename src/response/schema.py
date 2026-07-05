"""
Response schema for Confidant's presentation layer.

Implements engine/specs/response-generator-specification-v1.md's Output
section verbatim -- two fields, exactly as specified. This is the first
layer in the pipeline whose output (`response_text`) is actually shown to
the user; every other layer's output (Interpretation, WorldState,
Judgment, Planner) is an internal cognitive artifact. Nothing about that
changes the schema shape, though -- still one Pydantic model, still
produced by one structured-output call, same "one call, one schema"
discipline as Judgment v2 and Planner v1.

`confidence` here is NOT a new, independently-formed assessment -- per
the spec's "Handling Uncertainty" section, Response Generator "should
reflect the confidence of upstream cognition" and "must never exaggerate
certainty." It's a faithful carry-through of how confident Judgment and
Planner already are, expressed as a single number, not a fresh judgment
about the situation.

`response_text` rejects empty/whitespace-only values (mode="after"
validator, not just Field(min_length=1) -- so "   " is caught too, not
just ""). Found via a live Ollama/llama3.2:3b dispatch: the model
returned an empty string and it passed validation silently, even though
an empty response is a hard failure for this layer specifically -- unlike
every upstream layer, where an empty list/string is often the CORRECT
sparse answer, response_text is the ONE artifact the user actually sees,
so "validated" must mean "usable," not just "present." Same "empty is as
useless as missing" principle already enforced at the provider level in
src/llm/providers.py's _extract_message_content.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class Response(BaseModel):
    response_text: str
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("response_text", mode="after")
    @classmethod
    def _reject_empty_response_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("response_text must not be empty or whitespace-only")
        return value
