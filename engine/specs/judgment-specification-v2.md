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
