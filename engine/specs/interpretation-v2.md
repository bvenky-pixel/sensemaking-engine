# Confidant Interpretation Engine v2 Design Brief

## Status

Draft

## Purpose

Interpretation v1 prioritized precision and epistemic discipline. Benchmark evaluation across 30 scenarios demonstrated strong resistance to hallucinated structure, but revealed recurring under-extraction of important reasoning artifacts.

Interpretation v2 retains the core epistemic philosophy of v1 while improving recall for meaningful structure that is genuinely present in the user's narrative.

The objective is not to make Interpretation more creative.

The objective is to make Interpretation more complete.

---

# Design Goals

Interpretation v2 should:

1. Preserve evidence-first reasoning.
2. Preserve sparse-by-default behavior.
3. Improve extraction of meaningful user goals.
4. Improve extraction of unknowns when clarification is required.
5. Improve extraction of assumptions when users rely on unstated beliefs.
6. Introduce contradiction detection.
7. Introduce risk identification.
8. Improve consistency between extracted state and downstream behavior.

---

# Core Philosophy

Interpretation remains a forensic analysis layer.

It does not:

* advise
* coach
* comfort
* plan
* persuade

It only extracts and organizes understanding.

The governing principle remains:

> Record what is present, not what is possible.

However, Interpretation should not under-report meaningful structure simply because it is implicit rather than explicitly labeled by the user.

---

# New Concepts

## Contradictions

### Definition

Contradictions represent tensions, inconsistencies, or seemingly conflicting realities within the user's description.

A contradiction does not require formal logical inconsistency.

The purpose is to capture situations where two pieces of information pull in opposite directions.

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

> I want more freedom, but I need financial stability.

Contradiction:

> Desire for freedom conflicts with need for stability.

### Rules

Contradictions should:

* describe the tension
* not explain the tension
* not resolve the tension
* not assign blame
* not speculate about motives

### Schema

```python
contradictions: List[str]
```

Default:

```python
[]
```

---

## Risks

### Definition

Risks represent plausible negative outcomes directly connected to the current situation.

Risks are not predictions.

Risks are not catastrophizing.

Risks identify meaningful downside exposure.

### Examples

User:

> I'm thinking of quitting without another offer.

Risks:

* Loss of income
* Extended unemployment

---

User:

> My spouse is talking about divorce.

Risks:

* Relationship dissolution

---

User:

> I am considering taking on significant debt.

Risks:

* Financial strain

### Rules

Risks should:

* emerge directly from the described situation
* remain grounded in available evidence
* avoid worst-case speculation
* avoid advice

### Schema

```python
risks: List[str]
```

Default:

```python
[]
```

---

# Existing Fields

## Goals

### Problem Observed In V1

Goals were frequently omitted despite clear evidence of desired outcomes.

### V2 Interpretation

Goals may be extracted when the desired outcome is obvious from the user's description.

Goals do not require explicit phrases such as:

* I want
* I need
* My goal is

### Examples

User:

> I've been trying to move into product management.

Goal:

> Move into product management.

---

User:

> My partner says we keep having the same argument.

Goal:

> Improve the relationship conflict.

---

# Unknowns

### Problem Observed In V1

Unknowns were often empty even when the response later asked clarification questions.

### V2 Principle

Unknowns should capture information gaps that materially limit understanding.

Unknowns are not planning questions.

Unknowns are not coaching questions.

Unknowns should answer:

> What information is missing that would help explain the current situation?

### Consistency Rule

When:

```python
requires_clarification == True
```

unknowns should rarely be empty.

---

# Assumptions

### Problem Observed In V1

Assumption extraction was overly conservative.

### Definition

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

### V2 Guidance

Many conversations genuinely contain no assumptions.

However, when a conclusion depends on an unstated belief, that belief should be captured.

---

# Consistency Invariants

Interpretation should internally self-check for consistency.

## Clarification

If:

```python
requires_clarification == True
```

then:

```python
unknowns
```

should usually contain at least one relevant gap.

---

## Decision Making

If the user is comparing alternatives:

```python
decision_options
```

should rarely be empty.

---

## Goal Detection

If a desired outcome is clearly present:

```python
goals
```

should rarely be empty.

---

## Emotional Content

If meaningful emotional content is present:

```python
emotional_signals
```

should rarely be empty.

---

# Proposed Interpretation Schema V2

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

# Success Criteria

Interpretation v2 should demonstrate measurable improvement in:

* Goal extraction
* Unknown extraction
* Assumption extraction
* Contradiction detection
* Risk detection

while preserving:

* Epistemic discipline
* Low hallucination rate
* Structured consistency
* Sparse-by-default behavior

Interpretation v2 should continue to optimize for truthful structure rather than exhaustive structure.
