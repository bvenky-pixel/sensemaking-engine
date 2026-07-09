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
- **Active Decisions** — Outstanding decisions.
- **Open Unknowns** — Unknowns that materially affect goals.
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
