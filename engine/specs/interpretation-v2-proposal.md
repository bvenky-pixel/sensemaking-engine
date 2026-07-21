# Interpretation v2 — Design Proposal

**Status:** Priority 1 IMPLEMENTED 2026-07-11 (see engine/decisions.md
"Interpretation v2 Priority 1" and src/interpretation/prompt.py) --
except `contradictions`/`risks`, deliberately deferred: this document
predates a decision made two days after its own last edit
(`interpretation-spec-v1.1.md`, frozen 2026-07-09, declined a
`contradictions` field on Interpretation because Judgment's own
`contradictions` field already owns "detect a conflict" -- Judgment also
already has a boolean-gated `risks` field). Tracing the pipeline
confirmed Judgment never reads raw Interpretation output at all (only
WorldState), and WorldState has no `contradictions`/`risks` tier today --
so an Interpretation-only version of these fields would be functionally
inert until a real architecture question is resolved (does this need its
own WorldState tier; how does it relate to Judgment's existing fields).
Priority 2 (Decision Events/Goal Updates/Entity Attribute Updates) was
already implemented separately, as v1.1, before this round.

**CONFIRMED by the founder (2026-07-19, backlog #239, see
engine/decisions.md "Interpretation: contradictions/risks stay
declined"): the deferral above still holds.** No new WorldState tier or
downstream consumer has emerged since 2026-07-11 that would make an
Interpretation-level `contradictions`/`risks` field anything but inert
debug output -- Judgment's own fields (now including
`contradiction_significance`/`risk_significance`, added 2026-07-19,
backlog #228) continue to own this responsibility with full WorldState
visibility Interpretation structurally lacks. These two fields remain
un-implemented by deliberate, confirmed choice, not by default.

**Priority 3 (state-aware architecture) treated as resolved by existing
precedent, not reopened (2026-07-19, backlog #241, see
engine/decisions.md "Interpretation: stateless-vs-state-aware treated
as resolved by precedent")**: the one time this concretely mattered
(2026-07-10, decision-lifecycle round 3), the founder's own real call
was to keep Interpretation stateless and relocate state-dependent
matching downstream (to Judgment, and since then Tier 2) rather than
restructure Interpretation's pipeline shape. This round proposed closing
Priority 3 on that same precedent rather than re-opening it from
scratch, and proceeded on that basis without objection -- flagged here
plainly, same as any other resolution this project records, so it's
easy to revisit if the other direction was actually wanted.

This document proposes the next iteration of Confidant's Interpretation Engine following evaluation of:

* 30 benchmark scenarios
* WorldState v1 state-evolution testing
* Live multi-turn walkthroughs
* Interpretation v0.9 production behavior

This is a design document, not a schema specification.

No prompt, schema, or code changes are implied by this document.

As with previous Interpretation versions:

1. Design discussion
2. Frozen specification
3. Migration document
4. Prompt changes
5. Schema implementation
6. Benchmark validation

---

# Executive Summary

Interpretation v0.9 successfully optimized for epistemic discipline.

The system demonstrated:

* low hallucination rates
* strong separation of evidence and inference
* consistent extraction of facts and claims
* reliable emotional signal detection

However benchmark evaluation revealed recurring under-extraction of meaningful structure.

The primary failure mode is not hallucination.

The primary failure mode is omission.

Interpretation often understands more than it records.

Interpretation v2 focuses on improving state completeness while preserving the evidence-first philosophy established in v0.9.

---

# Two Distinct Problem Domains

Evaluation surfaced two separate categories of shortcomings.

## Domain A — Understanding Quality

Questions such as:

* What is the user trying to achieve?
* What information is missing?
* What assumptions are they relying on?
* What tensions exist?
* What risks are present?

These concern understanding the current message.

---

## Domain B — State Evolution

Questions such as:

* Was a previous decision chosen?
* Was a goal completed?
* Did we learn something new about an entity?

These concern updating previously known information.

Interpretation v2 primarily targets Domain A.

Domain B concepts are documented as future candidates but intentionally deprioritized until v2 quality improvements are validated.

---

# Design Goals

Interpretation v2 should:

1. Preserve sparse-by-default behavior.
2. Preserve evidence-first reasoning.
3. Improve goal extraction.
4. Improve unknown extraction.
5. Improve assumption extraction.
6. Introduce contradiction detection.
7. Introduce risk identification.
8. Improve consistency between extracted state and downstream behavior.
9. Preserve low hallucination rates.

---

# Proposed Additions

## Contradictions

### Purpose

Capture tensions, inconsistencies, and conflicting realities described by the user.

A contradiction does not require formal logical inconsistency.

The goal is to capture meaningful tension.

### Examples

User:

> My manager says I'm doing great, but I was passed over for promotion.

Contradiction:

> Positive performance feedback conflicts with promotion outcome.

---

User:

> I love this relationship, but I think I need to leave.

Contradiction:

> Emotional attachment conflicts with desire to leave.

---

User:

> I want freedom, but I need financial stability.

Contradiction:

> Desire for freedom conflicts with need for stability.

### Proposed Schema

```python
contradictions: List[str]
```

Default:

```python
[]
```

---

## Risks

### Purpose

Capture plausible negative outcomes directly connected to the current situation.

Risks are not predictions.

Risks are not catastrophizing.

Risks are meaningful downside exposure.

### Examples

User:

> I'm considering quitting without another offer.

Risks:

* Loss of income
* Extended unemployment

---

User:

> My spouse is talking about divorce.

Risks:

* Relationship dissolution

### Proposed Schema

```python
risks: List[str]
```

Default:

```python
[]
```

---

# Existing Field Improvements

## Goals

### Problem Observed

Goals frequently remained empty despite clear evidence of desired outcomes.

### V2 Principle

Goals do not require explicit phrases such as:

* I want
* My goal is
* I need

Desired outcomes may be inferred when strongly supported by context.

### Examples

User:

> I've been trying to move into product management.

Goal:

> Move into product management.

---

User:

> My partner says we keep having the same argument.

Goal:

> Improve relationship conflict.

---

## Unknowns

### Problem Observed

Unknowns frequently remained empty even when downstream responses requested clarification.

### V2 Principle

Unknowns should identify information gaps that materially limit understanding.

Unknowns are not coaching questions.

Unknowns are not planning questions.

Unknowns should answer:

> What information is missing that would help explain the current situation?

### Consistency Rule

When:

```python
requires_clarification == True
```

unknowns should rarely be empty.

---

## Assumptions

### Problem Observed

Assumption extraction was overly conservative.

### V2 Principle

Assumptions are unstated beliefs connecting observations to conclusions.

### Examples

User:

> My friend hasn't replied for three days.
> I think they're angry.

Assumption:

> Lack of response indicates anger.

---

User:

> I wasn't promoted.
> My manager must not value me.

Assumption:

> Promotion outcome reflects personal value.

### Guidance

Many conversations genuinely contain no assumptions.

However, when a conclusion depends on an unstated belief, that belief should be captured.

---

# Consistency Invariants

Interpretation should internally self-check for consistency.

---

## Clarification Consistency

If:

```python
requires_clarification == True
```

then:

```python
unknowns
```

should rarely be empty.

---

## Decision Consistency

If alternatives are being compared:

```python
decision_options
```

should rarely be empty.

---

## Goal Consistency

If a desired outcome is clearly present:

```python
goals
```

should rarely be empty.

---

## Emotional Consistency

If meaningful emotional content is present:

```python
emotional_signals
```

should rarely be empty.

---

# Proposed Interpretation Schema v2

```python
class Interpretation(BaseModel):

    urgency: Literal["low", "medium", "high"]

    impact_domains: List[ImpactDomain]

    emotional_signals: List[EmotionalSignal]

    surface_complaint: str

    core_question: str

    core_question_confidence: float

    observed_facts: List[str]

    claims: List[str]

    goals: List[str]

    decision_options: List[str]

    assumptions: List[str]

    contradictions: List[str]

    risks: List[str]

    inferences: List[Inference]

    unknowns: List[str]

    biases: List[Bias]

    entities: List[str]

    clarity_score: float

    requires_clarification: bool
```

---

# Deferred State Evolution Signals

WorldState testing surfaced several additional gaps.

These concepts are intentionally deferred from the initial v2 implementation.

They should be revisited after benchmark validation of v2 quality improvements.

---

## Decision Events

Purpose:

Track lifecycle changes to previously identified decision options.

Illustrative shape:

```python
DecisionEvent:
    option: str
    event: Literal[
        "proposed",
        "chosen",
        "rejected",
        "deferred"
    ]
```

Example:

Option:

> Apply externally

Event:

> deferred

---

## Goal Updates

Purpose:

Track lifecycle changes to previously identified goals.

Illustrative shape:

```python
GoalUpdate:
    goal: str
    status: Literal[
        "active",
        "paused",
        "completed",
        "abandoned"
    ]
```

Example:

Goal:

> Build Confidant

Status:

> completed

---

## Entity Attribute Updates

Purpose:

Capture structured updates about known entities.

Illustrative shape:

```python
EntityAttributeUpdate:
    entity: str
    attribute: str
    value: str
```

Example:

```python
entity="Sarah"
attribute="role"
value="Head of Product"
```

---

# Open Architectural Question

Interpretation currently operates as a stateless per-turn function.

Future state-evolution work must resolve:

## Option A

Stateless Interpretation.

Interpretation emits updates.

Downstream systems match updates to stored objects.

---

## Option B

State-aware Interpretation.

Interpretation receives a compact view of currently tracked goals, decisions, and entities.

Interpretation performs matching directly.

No decision is proposed in this document.

The question remains intentionally deferred.

---

# Prioritization

## Priority 1 — Immediate v2 Work

* Contradictions
* Risks
* Goals
* Unknowns
* Assumptions
* Consistency checks

Success measured using the existing 30-test benchmark.

---

## Priority 2 — State Evolution

* Decision Events
* Goal Updates
* Entity Attribute Updates

Success measured through multi-turn state-evolution testing.

---

## Priority 3 — Future Architecture

* State-aware Interpretation
* Object references
* Entity identity resolution
* Goal identity resolution
* Decision identity resolution

---

# Success Criteria

Interpretation v2 should improve:

* Goal extraction
* Unknown extraction
* Assumption extraction
* Contradiction detection
* Risk detection
* State consistency

while preserving:

* Sparse-by-default behavior
* Evidence-first reasoning
* Low hallucination rates
* Strong epistemic separation

The objective is not exhaustive extraction.

The objective is truthful, complete extraction.
