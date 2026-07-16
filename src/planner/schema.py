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

`active_lens` (added for Synthesis, see engine/decisions.md "Synthesis"
and src/orchestrator/modes.py's "adaptive" mode) is NOT part of the
original v1 spec -- added the same way Judgment's `has_knowledge_correction`/
`has_risk_signal`/`stagnation_notes` were added on top of its own v2
spec, once a real capability needed a field the original spec never
anticipated. Only ever meaningfully set when the Journey is in Adaptive
mode (see src/planner/prompt.py's FIELD DEFINITIONS); every other mode
-- including no mode at all -- leaves it `None`, since those modes
already fix the lens by construction and have nothing to choose.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from src.orchestrator.modes import ConcreteLens

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

    active_lens: Optional[ConcreteLens] = None
