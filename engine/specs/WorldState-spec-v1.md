# WorldState Specification v1

## Purpose

**WorldState** is the canonical representation of everything Confidant
currently knows about the user's world.

It is **persistent**, **incrementally updated**, and **independent of
any single message**.

Every conversation turn produces a new Interpretation.

Every Interpretation updates the WorldState.

Judgment, Planner, and future reasoning engines operate exclusively over
the WorldState rather than raw conversation history.

------------------------------------------------------------------------

# Design Principles

## 1. WorldState represents knowledge, not language.

Interpretation extracts meaning from one message.

WorldState accumulates meaning across many messages.

## 2. WorldState only grows more accurate.

New interpretations should refine existing knowledge rather than
replacing it.

Knowledge evolves. It is never forgotten.

## 3. Nothing is silently deleted.

If knowledge becomes outdated: - Mark it superseded - Mark it resolved -
Mark it retracted

Historical state remains available.

## 4. WorldState minimizes reasoning.

Its responsibility is to maintain an accurate model, not draw
conclusions.

Judgment performs reasoning.

## 5. Every field has merge semantics.

No field is overwritten blindly.

Each field defines exactly how new information updates existing
knowledge.

------------------------------------------------------------------------

# Architecture

``` text
User Message
      │
      ▼
Interpretation
      │
      ▼
State Builder
      │
      ▼
WorldState
      │
      ▼
Judgment
      │
      ▼
Planner
      │
      ▼
Response
```

------------------------------------------------------------------------

# Core Structure

## Facts

Observations believed to be true.

Examples: - Boss denied transfer. - User works at Google. - User lives
in Mumbai.

Status: - Active - Superseded - Retracted

**Merge rule:** Update with newer evidence while preserving historical
versions.

## Claims

Statements made by the user that may not be objectively verified.

Examples: - Boss is toxic. - HR doesn't care. - The market is terrible.

**Merge rule:** Merge identical claims, preserve revisions, mark
retractions.

## Goals

Desired future states.

Lifecycle: - Active - Paused - Completed - Abandoned

**Merge rule:** Never replace. Update lifecycle only.

## Open Decisions

Lifecycle: - Open - Resolved - Expired

**Merge rule:** Track until resolved. Never erase history.

## Open Unknowns

Missing information recognized by the system.

**Merge rule:** Remove only when answered. Resolved unknowns become
facts.

## Entities

Persistent people, organizations, and important objects.

Each entity accumulates: - Name - Type - Known attributes -
Relationships

**Merge rule:** Enrich existing entities. Never duplicate.

------------------------------------------------------------------------

# Cross-cutting Sections

## Emotional History

Maintain chronological emotional history to enable trend analysis.

## Timeline

Append-only chronological record of important events.

## Conversation Summary

Compressed representation of the current WorldState.

Regenerated periodically rather than every turn.

## Preferences

Stable user preferences.

Updated only with high confidence.

## Projects

Long-running efforts that own related goals, facts, decisions, and
timeline entries.

------------------------------------------------------------------------

# Merge Policy

  Section             Merge Strategy
  ------------------- --------------------------------------------
  Facts               Update with newer evidence, retain history
  Claims              Merge duplicates, preserve revisions
  Goals               Update lifecycle only
  Decisions           Track until resolved
  Unknowns            Remove only when answered
  Entities            Enrich existing entities
  Timeline            Append only
  Emotional History   Append only
  Preferences         High-confidence updates only
  Projects            Merge into existing project

------------------------------------------------------------------------

# State Builder Responsibilities

Given: - Current WorldState - Latest Interpretation

Produce: - Updated WorldState

The State Builder must: - Merge knowledge - Resolve contradictions -
Update lifecycles - Preserve history - Remove resolved unknowns - Enrich
entities

The State Builder must **not**: - Give advice - Explain - Judge - Plan -
Infer deep psychological conclusions

------------------------------------------------------------------------

# WorldState Philosophy

-   **Interpretation:** What does this message mean?
-   **State Builder:** How does this change what I know?
-   **WorldState:** What is my current model of the user's world?
-   **Judgment:** Given that model, what conclusions can I draw?
-   **Planner:** What should happen next?
-   **Response:** How do I communicate that?

------------------------------------------------------------------------

# Provenance

**IMPLEMENTED 2026-07-10** (see engine/decisions.md "WorldState
provenance -- trajectory prerequisite") -- `source`/`first_seen`/
`last_updated` and turn numbering (`WorldState.turn_count`) below are
real, not aspirational. `supporting_evidence` (a list of every turn that
touched an item) is deliberately NOT implemented -- no motivating use
case yet, since it would require bookkeeping on every reaffirmation, not
just creation/status-change. The worked example below is kept as
originally written for continuity, but the actual `Provenance` model
(`src/state/world_state.py`) has only `source`/`first_seen`/
`last_updated` -- treat `supporting_evidence` in the example as future
work, not current shape.

Every durable piece of knowledge should be traceable to the conversation
that created or updated it.

Example:

``` python
Fact(
    content="Boss denied transfer",
    status="active",
    source="interpretation",
    first_seen=12,
    last_updated=18,
    supporting_evidence=[12, 18]
)
```

Provenance enables explainability, debugging, and trustworthy long-term
memory.
