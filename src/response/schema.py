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
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Response(BaseModel):
    response_text: str
    confidence: float = Field(ge=0.0, le=1.0)
