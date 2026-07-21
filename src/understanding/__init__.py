"""
Understanding -- the stable, human-readable layer rendered from a
Journey's own WorldState (see engine/decisions.md "Understanding layer
-- Journey-scoped identity").

Question answered: given everything WorldState already knows about this
Journey, what does a settled, non-flickering statement of that
understanding look like -- one that doesn't reword itself every turn the
way Judgment's freshly-synthesized prose does, because it's derived from
WorldState's own now-id-bearing Fact/Claim/Goal/Decision objects rather
than re-synthesized by an LLM call each time.

Two tiers, by design (see src/understanding/schema.py):
- Tier 1: a pure, deterministic template over WorldState's raw
  knowledge items -- zero LLM calls, same discipline as
  src/executor/engine.py::build_clarity_brief. See
  src/understanding/engine.py.
- Tier 2 (shipped -- see engine/decisions.md "Tier 2 design" and
  engine/specs/understanding-specification-v1.md): LLM-synthesized
  statements that connect multiple Tier 1 candidates into a genuine
  synthesis none of them says alone. Conditional (most turns skip the
  LLM call -- see should_recompute_tier2) and non-blocking (any
  failure leaves WorldState unchanged rather than aborting the turn).
  See src/understanding/tier2_engine.py.
"""

from __future__ import annotations

from src.understanding.schema import (
    UnderstandingState,
    UnderstandingStatement,
    UnderstandingStatementKind,
    UnderstandingTier,
)

# Deliberately NOT re-exporting build_tier1_statements here (import it
# directly from src.understanding.engine instead): src/state/world_state.py
# imports UnderstandingState from src.understanding.schema for the new
# WorldState.understanding field, and importing ANY submodule of a
# package first runs that package's __init__.py -- if this file also
# imported engine.py (which takes a WorldState argument and so must
# import src.state.world_state), that would be a real circular import
# (world_state.py -> this __init__.py -> engine.py -> world_state.py,
# mid-load). schema.py has no WorldState dependency, so re-exporting only
# schema.py's names here is safe.
__all__ = [
    "UnderstandingState",
    "UnderstandingStatement",
    "UnderstandingStatementKind",
    "UnderstandingTier",
]
