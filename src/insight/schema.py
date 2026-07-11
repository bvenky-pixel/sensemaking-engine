"""
Insight schema -- cross-session theme detection (see
engine/decisions.md "Major update").

Implements the semantic-clustering piece Learning Phase 1's own
docstring (src/learning/engine.py) explicitly named as needing
infrastructure that "does not exist yet": recurring qualitative themes
across a person's separate sessions, as opposed to Learning Phase 1's
mechanical, non-LLM behavioral-event counting within one session.

Unlike Learning Phase 1's Pattern, this genuinely needs an LLM call --
detecting that two differently-worded sessions describe the same
underlying pattern (e.g. "waiting on my manager's approval" and "stuck
until my co-founder decides") is language understanding, not counting.
Same "one call, one schema" discipline as every other LLM-calling stage
(Interpretation/Judgment/Planner/Response), including the same grounding
discipline: a theme must be evidenced by specific session content
actually given to it, never invented.
"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

# Honest, currently-uncalibrated first guess (same style as every other
# threshold in this codebase, e.g. src/learning/engine.py's MIN_EVIDENCE,
# src/judgment/engine.py's STAGNATION_TURN_THRESHOLD) -- lower than
# Learning Phase 1's MIN_EVIDENCE=3 because sessions are few and rich (one
# real conversation each) rather than many and small (individual
# behavioral events).
MIN_EVIDENCE_SESSIONS = 2

# Caps how many sessions' worth of text get sent in one prompt as session
# count grows over time -- most-recently-updated sessions win. Also an
# honest first guess, not empirically tuned.
MAX_SESSIONS_FOR_INSIGHT = 30


class Insight(BaseModel):
    """One detected cross-session theme. `evidence_session_ids` must
    reference real session ids actually given to the engine -- see
    engine.py's post-call filtering, which never trusts the model's own
    ids uncritically, the same discipline as Interpretation's engine-level
    grounding filters."""

    theme: str
    detail: str
    evidence_session_ids: List[str] = Field(default_factory=list)


class InsightBatch(BaseModel):
    insights: List[Insight] = Field(default_factory=list)
