# Interpretation v2 — Design Specification

**Status:** SPECIFICATION (frozen for implementation)

**Date:** 2026-07-08

**Version:** 2.0

---

## Table of Contents

1. [Overview](#overview)
2. [Problem Statement](#problem-statement)
3. [Design Goals](#design-goals)
4. [Schema](#schema)
5. [Extraction Rules](#extraction-rules)
6. [Prompt Guidance](#prompt-guidance)
7. [Consistency Invariants](#consistency-invariants)
8. [Risk Mitigation](#risk-mitigation)
9. [Validation Plan](#validation-plan)
10. [Implementation Phases](#implementation-phases)
11. [Deferred Work](#deferred-work)

---

## Overview

Interpretation v2 improves extraction completeness while preserving evidence-first reasoning and low hallucination rates.

**Core insight:** v0.9 understands more than it records. The primary failure mode is omission, not hallucination.

**Scope:** Domain A (understanding quality) only. Domain B (state evolution) is deferred.

**Success criterion:** Improve goal, unknown, assumption, contradiction, and risk extraction while maintaining sparse-by-default behavior and epistemic discipline.

---

## Problem Statement

### Benchmark Findings

Evaluation of 30 benchmark scenarios revealed:

- Goals frequently empty despite clear evidence of desired outcomes
- Unknowns frequently empty despite requires_clarification=true
- Assumptions extraction overly conservative
- Recurring missed tensions and unidentified downside exposure
- Downstream behavior requests clarification that interpretation didn't surface

### Root Cause

Not hallucination. The model identifies meaningful structure but fails to record it consistently.

---

## Design Goals

Interpretation v2 should:

1. **Preserve** sparse-by-default behavior
2. **Preserve** evidence-first reasoning  
3. **Preserve** low hallucination rates
4. **Improve** goal extraction
5. **Improve** unknown extraction
6. **Improve** assumption extraction
7. **Introduce** contradiction detection
8. **Introduce** risk identification
9. **Improve** consistency between extracted state and downstream behavior

---

## Schema

### Interpretation v2 Object

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
    goals: List[str]  # Improved: inferred goals allowed
    decision_options: List[str]
    assumptions: List[str]  # Improved: less conservative
    contradictions: List[str]  # NEW
    risks: List[str]  # NEW
    inferences: List[Inference]
    unknowns: List[str]  # Improved: consistency with clarification
    biases: List[Bias]
    entities: List[str]
    clarity_score: float
    requires_clarification: bool
```

### New Field: Contradictions

**Purpose:** Capture tensions, inconsistencies, and conflicting realities.

**Definition:** A contradiction does not require formal logical inconsistency. It captures meaningful tension present in the user's description.

**Schema:**
```python
contradictions: List[str]
```

**Default:** `[]`

### New Field: Risks

**Purpose:** Capture plausible negative outcomes connected to the current situation.

**Definition:** Risks are not predictions. Risks identify meaningful downside exposure grounded in available facts.

**Schema:**
```python
risks: List[str]
```

**Default:** `[]`

---

## Extraction Rules

### Contradictions

**Required Criteria:**

1. Both sides of the tension must be present or strongly implied in the user's message
2. Both sides must be cited—evidence grounding is mandatory
3. Describe the tension, not explain it
4. Do not assign blame or speculate about motives
5. Do not resolve the tension

**Linguistic Patterns:**

- "but" / "however" / "though" — explicit contrast markers
- "love...but..." — emotional conflict
- "want...need..." — competing values
- "they say...but I..." — external feedback vs. internal reality

**Examples:**

```
User: "My manager says I'm doing great, but I was passed over for promotion."
Contradiction: "Positive performance feedback conflicts with promotion outcome."

User: "I love this relationship, but I think I need to leave."
Contradiction: "Emotional attachment conflicts with desire to leave."

User: "I want freedom, but I need financial stability."
Contradiction: "Desire for freedom conflicts with need for stability."
```

**Non-Examples (do not extract):**

```
User: "I'm scared of flying but I just booked a trip."
❌ NOT: "Fear of flying conflicts with desire to travel."
   Reason: People take flights despite fear. Normal, not tension.

User: "I love my job but it's exhausting."
❌ NOT: "Love of work conflicts with exhaustion."
   Reason: These are compatible. Not contradictory.

User: "My partner is critical sometimes."
❌ NOT: "They're caring but also critical."
   Reason: Inference, not grounded in text.
```

### Risks

**Required Criteria:**

1. Risk must emerge directly from facts already present
2. Risk must remain grounded in available evidence
3. Avoid worst-case scenarios or catastrophizing
4. Avoid advice or planning language
5. Avoid speculation beyond the immediate situation

**Linguistic Patterns:**

- Conditionals: "If I do X..." — introduces potential risk
- Lack of safety nets: "without...", "no backup..."
- Stated concerns: "I'm worried about..."
- Consequences: "that would result in..."

**Examples:**

```
User: "I'm considering quitting without another offer."
Risks:
- Loss of income
- Extended unemployment

User: "My spouse is talking about divorce."
Risks:
- Relationship dissolution

User: "I'm thinking of taking on significant debt."
Risks:
- Financial strain
```

**Non-Examples (do not extract):**

```
User: "I'm changing jobs."
❌ NOT: "I might become homeless."
   Reason: Disproportionate leap from facts.

User: "I got the job!"
❌ NOT: "Imposter syndrome might develop."
   Reason: Not grounded in user's description.
```

### Goals (Improved)

**V0.9 Problem:** Goals required explicit phrases ("I want", "My goal is"). Desired outcomes were frequently missed.

**V2 Rule:** Goals do not require explicit phrases. Desired outcomes may be inferred when strongly supported by context.

**Licensed Inference Patterns:**

- "trying to..." → goal is the object of "trying"
- "working toward..." → goal is the object
- "attempting..." → goal is the object
- "struggling with..." → goal is to improve/resolve the struggle
- "frustrated by not..." → goal is to achieve what's being denied

**Note:** Do NOT use "considering..." to infer goals. "Considering" signals decision options being evaluated, not desired outcomes. Collapsing consideration into goals corrupts the distinction between decision_options and goals.

**Examples:**

```
User: "I've been trying to move into product management."
Goal: "Move into product management."

User: "My partner says we keep having the same argument."
Goal: "Improve relationship conflict."

User: "I'm struggling to get my startup off the ground."
Goal: "Successfully launch the startup."
```

**Non-Examples:**

```
User: "I work in engineering."
❌ NOT: "Become an engineering manager."
   No linguistic signal of aspiration or effort.

User: "What if I wanted to learn French?"
❌ NOT: "Learn French."
   Hypothetical, not real engagement.
```

### Assumptions (Improved)

**V0.9 Problem:** Prompt guidance "In most turns assumptions=[]" biased toward under-extraction.

**V2 Rule:** Extract assumptions when the user draws a conclusion not directly supported by stated facts.

**Required Criteria:**

1. The user must draw an explicit conclusion or judgment
2. That conclusion must depend on an unstated belief
3. The unstated belief must connect observation to conclusion

**Pattern:** Observation → [assumption] → Conclusion

**Examples:**

```
User: "My friend hasn't replied for three days. I think they're angry."
Assumption: "Lack of response indicates anger."
Pattern: No reply → [assumes = indicates anger] → "They're angry"

User: "I wasn't promoted. My manager must not value me."
Assumption: "Promotion outcome reflects personal value."
Pattern: No promotion → [assumes = reflects value] → "Not valued"

User: "My co-founder disagreed with me. He clearly doesn't trust me."
Assumption: "Disagreement implies lack of trust."
Pattern: Disagreement → [assumes = implies distrust] → "No trust"
```

**Non-Examples:**

```
User: "My friend is quiet today."
❌ NOT: "Assume they're upset."
   No conclusion drawn by user. Unknowns might be appropriate.

User: "I got the promotion!"
❌ NOT: "Assume I'm capable."
   Conclusion doesn't depend on unstated belief.
```

### Unknowns (Improved)

**V0.9 Problem:** Unknowns frequently remained empty despite requires_clarification=true.

**V2 Rule:** Unknowns should identify information gaps that materially limit understanding.

**Consistency Rule:** If requires_clarification=true, unknowns should usually be non-empty.

**Required Criteria:**

1. Unknown must answer: "What information would help explain the situation?"
2. Unknowns are not coaching questions
3. Unknowns are not planning questions
4. Unknown must be grounded in evidence gap, not speculation

**Examples:**

```
User: "I feel stuck."
Unknowns:
- What area of life feels stuck?
- How long has this felt true?

User: "My boss keeps avoiding the conversation."
Unknowns:
- Has the boss explained the reason for avoiding the discussion?
```

**Consistency Exception:**

If requires_clarification=true but no specific information gap is identifiable, unknowns may remain empty:

```
User: "I don't know what to do."
requires_clarification: true
unknowns: []
Justification: User's confusion is clear but no specific gap is identifiable.
```

---

## Prompt Guidance

### Section: CONTRADICTIONS

Insert after ASSUMPTIONS section.

```
CONTRADICTIONS

Purpose:
Capture tensions, inconsistencies, or conflicting realities in the user's message.
A contradiction does not require formal logical inconsistency.
Record meaningful tension.

Rules:
- Both sides of the tension must be present in the user's message
- Cite evidence for both sides
- Describe the tension, do not explain it
- Do not resolve the tension
- Do not assign blame or speculate about motives
- Empty list is correct when no meaningful tension exists

Examples:

User: "My manager says I'm doing great, but I was passed over for promotion."
GOOD: "Positive performance feedback conflicts with promotion outcome."

User: "I love this relationship, but I think I need to leave."
GOOD: "Emotional attachment conflicts with desire to leave."

Do NOT extract:
User: "I'm scared of flying but I booked a trip."
BAD: "Fear of flying conflicts with desire to travel."
Reason: These are compatible. Not a real tension.

Output format: List of strings
Default: []
```

### Section: RISKS

Insert after CONTRADICTIONS section.

```
RISKS

Purpose:
Capture plausible negative outcomes directly connected to the current situation.
Risks are not predictions. Risks are not catastrophizing.
Risks identify meaningful downside exposure.

Rules:
- Risk must emerge from facts already stated
- Risk must be grounded in available evidence
- Avoid worst-case scenarios
- Avoid advice or planning language
- Avoid speculation beyond immediate situation
- Empty list is correct when no meaningful risk is present

Examples:

User: "I'm thinking of quitting without another offer."
GOOD:
- Loss of income
- Extended unemployment

User: "My spouse is talking about divorce."
GOOD:
- Relationship dissolution

Do NOT extract:
User: "I'm changing jobs."
BAD: "I might become homeless."
Reason: Disproportionate leap from facts.

Output format: List of strings
Default: []
```

### Section: GOALS (Revised)

Revise existing GOALS section guidance:

```
GOALS — Revised

Problem Observed:
Goals frequently remained empty despite clear evidence of desired outcomes.

Guidance:
Goals do not require explicit phrases such as "I want", "My goal is", "I need".
Desired outcomes may be inferred when strongly supported by context.

Licensed inference patterns:
- "trying to X" → X is a goal
- "working toward X" → X is a goal  
- "attempting X" → X is a goal
- "struggling with X" → goal is to improve/resolve X
- "frustrated by not X" → goal is to achieve X

CAUTION: Do not use "considering" to infer goals. "Considering" signals decision
options being evaluated, not desired outcomes. Example: "I'm considering quitting"
is a decision option (quit vs. stay), not a goal (quit job). Collapsing these
concepts corrupts benchmark validation.

Examples:

User: "I've been trying to move into product management."
GOOD: "Move into product management."

User: "My partner says we keep having the same argument."
GOOD: "Improve relationship conflict."

Do NOT extract:
User: "I work in engineering."
BAD: "Become an engineering manager."
Reason: No linguistic signal of aspiration.

User: "What if I wanted to learn French?"
BAD: "Learn French."
Reason: Hypothetical, not real engagement.

Output format: List of strings
Default: []
```

### Section: UNKNOWNS (Revised)

Revise existing UNKNOWNS section guidance:

```
UNKNOWNS — Revised

Problem Observed:
Unknowns frequently remained empty even when requires_clarification=true.

Guidance:
Unknowns should identify information gaps that materially limit understanding.
Unknowns are not coaching questions.
Unknowns are not planning questions.

Unknowns answer: "What information is missing that would help explain the situation?"

Consistency Rule:
If requires_clarification=true, unknowns should usually be non-empty.
Exception: If no specific information gap is identifiable, unknowns may remain empty.

Examples:

User: "I feel stuck."
GOOD:
- What area of life feels stuck?
- How long has this felt true?

User: "My boss keeps avoiding the conversation."
GOOD:
- Has the boss explained the reason?

User: "I don't know what to do."
requires_clarification: true
unknowns: []
Justification: Confusion is clear but no specific gap identifiable.

Output format: List of strings
Default: []
```

### Section: ASSUMPTIONS (Revised)

Revise existing ASSUMPTIONS section guidance:

```
ASSUMPTIONS — Revised

Problem Observed:
Assumption extraction was overly conservative due to guidance bias.

Guidance:
Many conversations genuinely contain no assumptions.
However, when a conclusion depends on an unstated belief, capture that belief.

Pattern to identify: Observation → [unstated belief] → Conclusion

Examples:

User: "My friend hasn't replied for three days. I think they're angry."
GOOD: "Lack of response indicates anger."
Pattern: No reply → [assumes = indicates anger] → "They're angry"

User: "I wasn't promoted. My manager must not value me."
GOOD: "Promotion outcome reflects personal value."

User: "My co-founder disagreed. He doesn't trust me."
GOOD: "Disagreement implies lack of trust."

Do NOT extract:
User: "My friend is quiet today."
BAD: "Assume they're upset."
Reason: User drew no conclusion. Unknowns might be appropriate.

Output format: List of strings
Default: []
```

### Section: FINAL CONSISTENCY REVIEW

Add before output section:

```
FINAL CONSISTENCY REVIEW

Before producing output, perform internal validation:

1. Clarification Consistency:
   If requires_clarification=true, are unknowns usually non-empty?
   (Exception: If no identifiable gap, unknowns may be empty)

2. Goal Consistency:
   If a desired outcome is clearly present, are goals usually non-empty?

3. Decision Consistency:
   If alternatives are being compared, are decision_options usually non-empty?

4. Emotional Consistency:
   If meaningful emotional content is present, are emotional_signals usually non-empty?

5. Contradiction Check:
   Is there an obvious tension that belongs in contradictions?

6. Risk Check:
   Is there meaningful downside exposure that belongs in risks?

PRIORITY RULE:
Evidence grounds all extraction. Consistency guides calibration.
If a consistency rule suggests a field should be non-empty, but that field cannot
be grounded in evidence from the user's message, leave it empty.

Do not generate content for consistency alone.
```

---

## Consistency Invariants

### Rule: Clarification Consistency

```
IF requires_clarification == true
THEN unknowns should usually be non-empty

EXCEPTION:
User's confusion is clear but no specific information gap is identifiable.
In this case, unknowns may be empty.
Justify with evidence from the message.
```

### Rule: Goal Consistency

```
IF desired outcome is clearly present
THEN goals should rarely be empty

EXAMPLES:
User: "I've been trying to..."
User: "My goal is to..."  
User: "I want to..."
User: "I'm working toward..."
```

### Rule: Decision Consistency

```
IF alternatives are being compared
THEN decision_options should rarely be empty

EXAMPLES:
User: "Should I stay or leave?"
User: "Option 1: X. Option 2: Y."
User: "I could either... or..."
```

### Rule: Emotional Consistency

```
IF meaningful emotional content is present
THEN emotional_signals should rarely be empty

EXAMPLES:
User describes feelings, reactions, emotional states
User reports emotional conflict or distress
User references relationships and relational emotion
```

### Priority Rule: Evidence Grounds Extraction

```
Evidence grounds all extraction.
Consistency rules guide calibration.

When consistency rule conflicts with evidence:
1. Can this field be grounded in evidence from the user's message?
2. If YES → Extract
3. If NO → Leave field empty

Do not generate content for consistency alone.
```

---

## Risk Mitigation

### Risk 1: Contradiction Over-Generation

**Problem:** Over-extracting contradictions that feel forced or aren't genuine tensions.

**Mitigation:**

1. **Evidence Citation:** Both sides must be cited from the message
2. **Negative Examples:** Prompt includes counter-examples of false contradictions
3. **Measurement:** Track contradiction extraction rate; flag >1.5 avg per message
4. **Validation:** For each contradiction, verify both sides are present in text

**Example Validation:**
```
User: "I love my job but it's exhausting."
Extracted contradiction: "Love of work conflicts with exhaustion."
Validation: These are compatible states. REJECT.
```

### Risk 2: Hallucination Creep in Assumptions

**Problem:** Loosening assumption guidance could increase false assumptions.

**Mitigation:**

1. **Pattern Enforcement:** Require Observation → Assumption → Conclusion chain
2. **Confidence Threshold:** Only extract when user draws explicit conclusion
3. **Measurement:** Track assumption rate vs v0.9; alert if >20% increase
4. **Validation:** Compare against benchmark; flag assumptions marked wrong

**Example Validation:**
```
User: "My friend is quiet today."
Extracted assumption: "Assume they're upset."
Validation: User drew no conclusion. REJECT.
```

### Risk 3: Goal Inference Over-Reaching

**Problem:** Inferring goals too broadly from weak signals.

**Mitigation:**

1. **Linguistic Signals:** Enumerate patterns that license inference
2. **High Confidence:** Only infer when evidence is strong
3. **Measurement:** Track goal accuracy against human judgment; flag <85%
4. **Validation:** Inferred goals must match benchmark human ratings

**Example Validation:**
```
User: "I work in engineering."
Inferred goal: "Become an engineering manager."
Validation: No signal. REJECT.
```

### Risk 4: Risk Over-Generation or Catastrophizing

**Problem:** Extracting risks that are speculative or disproportionate.

**Mitigation:**

1. **Grounding:** Risk must emerge from stated facts
2. **Proportionality:** Avoid worst-case scenarios
3. **Measurement:** Track risk false-positive rate; flag >10%
4. **Validation:** Each risk must be proportional to facts

**Example Validation:**
```
User: "I'm changing jobs."
Extracted risk: "I might become homeless."
Validation: Disproportionate. REJECT.
```

### Risk 5: Unknowns Consistency Rule Forcing Generation

**Problem:** Generating false unknowns just to satisfy consistency rule.

**Mitigation:**

1. **Priority Rule:** Evidence grounds extraction; consistency guides calibration
2. **Exception Clause:** Unknowns may remain empty if no gap is identifiable
3. **Justification:** Require explicit evidence citation
4. **Measurement:** Track false-positive unknowns; alert if >15%

**Example Validation:**
```
User: "I don't know what to do."
requires_clarification: true
unknowns: []
Validation: Confusion is clear but no specific gap identifiable. ACCEPT.
```

---

## Validation Plan

### Benchmark Validation (30 scenarios)

For each extraction type, measure:

| Extraction Type | Metric | Threshold | Action |
|-----------------|--------|-----------|--------|
| Contradictions | False-positive rate | <10% | Iterate if exceeded |
| Contradictions | Avg per message | <1.5 | Flag if exceeded |
| Risks | False-positive rate | <10% | Iterate if exceeded |
| Risks | Avg per message | <2 | Flag if exceeded |
| Goals | Accuracy vs human | >85% | Loosen if below |
| Assumptions | Rate increase vs v0.9 | <20% | Flag if exceeded |
| Unknowns | False-positive rate | <15% | Loosen rule if exceeded |

### Secondary Validation: Evidence Grounding

For each extracted item:

1. Mark evidence span in original message
2. Ask: "Is this justified by the evidence?"
3. Target: >90% clearly justified

### Consistency Validation

Measure consistency rule effectiveness:

```
For each scenario where consistency rule triggers:
- Is the rule addressing a real gap?
- Is the extraction justified?
- Rate true-positive vs false-positive
```

---

## Implementation Phases

### Phase 1: Contradictions + Risks (New Fields)

**Deliverables:**
- Prompt sections for contradictions and risks
- Negative examples for both
- Measurement plan

**Success Criteria:**
- Contradictions: <10% false-positive rate
- Risks: <10% false-positive rate  
- Neither exceeds 1.5 avg per message

**Go/No-Go Gate:** Validate against 30 runs. If false-positive >15%, iterate prompt.

### Phase 2: Goal + Unknown + Assumption Loosening

**Deliverables:**
- Revised GOALS prompt (inferred goals allowed)
- Revised UNKNOWNS prompt (consistency rule added)
- Revised ASSUMPTIONS prompt (removed under-extraction bias)

**Success Criteria:**
- Goals: >85% accuracy vs human judgment
- Assumptions: <20% increase in extraction rate vs v0.9
- Unknowns: <15% false-positive rate

**Go/No-Go Gate:** Validate against 30 runs. If accuracy <80%, iterate.

### Phase 3: Consistency Invariants

**Deliverables:**
- Prompt section: FINAL CONSISTENCY REVIEW
- Priority rule: Evidence grounds extraction

**Success Criteria:**
- Consistency rules surface real missed extractions
- No false-positive generation for consistency alone
- Overall extraction completeness improves

**Go/No-Go Gate:** Validate that consistency rules improve state completeness without increasing hallucination.

---

## Deferred Work

### Domain B: State Evolution (v2.1+)

The following are explicitly deferred from v2.0:

#### Decision Events

Track lifecycle changes to decision options.

```python
DecisionEvent:
    option: str
    event: Literal["proposed", "chosen", "rejected", "deferred"]
```

#### Goal Updates

Track lifecycle changes to goals.

```python
GoalUpdate:
    goal: str
    status: Literal["active", "paused", "completed", "abandoned"]
```

#### Entity Attribute Updates

Capture structured updates about known entities.

```python
EntityAttributeUpdate:
    entity: str
    attribute: str
    value: str
```

### Architectural Question: Stateless vs State-Aware Interpretation

Currently: Stateless (Interpretation emits updates; downstream systems match).

Future: State-aware option (Interpretation receives compact view of tracked objects).

**No decision proposed.** Defer until v2 state-evolution work begins.

---

## Explicit Non-Goals

Interpretation v2 does not change:

- Evidence-first reasoning
- Sparse-by-default philosophy
- Confidence calibration rules
- Emotional signal calibration
- Bias extraction rules
- Inference confidence rules
- Prohibition on advice
- Prohibition on invented motives

Interpretation remains an extraction layer, not a planning or coaching layer.

---

## Acceptance Criteria

Interpretation v2 is complete when:

1. ✅ Schema implementation matches specification
2. ✅ Prompt guidance implemented with examples and negative cases
3. ✅ Consistency invariants added to prompt
4. ✅ Risk mitigation strategies deployed
5. ✅ Benchmark validation run on all 30 scenarios
6. ✅ Contradictions: <10% false-positive rate
7. ✅ Risks: <10% false-positive rate
8. ✅ Goals: >85% accuracy
9. ✅ Assumptions: <20% rate increase
10. ✅ Unknowns: <15% false-positive rate
11. ✅ No hallucination rate increase
12. ✅ Evidence grounding >90%

---

**Document Version:** 1.0  
**Last Updated:** 2026-07-08  
**Status:** FROZEN FOR IMPLEMENTATION
