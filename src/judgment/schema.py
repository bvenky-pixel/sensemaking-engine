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

UPDATE (2026-07-11, see engine/decisions.md "Judgment trajectory/
stagnation assessment"): WorldState now HAS that historical signal
(turn_count, provenance.first_seen/last_updated -- see
src/state/world_state.py). `resolved_since_last_turn` remains out of
scope (no motivating use case). `trajectory` is deliberately NOT brought
back as originally sketched (a single "Improving/Stable/Deteriorating/
Uncertain" enum) -- superseded by `stagnation_notes` below, a concrete,
evidence-cited alternative. See
engine/specs/judgment-specification-v2.md's Field Definitions for the
full supersession rationale.

`phase` (Prepare/Discover/Discern/...) is intentionally NOT part of this
schema at all -- it's kept as a separate, deterministic, non-LLM concern
in src/judgment/engine.py's `recommend_phase_transition`, explicitly
scoped as legacy compatibility only (see engine/decisions.md): the spec
doesn't mention phase, and its long-term owner is the future Planner, not
Judgment.
"""

from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, Field, model_validator


class DecisionResolution(BaseModel):
    """
    Signals that a decision option already tracked in WorldState (status
    still "open" as of the WorldState Judgment was given) has since been
    resolved or deferred, per this turn's Facts/Claims. `option` MUST be
    the EXACT text of the existing WorldState.decisions entry -- Judgment
    is given the full serialized WorldState verbatim (see
    src/judgment/engine.py::run_judgment), so unlike Interpretation's
    `decision_events` (a stateless, single-message function that can only
    guess at a prior turn's exact extracted text), Judgment can quote the
    real thing directly. See engine/decisions.md "decision lifecycle,
    round 3" for why this moved here instead of staying an Interpretation
    concern.
    """

    option: str
    status: Literal["resolved", "deferred"]


class Judgment(BaseModel):
    primary_problem: str
    primary_goal: str
    current_focus: str

    key_blockers: List[str] = Field(default_factory=list)

    # v1.5 (added 2026-07-10, see engine/decisions.md "Judgment salience --
    # first reasoning-depth v2 increment"): real, WorldState-grounded
    # issues Judgment noticed but deliberately did NOT escalate to
    # primary_problem. No boolean-gate here, unlike has_risk_signal/
    # has_decision_resolution -- those gates were added only after real
    # batch testing proved a specific detects-but-fails-to-transcribe
    # failure mode for those fields; adding one here pre-emptively, with
    # zero evidence of that failure shape for a brand-new field, would
    # invent unvalidated capability. Escalate later only if the same
    # failure shape shows up in live testing.
    secondary_issues: List[str] = Field(default_factory=list)

    open_unknowns: List[str] = Field(default_factory=list)
    active_decisions: List[str] = Field(default_factory=list)
    contradictions: List[str] = Field(default_factory=list)

    # v1.4 (see engine/decisions.md "decision lifecycle, round 3"):
    # Interpretation's decision_events (even after its own boolean-gate
    # escalation) kept failing for a structural reason, not a compliance
    # one -- Interpretation is a stateless, single-message function that
    # never sees WorldState.decisions, so "anchor to the previously-
    # extracted option text" asked it to recall a string it was never
    # shown. Judgment reads the full WorldState every turn (including the
    # real, exact decision text), so it can quote it directly instead of
    # guessing. `has_decision_resolution` is the SAME boolean-gate lever
    # that already fixed has_assumption/has_risk_signal -- appropriate
    # here because, unlike decision_events, this is once again a
    # transcription-compliance problem (does the model bother to check
    # and copy), not a retrieval problem (Judgment already has the
    # ground truth in front of it).
    has_decision_resolution: bool
    decision_resolution_option: str  # exact WorldState.decisions text; "" if has_decision_resolution is False
    decision_resolution_status: Literal["", "resolved", "deferred"]
    decision_resolutions: List[DecisionResolution] = Field(default_factory=list)

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

    # v1.6 (added 2026-07-11, see engine/decisions.md "Judgment
    # trajectory/stagnation assessment"): Judgment's own SYNTHESIS of the
    # raw "Stagnation Signals" input it's given (computed deterministically
    # by src/judgment/engine.py::compute_stagnation_signals from
    # WorldState.turn_count/provenance -- Judgment never computes the
    # turn-gap arithmetic itself, only reasons about which raw signal
    # actually matters). A raw signal explained by a stated Fact/Claim
    # (e.g. an external blocker, an agreed wait) should usually be left
    # out here, or reframed to acknowledge the explanation -- this is NOT
    # a restatement of the raw signals list, and empty is the correct,
    # common answer whenever nothing raw was given or nothing raw is
    # actually significant. No boolean-gate here, same reasoning as
    # secondary_issues -- no evidence yet of a transcription-compliance
    # failure for this brand-new field.
    stagnation_notes: List[str] = Field(default_factory=list)

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

        # has_decision_resolution=True is the model's own committed
        # signal that decision_resolution_option/status names a real
        # transition. If decision_resolutions is still empty at this
        # point, reconstruct one -- both source fields are already
        # structured (not free text to parse or guess at), so this is a
        # mechanical relocation, the same class of repair as risks above.
        if (
            self.has_decision_resolution
            and not self.decision_resolutions
            and self.decision_resolution_option.strip()
            and self.decision_resolution_status
        ):
            self.decision_resolutions = [
                DecisionResolution(
                    option=self.decision_resolution_option.strip(),
                    status=self.decision_resolution_status,
                )
            ]
        return self
