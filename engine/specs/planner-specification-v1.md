Planner Specification v1

Purpose

Planner translates understanding into conversational intent.

It determines what the conversation should accomplish next based on the current WorldState and Judgment.

Planner does not generate natural language.

Planner does not provide advice.

Planner does not make decisions on behalf of the user.

Planner exists to identify the highest-value conversational objective that moves the user closer to resolution while preserving the user's agency.

---

Design Philosophy

Confidant separates cognition into distinct stages.

Interpretation answers:

«What did the user communicate?»

WorldState answers:

«What do we know?»

Judgment answers:

«What does it mean?»

Planner answers:

«What should this conversation accomplish next?»

Response Generation answers:

«How should that be communicated?»

Planner never performs the responsibilities of any other cognitive stage.

---

Core Principles

1. Planner Optimizes for Resolution

Planner's primary objective is to identify:

«What is currently preventing resolution?»

Resolution does not necessarily mean solving the user's external problem.

It means helping the user move one meaningful step closer to clarity, understanding, or action.

---

2. User Agency is Absolute

Planner never replaces the user's judgment.

Planner may:

- identify risks
- identify missing information
- recommend exploration
- suggest reflection

Planner must never:

- decide for the user
- manipulate the user
- force a direction

If the user clearly chooses a path despite identified risks, Planner supports that choice while continuing to surface relevant considerations.

Agency always belongs to the user.

---

3. Planner Plans Conversations

Planner does not plan lives.

Its responsibility ends at determining the next conversational objective.

External actions belong to the user.

Future agentic capabilities may execute user-approved actions, but those are outside Planner's responsibility.

---

4. Multi-turn Thinking

Planner reasons across the trajectory of the conversation.

It asks:

«Where should this conversation ultimately go?»

It then selects the highest-priority next objective toward that destination.

Planner does not attempt to accomplish the entire trajectory in one response.

---

5. Grounded Planning

Every recommendation must be supported by:

- WorldState
- Judgment

Planner never introduces new facts or interpretations.

---

Inputs

Planner consumes:

- WorldState
- Judgment

Planner never consumes:

- raw conversation
- Interpretation
- previous prompts

---

Outputs

class Planner:

    primary_objective: str

    rationale: str

    conversational_strategy: str

    resolution_blocker: str

    priority_topics: List[str]

    questions_to_explore: List[str]

    assumptions_to_test: List[str]

    planning_constraints: List[str]

    desired_outcome: str

    temporal_horizon: str

    confidence: float

---

Field Definitions

primary_objective

The single most valuable conversational objective.

Exactly one objective should be selected.

Examples:

- Clarify uncertainty
- Explore motivations
- Support decision making
- Review progress
- Reflect emotions
- Build understanding
- Validate assumptions

---

rationale

Why this objective was selected.

Must explicitly reference Judgment.

---

conversational_strategy

How the conversation should proceed.

Examples:

- Ask exploratory questions
- Summarize understanding
- Compare alternatives
- Reflect emotions
- Challenge assumptions
- Explore trade-offs
- Validate understanding

This is conversational intent, not generated language.

---

resolution_blocker

The primary factor preventing progress.

Examples:

- Missing information
- Unresolved uncertainty
- Conflicting priorities
- Emotional overload
- External dependency
- Waiting for an event
- Lack of decision criteria

This field represents the central obstacle Planner is attempting to reduce.

---

priority_topics

Topics most valuable to discuss next.

Planner should prioritize only the highest-impact topics.

---

questions_to_explore

Internal planning questions.

These are not necessarily asked directly to the user.

They represent information Planner believes would reduce uncertainty.

---

assumptions_to_test

Beliefs that deserve further examination.

Typically derived from Judgment assumptions or inferred reasoning.

---

planning_constraints

Constraints governing execution.

Examples:

- Preserve user agency.
- Avoid overwhelming the user.
- Focus on one unresolved issue.
- Do not reopen resolved decisions.
- Maintain conversational momentum.

These constrain the Response Generator rather than the user.

Added 2026-07-10 (see engine/decisions.md): whenever a WorldState Fact or
Claim reflects the user's own explicit instruction about HOW they want
to be responded to (e.g. "don't ask me questions," "keep it brief"),
that instruction MUST be translated into its own literal constraint here
(e.g. "no direct questions in the response") -- not left implicit in
conversational_strategy alone, since the Response Generator never sees
raw WorldState facts, only this list.

---

desired_outcome

The desired conversational outcome.

Examples:

- User identifies the next action.
- User understands the primary blocker.
- User distinguishes facts from assumptions.
- User gains clarity about priorities.
- User defines decision criteria.

Planner optimizes for conversational progress, not external success.

---

temporal_horizon

The time horizon of the current objective.

Suggested values:

- Immediate
- Near-term
- Long-term

Planner should recognize when progress depends on future events rather than immediate action.

---

confidence

Planner's confidence that this conversational plan is appropriate given the current WorldState and Judgment.

Confidence reflects the completeness and reliability of available evidence, not the model's subjective certainty.

---

Non-Goals

Planner must never:

- generate natural language
- provide emotional support
- persuade the user
- predict future events
- diagnose
- invent facts
- override user intent

---

Relationship to Response Generation

Planner produces intent.

Response Generation produces communication.

Planner decides:

«What should happen?»

Response Generation decides:

«How should it be expressed?»

Maintaining this separation allows conversational style, tone, and language generation to evolve independently from cognitive planning.

---

Design Philosophy Summary

Planner exists to bridge reasoning and communication.

It transforms Judgment into a structured conversational plan that:

- identifies what is blocking progress,
- determines the highest-value next conversational objective,
- preserves user agency,
- plans across multiple turns,
- and guides the conversation toward greater clarity and meaningful action.

Its purpose is not to solve the user's problems.

Its purpose is to help the user solve their own.
