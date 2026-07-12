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
- Tier 1 (this round): a pure, deterministic template over WorldState's
  raw knowledge items -- zero LLM calls, same discipline as
  src/executor/engine.py::build_clarity_brief.
- Tier 2 (deferred -- see the plan file this round shipped from and its
  own "Deferred design -- Tier 2" section): LLM-synthesized statements
  (declarative uncertainty, values-level inference) that need real
  synthesis beyond raw content. The schema already accommodates it
  (UnderstandingState.tier2, tier2_grounding_signature) so adding it
  later needs no further schema migration -- tier2 simply stays empty
  until that round ships.
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
