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

Judgment v3 design pass (2026-07-19, backlog #228, see engine/decisions.md
"Judgment v3 design pass"): `engine/specs/judgement-v3-design` (a
discussion draft, never frozen, most of it never implemented) was
reviewed at the founder's explicit direction. Four of its seven named
responsibilities were still genuinely unaddressed by v2 as of this round
-- `situation_assessment`, `contradiction_significance`,
`risk_significance`, and `decision_readiness` below, each covering
exactly one -- added the same way every other Judgment field has been:
grounded, no boolean-gate (no evidence yet of a detects-but-fails-to-
transcribe failure for any of these, same reasoning as secondary_issues/
stagnation_notes), and defaulted to "" so no existing test fixture across
the codebase needed updating. Three of the draft's other items were
deliberately NOT built, each for a specific reason: Salience Detection's
"explicit ranking" (already-shipped primary_problem/secondary_issues
split covers "central vs. secondary"; "background information" needs no
field by definition; ranking beyond list order has no motivating
evidence). Uncertainty Assessment's "separate assessment confidence"
(the draft's own Open Questions section left this genuinely undecided;
`confidence` below already answers "how complete is the evidentiary
basis," the same question in different words). Goal Progress Assessment
as a full active/stagnant/uncertain enum (superseded by `stagnation_notes`
already, same as `trajectory` -- see that field's own 2026-07-11
supersession decision immediately below; re-litigating it now with no new
evidence would repeat the mistake that decision was made to avoid).
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


class KnowledgeCorrection(BaseModel):
    """
    Signals that a Fact or Claim already tracked in WorldState (status
    still "active" as of the WorldState Judgment was given) is stale or
    redundant, per this turn's fuller picture of WorldState.facts/claims.
    `target` MUST be the EXACT text of the existing WorldState.facts/
    claims entry being corrected -- same reasoning as DecisionResolution.
    option above: Judgment is given the full serialized WorldState
    verbatim, so it can quote the real thing directly rather than
    inventing a label.

    kind="retracted": target is no longer true, no replacement known --
    corrected_content is "".
    kind="superseded": target is outdated or a reworded near-duplicate of
    a clearer statement -- corrected_content carries that replacement
    text, which src/state/builder.py appends as a fresh, active item of
    the SAME type (Fact stays Fact, Claim stays Claim); target itself is
    marked superseded, never deleted.

    One model covers BOTH Facts and Claims rather than splitting into
    FactCorrection/ClaimCorrection -- matching happens by content
    (src/state/builder.py searches WorldState.facts then WorldState.claims
    for `target`), not by a type Judgment would have to declare itself;
    asking Judgment to also classify the tier is pure transcription risk
    with no upstream evidence it's needed. See engine/decisions.md
    "Fact/Claim correction and near-duplicate consolidation".
    """

    target: str
    kind: Literal["retracted", "superseded"]
    # Required (non-empty) only when kind == "superseded". NOT enforced
    # by a raising validator here -- a hard ValidationError on this one
    # field would fail the entire Judgment call over one malformed entry
    # in a new, unproven mechanism. Enforced instead by Judgment's own
    # auto-repair validator below AND, independently, by
    # src/state/builder.py::apply_knowledge_corrections (an entry can
    # arrive there having bypassed the repair path entirely, if the model
    # writes directly into knowledge_corrections).
    corrected_content: str = ""


class Judgment(BaseModel):
    primary_problem: str
    primary_goal: str
    current_focus: str

    # v2.0 (added 2026-07-19, see engine/decisions.md "Judgment v3 design
    # pass", backlog #228): Judgment v3 draft's "Situation Assessment"
    # responsibility -- a higher-level FRAME for the whole situation, not
    # a third way of saying primary_problem (the specific blocking issue)
    # or current_focus (what the user is doing about it). Optional/
    # defaulted, no boolean-gate -- brand new field, no evidence yet of a
    # transcription-compliance failure to gate against.
    situation_assessment: str = ""

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

    # v2.0 (added 2026-07-19, see engine/decisions.md "Judgment v3 design
    # pass", backlog #228): Judgment v3 draft's "Contradiction Assessment"
    # responsibility, distinct from `contradictions` above -- that field
    # RECORDS a tension (Interpretation's own role, in the draft's own
    # framing, though built here since Interpretation has no contradictions
    # field -- see #239); this field ASSESSES what the tension actually
    # IMPLIES, one sentence, never a restatement of the contradiction
    # itself. Empty whenever contradictions is empty, or a real
    # contradiction exists but no honest implication can be drawn yet.
    contradiction_significance: str = ""

    # v1.7 (added 2026-07-12, see engine/decisions.md "Fact/Claim
    # correction and near-duplicate consolidation"): the structured,
    # WorldState-mutating counterpart to contradictions just above --
    # contradictions is free text with no write-back path (confirmed by
    # grep: it only ever flows into Planner's prompt and an eval metric
    # count). This closes two related gaps at once: (1) FactStatus/
    # ClaimStatus already anticipate "superseded"/"retracted" (see
    # src/state/world_state.py) but nothing ever assigns them, and (2)
    # near-duplicate Facts/Claims (paraphrased restatements of the same
    # underlying content -- _merge_content_items in src/state/builder.py
    # dedups by exact match only) accumulate with no decay. Both route
    # through this ONE mechanism rather than two: both are really the
    # same underlying judgment call -- "is this WorldState fact/claim
    # still the best current statement, or should something replace it?"
    # -- and Judgment already has full WorldState visibility plus the
    # contradictions cross-check instruction to draw on. Deliberately NOT
    # a mechanical word-overlap merge: "Boss denied the transfer." and
    # "Boss approved the transfer." score 0.67 fuzzy overlap under the
    # same formula used for Unknown resolution elsewhere in this
    # codebase -- well within a plausible near-duplicate threshold, which
    # would silently conflate two opposite-meaning facts. Judgment
    # reasons about meaning, not surface word overlap, so it doesn't have
    # that false-positive risk. has_knowledge_correction is the SAME
    # boolean-gate lever as has_decision_resolution -- same
    # transcription-compliance rationale (Judgment already has the
    # ground truth in front of it, the risk is forgetting to copy it
    # into the structured field).
    has_knowledge_correction: bool
    knowledge_correction_target: str  # exact WorldState facts/claims text; "" if has_knowledge_correction is False
    knowledge_correction_kind: Literal["", "retracted", "superseded"]
    knowledge_correction_corrected_content: str  # required only when kind == "superseded"; "" otherwise
    knowledge_corrections: List[KnowledgeCorrection] = Field(default_factory=list)

    # v1.9 (added 2026-07-15, see engine/decisions.md "Tier 1
    # completeness + has_knowledge_correction calibration" -- the
    # near_duplicate_rewording calibration miss, and its own restructure
    # after v1.8 measurably regressed has_knowledge_correction): a
    # PURELY OBSERVATIONAL field, deliberately placed AFTER
    # has_knowledge_correction's whole block rather than before it (v1.8
    # placed it between contradictions and has_knowledge_correction and
    # a live re-run showed has_knowledge_correction's contradictions-
    # adjacency compliance -- the one confirmed, measured fix from the
    # prior round -- regressed as a direct result: contradictions was
    # correctly populated but has_knowledge_correction stayed False in
    # the same response, the exact "detected but didn't transcribe"
    # failure the adjacency fix had eliminated). has_knowledge_correction
    # MUST NOT depend on this field's value -- it cannot, structurally:
    # by the time the model generates near_duplicates, it has already
    # committed to has_knowledge_correction several fields back. This
    # field exists solely to observe, independent of the correction
    # gate, whether the model demonstrably runs a near-duplicate check
    # at all (empty vs. absent was previously indistinguishable). Once
    # live data confirms whether/how reliably the model populates this,
    # a future round can decide how to fold a real near-duplicate hit
    # into knowledge_corrections -- e.g. mechanically in builder.py
    # rather than via a second LLM-side boolean gate, avoiding the
    # sequential-boolean-gate fragility this round's attempt ran into.
    near_duplicates: List[str] = Field(default_factory=list)

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

    # v2.0 (added 2026-07-19, see engine/decisions.md "Judgment v3 design
    # pass", backlog #228): Judgment v3 draft's "Decision Readiness"
    # responsibility -- whether the user appears to actually be weighing
    # the open option(s) in active_decisions, or whether the decision
    # looks blocked/stalled, never a recommendation of which option to
    # pick (that stays a future Planner's job). Empty whenever
    # active_decisions is empty, or nothing beyond "a decision is open"
    # is discernible yet.
    decision_readiness: str = ""

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

    # v2.0 (added 2026-07-19, see engine/decisions.md "Judgment v3 design
    # pass", backlog #228): Judgment v3 draft's "Risk Assessment"
    # materiality responsibility -- distinct from risk_scan (which
    # justifies the has_risk_signal check) and risks (specific factors).
    # One sentence on whether/how the named risk(s) materially constrain
    # the primary goal or decision -- not every risk worth naming in
    # `risks` also rises to this bar. Empty whenever has_risk_signal is
    # false, or risks exist but none is materially constraining.
    risk_significance: str = ""

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

    # Migrated from content-based (prose quotes/paraphrases) to real
    # KnowledgeItem.id references (2026-07-19, backlog #242, see
    # engine/decisions.md "Judgment: supporting_evidence migrated to
    # KnowledgeItem id references") -- WorldState objects have carried
    # stable ids since backlog #81/#82, and every WorldState item's `id`
    # is already visible to the model (it's a plain field, not excluded
    # from the prompt's `state.model_dump_json` dump), so this no longer
    # needs to be prose. Each entry should be the real `id` of the
    # specific WorldState item (a Fact, Claim, Goal, ...) that justifies
    # a conclusion above. src/judgment/engine.py::run_judgment filters
    # this down to ids that actually exist in the WorldState given this
    # call -- never trusts the model's own ids uncritically, same
    # discipline as src/insight/engine.py's/src/understanding/tier2_engine.py's
    # own grounding enforcement.
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

        # has_knowledge_correction=True is the model's own committed
        # signal that knowledge_correction_target/kind (and, for
        # "superseded", corrected_content) name a real correction. Same
        # mechanical-relocation repair as decision_resolutions above, but
        # the replacement-content requirement is CONDITIONAL on kind --
        # "retracted" has no replacement text at all (corrected_content
        # stays ""), "superseded" requires real, non-empty
        # corrected_content, never fabricated here: if the model left it
        # blank for a superseded correction, this repair intentionally
        # does NOT construct an entry (silently drop rather than
        # fabricate, same discipline as every _apply_* function in
        # src/state/builder.py). src/state/builder.py's own
        # apply_knowledge_corrections defensively re-checks this same
        # condition for entries that arrive pre-built in
        # knowledge_corrections, bypassing this repair path entirely.
        if self.has_knowledge_correction and not self.knowledge_corrections:
            target = self.knowledge_correction_target.strip()
            corrected = self.knowledge_correction_corrected_content.strip()
            kind = self.knowledge_correction_kind
            valid_for_kind = kind == "retracted" or (kind == "superseded" and corrected)
            if target and kind and valid_for_kind:
                self.knowledge_corrections = [
                    KnowledgeCorrection(
                        target=target,
                        kind=kind,
                        corrected_content=corrected if kind == "superseded" else "",
                    )
                ]
        return self
