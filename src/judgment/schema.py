"""
Judgment schema for Confidant's reasoning layer.

Implements engine/specs/judgment-specification-v2.md's Output section,
with two fields deliberately removed per explicit scope decision (see
engine/decisions.md): `resolved_since_last_turn` and `trajectory` both
require a delta against a PREVIOUS WorldState/Judgment, which a single
WorldState snapshot can't supply -- WorldState v1 has no turn numbers or
retained history of state transitions. Add them back once WorldState
grows the historical signal needed (v1.1/v1.2 provenance work), not by
guessing at a delta here.

`phase` (Prepare/Discover/Discern/...) is intentionally NOT part of this
schema at all -- it's kept as a separate, deterministic, non-LLM concern
in src/judgment/engine.py's `recommend_phase_transition`, explicitly
scoped as legacy compatibility only (see engine/decisions.md): the spec
doesn't mention phase, and its long-term owner is the future Planner, not
Judgment.
"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class Judgment(BaseModel):
    primary_problem: str
    primary_goal: str
    current_focus: str

    key_blockers: List[str] = Field(default_factory=list)
    open_unknowns: List[str] = Field(default_factory=list)
    active_decisions: List[str] = Field(default_factory=list)
    contradictions: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    opportunities: List[str] = Field(default_factory=list)

    confidence: float = Field(ge=0.0, le=1.0)

    # Content-based (not ID-based) for now -- WorldState objects have no
    # stable IDs yet (deferred to WorldState v1.1). Each entry should be a
    # direct quote/close paraphrase of the specific WorldState content
    # (a Fact, Claim, Goal, ...) that justifies a conclusion above, so a
    # reader can trace every assessment back to something actually in
    # WorldState -- migrate to ID references once WorldState supports them.
    supporting_evidence: List[str] = Field(default_factory=list)
