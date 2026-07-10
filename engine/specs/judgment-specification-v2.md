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

**One deliberate, narrow exception to #2** (added 2026-07-10, see
engine/decisions.md "decision lifecycle, round 3"): Decision Resolutions
are a conclusion Judgment draws (a previously-open decision's fate has
changed), but that conclusion is also written back into
`WorldState.decisions.status` by the orchestrator, since it was the only
available fix for a signal Interpretation is structurally unable to
produce. Judgment still never writes anything itself — the write-back is
a separate orchestrator-level step consuming Judgment's output, and it's
scoped to exactly this one field, not a general license for Judgment to
start mutating WorldState.

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
    key_blockers,
    resolved_since_last_turn,
    open_unknowns,
    active_decisions,
    contradictions,
    risks,
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
- **Key Blockers** — Constraints preventing progress.
- **Active Decisions** — Outstanding decisions still marked `open` in
  WorldState.decisions, MINUS any Judgment is reporting a Decision
  Resolution for this same turn (see below) — a decision stops being
  active the moment its fate is recognized, even before the write-back
  actually lands in WorldState.
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
- **Decision Resolutions — write-back exception.** This is the one place
  Judgment's normally read-only relationship with WorldState is broken:
  `src/state/builder.py::apply_judgment_resolutions` is called by the
  orchestrator immediately after Judgment returns, applying
  `decision_resolutions` to `WorldState.decisions` (matched by the same
  word-overlap mechanism as Interpretation's `_apply_decision_events`,
  since Judgment's `option` should already be close to exact). This
  reopens the write-back architecture question the original v1.0 gap
  list explicitly deferred — justified here because there was no other
  way to get a real, already-available signal (Judgment sees the exact
  text; Interpretation structurally cannot) to actually reach WorldState.
- **Contradictions** — Conflicts present in WorldState.
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
- **Opportunities** — Factors likely to accelerate progress.
- **Trajectory** — Improving, Stable, Deteriorating, or Uncertain.
- **Confidence** — Overall confidence in the assessment.
- **Supporting Evidence** — References to WorldState objects supporting each conclusion.

---

## Observations vs Assessments

Observations summarize WorldState.

Assessments are the first layer of reasoning built on those observations.

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
