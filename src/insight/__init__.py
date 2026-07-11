"""
Insight -- cross-session theme detection (see engine/decisions.md
"Major update").

Question answered: «Do a person's separate sessions describe a
recurring pattern?» -- the semantic-clustering piece Learning Phase 1's
own docstring named as needing infrastructure that didn't exist yet
(src/learning/engine.py). Unlike Learning Phase 1's mechanical,
non-LLM behavioral-event counting, this genuinely needs an LLM call for
real language understanding across differently-worded sessions.

Operates asynchronously, never inside a live conversation turn, same
boundary Learning already established: src/insight/engine.py::run_insight_detection
is only ever called by scripts/run_insight_detection.py, a standalone
offline script -- nothing in the live request path (src/api/server.py)
calls it.
"""

from __future__ import annotations

from src.insight.engine import InsightEngineError, run_insight_detection
from src.insight.schema import MAX_SESSIONS_FOR_INSIGHT, MIN_EVIDENCE_SESSIONS, Insight, InsightBatch

__all__ = [
    "Insight",
    "InsightBatch",
    "InsightEngineError",
    "run_insight_detection",
    "MIN_EVIDENCE_SESSIONS",
    "MAX_SESSIONS_FOR_INSIGHT",
]
