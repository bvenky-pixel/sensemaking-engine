# Judgment Specification v2

## Purpose

**Judgment** transforms accumulated knowledge into an objective assessment of the user's current situation.

It does **not** generate responses, plan actions, or provide advice.

Its sole responsibility is:

> **Given the current WorldState, what conclusions are justified?**

---

## Design Principles

1. Judgment reasons over **WorldState**, never raw conversation.
2. Judgment produces conclusions, not memory.
3. Judgment is stateless.
4. Every conclusion should be explainable with supporting evidence.
5. Judgment never invents facts.

**Two deliberate, narrow exceptions to #2**, confirmed by the founder as
the ongoing policy (2026-07-19, see engine/decisions.md "Judgment
write-back: confirmed as case-by-case policy", backlog #247 -- this
question was originally deferred in the v1.0 gap list, then reopened
2026-07-10 without ever being generalized into one written policy until
now):

1. **Decision Resolutions** (added 2026-07-10, see engine/decisions.md
   "decision lifecycle, round 3"): a conclusion Judgment draws (a
   previously-open decision's fate has changed) is also written back
   into `WorldState.decisions.status` by the orchestrator, since it was
   the only available fix for a signal Interpretation is structurally
   unable to produce.
2. **Knowledge Corrections** (added 2026-07-12, see engine/decisions.md
   "Fact/Claim correction and near-duplicate consolidation"): the same
   shape, for Facts/Claims Judgment recognizes as stale or redundant.

Judgment still never writes anything itself — each write-back is a
separate orchestrator-level step consuming Judgment's output, scoped to
exactly its own field, not a general license for Judgment to start
mutating WorldState. **Confirmed policy going forward**: any future
write-back need gets its own similarly narrow, independently-justified
exception, following this same precedent — not a generalized write-back
abstraction the two existing cases would be refactored to route through.

---

## Input

```python
WorldState
```

## Output

```python
Judgment(
    primary_problem,
    primary_goal,
    current_focus,
    situation_assessment,
    key_blockers,
    resolved_since_last_turn,
    open_unknowns,
    active_decisions,
    decision_readiness,
    contradictions,
    contradiction_significance,
    risks,
    risk_significance,
    opportunities,
    trajectory,
    confidence,
    supporting_evidence,
)
```

## Field Definitions

- **Primary Problem** — The single most important issue preventing progress.
- **Primary Goal** — The highest-priority active goal.
- **Current Focus** — What the user is currently working on.
- **Situation Assessment** — (added 2026-07-19, see engine/decisions.md
  "Judgment v3 design pass", backlog #228) Judgment v3 draft's
  "Situation Assessment" responsibility -- a single-sentence, higher-
  level characterization of the KIND of situation this is (e.g. "a
  stalled internal career transition"), not a third way of saying
  Primary Problem (the specific blocking issue) or Current Focus (what
  the user is doing about it). Empty whenever WorldState doesn't yet
  support a real characterization. No boolean-gate -- brand-new field,
  same "no gate without evidence of a transcription failure" discipline
  as Secondary Issues.
- **Key Blockers** — Constraints preventing progress.
- **Secondary Issues** — (added 2026-07-10, see engine/decisions.md
  "Judgment salience -- first reasoning-depth v2 increment") real,
  WorldState-grounded issues Judgment noticed but deliberately did NOT
  escalate to Primary Problem -- the first step toward the "salience"
  responsibility named in `engine/specs/judgement-v3-design` (never
  frozen or implemented in full, but this is its first concrete piece):
  Judgment should commit to a hierarchy of attention, not just a flat
  list. No boolean-gate paired with this field, unlike Has Risk Signal/
  Has Decision Resolution above -- those gates were added only after
  real batch testing proved a specific detects-but-fails-to-transcribe
  failure mode for those fields; this is a brand-new field with no such
  evidence yet, so it ships plain and would only be escalated the same
  way if live testing reveals that failure shape.
- **Active Decisions** — Outstanding decisions still marked `open` in
  WorldState.decisions, MINUS any Judgment is reporting a Decision
  Resolution for this same turn (see below) — a decision stops being
  active the moment its fate is recognized, even before the write-back
  actually lands in WorldState.
- **Decision Readiness** — (added 2026-07-19, see engine/decisions.md
  "Judgment v3 design pass", backlog #228) Judgment v3 draft's "Decision
  Readiness" responsibility -- whenever Active Decisions is non-empty,
  whether the user appears to actually be weighing the open option(s),
  whether real uncertainty is blocking that evaluation, or whether the
  decision looks stalled. NEVER a recommendation of which option to
  pick -- that stays a future Planner's job, per the draft's own
  Explicit Non-Responsibilities section. Empty whenever Active Decisions
  is empty. No boolean-gate, same reasoning as Situation Assessment.
- **Open Unknowns** — Unknowns that materially affect goals.
- **Has Decision Resolution / Decision Resolution Option / Decision
  Resolution Status / Decision Resolutions** — (added 2026-07-10, see
  engine/decisions.md "decision lifecycle, round 3") the same
  boolean-gate pattern as Has Risk Signal, but solving a different kind
  of problem. Interpretation's own `decision_events` field (the original
  home for this signal) proved structurally unable to hold: Interpretation
  is a stateless, single-message function that never sees WorldState, so
  asking it to "anchor to a previously-extracted option" asked it to
  recall exact text it was never shown — not a compliance gap a
  boolean-gate can fix, since the model has no ground truth to
  transcribe. Judgment reads the full WorldState verbatim every turn
  (including the real `WorldState.decisions` text), so it can quote the
  existing option directly instead of guessing — moving this signal here
  turns a retrieval problem back into a transcription-compliance
  problem, the kind boolean-gating already fixed twice this project
  (Has Assumption, Has Risk Signal). Paired with a code-level auto-repair
  validator (`Judgment._model_validator`, `src/judgment/schema.py`): if
  `has_decision_resolution` is `True` and `decision_resolutions` is still
  empty, `decision_resolution_option`/`decision_resolution_status` (both
  already-structured fields, not parsed free text) are mechanically
  recombined into a `DecisionResolution`.
- **Decision Resolutions — write-back exception.** One of the two places
  (see Design Principles above) Judgment's normally read-only
  relationship with WorldState is broken:
  `src/state/builder.py::apply_judgment_resolutions` is called by the
  orchestrator immediately after Judgment returns, applying
  `decision_resolutions` to `WorldState.decisions` (matched by the same
  word-overlap mechanism as Interpretation's `_apply_decision_events`,
  since Judgment's `option` should already be close to exact). This
  reopened the write-back architecture question the original v1.0 gap
  list explicitly deferred — justified here because there was no other
  way to get a real, already-available signal (Judgment sees the exact
  text; Interpretation structurally cannot) to actually reach WorldState.
  Whether to generalize this into one write-back mechanism (vs. keep it
  and Knowledge Corrections below as independent, narrow exceptions) is
  now settled -- see Design Principles above.
- **Has Knowledge Correction / Knowledge Correction Target / Knowledge
  Correction Kind / Knowledge Correction Corrected Content / Knowledge
  Corrections — the second write-back exception** (added 2026-07-12, see
  engine/decisions.md "Fact/Claim correction and near-duplicate
  consolidation"): the same boolean-gate-plus-write-back shape as
  Decision Resolutions above, for Facts/Claims Judgment recognizes as
  stale (`kind="retracted"`) or a reworded duplicate of a clearer
  statement (`kind="superseded"`, which also appends a fresh active
  Fact/Claim carrying the replacement text).
  `src/state/builder.py::apply_knowledge_corrections` is the write-back
  step, matching by exact text first, fuzzy word-overlap second,
  restricted to `status=="active"` items only.
- **Contradictions** — Conflicts present in WorldState.
- **Contradiction Significance** — (added 2026-07-19, see
  engine/decisions.md "Judgment v3 design pass", backlog #228) Judgment
  v3 draft's "Contradiction Assessment" responsibility -- distinct from
  Contradictions above, which RECORDS a tension; this field ASSESSES
  what that tension actually IMPLIES (e.g. "Career advancement appears
  blocked despite positive performance signals"), never a restatement
  of the contradiction's own content. Empty whenever Contradictions is
  empty, or a real contradiction exists but no honest implication can
  be drawn yet. No boolean-gate, same reasoning as Situation Assessment.
- **Has Risk Signal** — (added 2026-07-09, see engine/decisions.md) a
  mandatory boolean, ordered before Risk Scan, forcing the model to
  commit to a low-entropy yes/no before writing the free-text
  justification or the Risks list. Added after a full 30-test
  re-validation showed Risk Scan's own finding failing to propagate into
  `risks` in a large fraction of tests (not just E03's input) despite an
  explicit cross-field consistency rule already in the prompt. Paired
  with a code-level auto-repair validator (`_repair_risk_list`,
  `src/judgment/schema.py`): if `has_risk_signal` is `True` and `risks`
  is still empty, Risk Scan's own sentence is relocated into `risks`
  rather than left contradicting it.
- **Risk Scan** — (added 2026-07-09, see engine/decisions.md) a mandatory
  reasoning field immediately following Has Risk Signal, justifying that
  answer with an explicit pass over WorldState content for risk-worthy
  signals (including modest epistemic-humility risks grounded in
  ambiguous or persistent negative-affect Claims) before finalizing
  Risks/Opportunities. Structural escalation after a prompt-only fix for
  this same gap (E03) failed to hold on re-test, per this project's
  "typed over prompted, once prompting has failed" discipline.
- **Risks** — Factors likely to hinder progress.
- **Risk Significance** — (added 2026-07-19, see engine/decisions.md
  "Judgment v3 design pass", backlog #228) Judgment v3 draft's "Risk
  Assessment" materiality responsibility -- distinct from Risk Scan
  (justifies the Has Risk Signal check) and Risks (specific factors):
  whether/how the named risk(s) MATERIALLY constrain the primary goal
  or an active decision (e.g. "Financial uncertainty appears to be a
  significant constraint on decision making"). Empty whenever Has Risk
  Signal is false, or Risks exist but none is materially constraining.
  No boolean-gate, same reasoning as Situation Assessment.
- **Opportunities** — Factors likely to accelerate progress.
- **Trajectory** — Improving, Stable, Deteriorating, or Uncertain.
  **SUPERSEDED (2026-07-11, see engine/decisions.md "Judgment
  trajectory/stagnation assessment").** Never implemented (blocked on
  WorldState having no turn history -- see `src/judgment/schema.py`'s
  original docstring). Now that WorldState has `turn_count`/`provenance`,
  this was deliberately NOT built as originally sketched: a single global
  Improving/Stable/Deteriorating/Uncertain label is exactly the kind of
  vague, unfounded-sounding output that reads as generic-LLM rather than
  something only a persistent, turn-numbered WorldState could produce.
  Replaced by **Stagnation Notes** below -- a concrete, evidence-cited
  alternative (same "record the supersession, don't silently delete"
  convention used for Interpretation's `decision_events`).
- **Stagnation Notes** — (added 2026-07-11, see engine/decisions.md
  "Judgment trajectory/stagnation assessment") Judgment's synthesis of a
  mechanically-computed "Stagnation Signals" input (turn_count minus
  provenance.last_updated for each active Goal/open Decision, computed in
  Python by `src/judgment/engine.py::compute_stagnation_signals` --
  deliberately NOT left to the model to notice/compute itself, the same
  reasoning that justified the Has Risk Signal/Has Decision Resolution
  boolean-gates: models don't reliably self-track things they should get
  right mechanically). Judgment decides which raw signal, if any, is
  actually significant -- a gap already explained by a stated Fact/Claim
  (an external blocker, an agreed wait) is left out or reframed, never
  used to imply the user is at fault. No boolean-gate on this field yet
  -- no evidence of a transcription-compliance failure for a brand-new
  field; add one later only if real testing shows that failure shape.
- **Confidence** — Overall confidence in the assessment.
- **Supporting Evidence** — References to WorldState objects supporting each conclusion.

---

## Observations vs Assessments

Observations summarize WorldState.

Assessments are the first layer of reasoning built on those observations.

Situation Assessment, Contradiction Significance, Risk Significance, and
Decision Readiness (added 2026-07-19, backlog #228) are a SECOND layer,
built on top of those first-layer assessments -- judgments about what the
first layer's own findings mean or imply, not new observations of
WorldState.

---

## Open Questions — resolved (2026-07-19, backlog #228, see engine/decisions.md "Judgment v3 design pass")

`engine/specs/judgement-v3-design` (a discussion draft, never frozen)
named three items as genuinely undecided. Reviewed at the founder's
explicit direction alongside the four fields above; each closed rather
than left open:

- **Should Judgment explicitly rank issues** (beyond Primary Problem +
  Secondary Issues)? **No.** The existing split already covers "central
  vs. secondary"; "background information" needs no field by definition
  (unsurfaced); explicit ordinal ranking has no motivating evidence.
- **Should Judgment assess confidence separately** from Interpretation's
  own confidence fields? **No.** Confidence above already answers "how
  complete is the evidentiary basis for this assessment" -- the same
  question the draft's Uncertainty Assessment responsibility was asking
  in different words.
- **Should Judgment assess trajectory** (Improving/Stagnant/
  Deteriorating)? **No, reaffirmed.** Already superseded by Stagnation
  Notes (2026-07-11) for the reasons that decision recorded; no new
  evidence since then argues for revisiting it.

---

## Judgment MUST NOT

- Coach
- Comfort
- Persuade
- Recommend actions
- Generate responses
- Ask follow-up questions

---

## Pipeline

```text
User Message
    ↓
Interpretation
    ↓
State Builder
    ↓
WorldState
    ↓
Judgment
    ↓
Planner
    ↓
Response
```
