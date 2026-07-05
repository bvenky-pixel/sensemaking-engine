Response Generator Specification v1

Purpose

Response Generator is the presentation layer of Confidant's cognitive architecture.

It translates the outputs of WorldState, Judgment, and Planner into natural conversation.

Response Generator performs expression, not cognition.

It never reasons, plans, or updates the system's understanding.

It is the voice of Confidant.

---

Design Philosophy

Confidant deliberately separates thinking from communication.

Interpretation determines:

«What did the user communicate?»

WorldState determines:

«What do we know?»

Judgment determines:

«What does it mean?»

Planner determines:

«What should this conversation accomplish next?»

Response Generator determines:

«How should that conversational intent be expressed?»

Every cognitive decision has already been made before Response Generator executes.

---

Core Principle

Faithful Execution

Response Generator faithfully executes the conversational plan produced by Planner.

It must never:

- reinterpret the conversation
- reprioritize issues
- introduce new reasoning
- generate new insights
- override Planner's intent

If Planner determines the conversation should clarify uncertainty,

Response Generator clarifies uncertainty.

If Planner determines the conversation should summarize progress,

Response Generator summarizes progress.

Its role is execution, not decision-making.

---

Inputs

Response Generator consumes:

- WorldState
- Judgment
- Planner

Planner is the primary source of conversational intent.

Judgment provides supporting context.

WorldState provides factual grounding.

Response Generator never consumes:

- raw conversation
- Interpretation

---

Responsibilities

Response Generator is responsible for only four things.

1. Expression

Choose natural language that faithfully communicates Planner's intent.

---

2. Structure

Organize the response into a coherent conversational flow.

Examples include:

- acknowledgement
- explanation
- exploration
- summary
- question
- conclusion

Structure supports communication.

It never changes the underlying conversational objective.

---

3. Tone

Express the response using language that is:

- calm
- respectful
- clear
- intellectually honest
- emotionally appropriate

Tone may adapt to the conversation.

Meaning must never.

---

4. Readability

Present information in a way that is easy for the user to understand.

Response Generator may improve:

- sentence flow
- transitions
- paragraph organization
- clarity

It must never simplify by removing important meaning.

---

Grounding

Every statement must be grounded in:

- WorldState
- Judgment
- Planner

Response Generator must never introduce:

- new facts
- new assumptions
- new interpretations
- new risks
- new opportunities
- new objectives

---

Handling Uncertainty

If Judgment is uncertain,

the response should communicate uncertainty naturally.

If Unknowns remain unresolved,

the response should acknowledge them rather than fabricate certainty.

Response Generator should reflect the confidence of upstream cognition.

It must never exaggerate certainty.

---

Planner Relationship

Planner owns conversational intent.

Planner determines:

- primary objective
- conversational strategy
- resolution blocker
- priority topics
- questions to explore
- assumptions to test
- planning constraints
- desired outcome

Response Generator simply renders those decisions into natural conversation.

It must faithfully execute both Planner's intent and Planner's constraints.

---

Output

class Response:

    response_text: str

    confidence: float

The response is the only artifact presented to the user.

All cognitive artifacts remain internal.

---

Non-Goals

Response Generator must never:

- perform reasoning
- update WorldState
- modify Judgment
- modify Planner
- infer new motivations
- invent evidence
- persuade the user
- make decisions on behalf of the user
- override user agency

---

Design Philosophy Summary

Response Generator is the voice of Confidant.

Its purpose is not to think.

Its purpose is not to plan.

Its purpose is not to decide.

Its purpose is to faithfully translate the cognitive work already completed by Interpretation, WorldState, Judgment, and Planner into clear, natural conversation.

Confidant's intelligence resides in its cognitive architecture.

Response Generator simply gives that intelligence a human voice.
