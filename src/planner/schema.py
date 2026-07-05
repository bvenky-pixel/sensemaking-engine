"""
Planner schema for Confidant's conversational-planning layer.

Implements engine/specs/planner-specification-v1.md's Output section
verbatim -- eleven fields, one Pydantic model, no fields added or dropped
beyond the spec. Two typing decisions made resolving the spec's prose
into concrete types (see engine/decisions.md for the full discussion):

- `temporal_horizon` is a closed `Literal`, not a free string. The spec
  calls it "Suggested values: Immediate / Near-term / Long-term" -- a
  short, complete enumeration (unlike the other free-text fields below,
  each introduced as non-exhaustive "Examples:"). This matches the
  precedent set by Interpretation's `urgency`/`impact_domains` fields:
  when the spec gives a genuinely closed set, "typed over prompted" wins.
- `primary_objective`, `conversational_strategy`, `resolution_blocker`,
  and `desired_outcome` stay plain `str`, despite each having a worked
  "Examples:" list in the spec. Those lists read as illustrative, not
  exhaustive ("Examples:", not "Suggested values:" or "one of:") --
  matches how Judgment's `primary_problem`/`primary_goal`/`current_focus`
  are plain strings guided by prompt examples rather than forced into an
  enum the spec never actually closes.
"""

from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, Field

TemporalHorizon = Literal["immediate", "near_term", "long_term"]


class Planner(BaseModel):
    primary_objective: str
    rationale: str
    conversational_strategy: str
    resolution_blocker: str

    priority_topics: List[str] = Field(default_factory=list)
    questions_to_explore: List[str] = Field(default_factory=list)
    assumptions_to_test: List[str] = Field(default_factory=list)
    planning_constraints: List[str] = Field(default_factory=list)

    desired_outcome: str
    temporal_horizon: TemporalHorizon

    confidence: float = Field(ge=0.0, le=1.0)
