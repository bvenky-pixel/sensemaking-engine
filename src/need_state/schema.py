"""
Need State Inference v1 schema -- the vision doc's Layer 7 (see
engine/specs/architecture-roadmap-v1.md), scoped to a small, closed
enumeration rather than the vision's fuller scored need-state vector.

Only three concrete needs plus a "general" fallback: `decision` (an open
Decision genuinely being weighed), `accountability` (a Goal or Decision
that has stalled -- same signal Commit mode and Judgment's own
stagnation_notes already use), and `reflection` (a Goal exists to weigh
the situation against, but nothing more specific is detectable). These
three names are the only need categories the founder's vision doc
actually names in the context of Retrieval ("Decision Retrieval,
Accountability Retrieval, Reflection Retrieval" -- see
engine/decisions.md "Retrieval"), not an invented larger taxonomy.
"""

from __future__ import annotations

from typing import Literal

NeedState = Literal["decision", "accountability", "reflection", "general"]
