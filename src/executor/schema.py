"""
ClarityBrief schema -- Executor's first artifact type.

Implements engine/specs/system-architecture-v2-specification.md's
Executor section: a persistent artifact, consumed OUTSIDE the live
conversational turn (Response Generator's exclusive territory), built
from a completed Sensemaking Engine pass via a FIXED, design-time
template -- not a new decision made per instance. See
src/executor/engine.py's build_clarity_brief for the exact field mapping
and why each choice is a reorganization of existing content, never a new
judgment call.

No prompt.py in this package, deliberately: unlike every Sensemaking
Engine component, Executor makes no LLM call at all for this artifact.
A Clarity Brief's whole point is reorganizing already-decided content,
so it's built with plain, deterministic field mapping -- the same kind
of thing engine/state_inspector.py's render() already does for WorldState,
just producing a shareable document instead of a debug printout.
"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class ClarityBrief(BaseModel):
    situation: str
    key_insights: List[str] = Field(default_factory=list)
    current_direction: str
    remaining_unknowns: List[str] = Field(default_factory=list)
    decisions: List[str] = Field(default_factory=list)
