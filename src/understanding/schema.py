"""
Understanding schema -- see src/understanding/__init__.py for the
package-level design rationale.

UnderstandingState lives directly on WorldState (src/state/world_state.py),
not a separate DB table -- it's Journey-scoped by construction (same
decision as everything else this round), so it round-trips for free
through the existing save_turn_result/load_state path with zero new
src/api/db.py plumbing, unlike src/insight/'s insights/insight_sessions
tables, which need their own table specifically because they're
cross-session aggregates with no single owning WorldState.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

UnderstandingStatementKind = Literal["fact", "claim", "goal", "decision", "uncertainty", "inference"]
UnderstandingTier = Literal[1, 2]


class UnderstandingStatement(BaseModel):
    """
    One line of Understanding, either tier.

    `id` is NOT a default_factory -- the caller assigns it explicitly.
    Tier 1 (src/understanding/engine.py::build_tier1_statements) derives
    a DETERMINISTIC id from its grounding WorldState item
    (f"tier1:{kind}:{item.id}"), specifically so re-rendering an
    unchanged WorldState is byte-identical, including id -- a random
    default here would silently break that stability guarantee, which is
    the entire point of this layer existing. Tier 2 (deferred) would
    assign a fresh id at synthesis time instead, since a Tier 2
    statement's own identity is the cached-until-regenerated text itself,
    not a 1:1 mapping to one grounding item.
    """

    id: str
    tier: UnderstandingTier
    kind: UnderstandingStatementKind
    text: str
    grounding_item_ids: List[str] = Field(default_factory=list)


class UnderstandingState(BaseModel):
    """
    Tier 1 populates every turn (see src/orchestrator/engine.py::run_turn).
    Tier 2 fields exist so this schema doesn't need to change shape when
    that tier is picked up later -- they stay empty/None this round; see
    the plan's "Deferred design -- Tier 2" section for tier2_grounding_signature's
    intended future use (a hash of (id, status, content) per grounding
    item, not bare ids -- keying on the id set alone under-invalidates a
    status-only change like a Decision resolving).
    """

    tier1: List[UnderstandingStatement] = Field(default_factory=list)
    tier2: List[UnderstandingStatement] = Field(default_factory=list)
    tier2_grounding_signature: Optional[str] = None
    tier2_computed_at_turn: Optional[int] = None
