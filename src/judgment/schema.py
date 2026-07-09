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

from pydantic import BaseModel, Field, model_validator


class Judgment(BaseModel):
    primary_problem: str
    primary_goal: str
    current_focus: str

    key_blockers: List[str] = Field(default_factory=list)
    open_unknowns: List[str] = Field(default_factory=list)
    active_decisions: List[str] = Field(default_factory=list)
    contradictions: List[str] = Field(default_factory=list)

    # v1.3 (see engine/decisions.md): `risk_scan` alone (added 2026-07-09)
    # proved unreliable across a 30-test real-pipeline run -- the model
    # correctly identified a risk-worthy signal in its own free-text
    # reasoning but failed to copy it into `risks` in a large fraction of
    # those cases, not just the one input (E03) it was originally fixed
    # against. `has_risk_signal` is a much lower-entropy decision (a
    # boolean) than "remember to duplicate this sentence into another
    # field," ordered FIRST so the model commits to the yes/no answer
    # before writing the justification or the list -- and it gives
    # `_repair_risk_list` below a cheap, reliable signal to auto-repair
    # `risks` from `risk_scan`'s own text if the model still leaves the
    # list empty, without parsing or guessing at the free-text field.
    has_risk_signal: bool
    risk_scan: str
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

    @model_validator(mode="after")
    def _repair_risk_list(self):
        # has_risk_signal=True is the model's own committed signal that
        # risk_scan names a real finding. If risks is still empty at this
        # point, relocate risk_scan's own sentence into it rather than
        # leaving the two fields contradicting each other -- this doesn't
        # invent content (it's the model's own text) and doesn't parse or
        # guess at what risk_scan means (it's gated purely on the boolean,
        # never on the free text itself).
        if self.has_risk_signal and not self.risks and self.risk_scan.strip():
            self.risks = [self.risk_scan.strip()]
        return self
