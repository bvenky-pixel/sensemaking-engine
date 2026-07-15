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

UnderstandingStatementKind = Literal[
    "fact", "claim", "goal", "decision", "uncertainty", "inference", "entity", "assumption",
    "emotion", "synthesis",
]
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
    Tier 1 populates every turn, unconditionally (see
    src/orchestrator/engine.py::run_turn). Tier 2 (see
    src/understanding/tier2_engine.py) populates CONDITIONALLY -- only
    when the candidate pool actually changed or the staleness backstop
    trips (see tier2_engine.py's own module docstring and
    engine/decisions.md "Tier 2 design" for why) -- so `tier2`,
    `tier2_grounding_signature`, and `tier2_computed_at_turn` can all
    stay unchanged across many turns in a row; that's the intended,
    cost-saving common case, not staleness.

    `tier2_grounding_signature`: a hash of the CURRENT CANDIDATE POOL
    (id + status + text per candidate, see
    tier2_engine.py::compute_tier2_grounding_signature), not just the
    ids a Tier 2 statement already cites -- see engine/decisions.md
    "Tier 2 design" for why hashing only already-cited items misses a
    new near-duplicate item arriving.
    """

    tier1: List[UnderstandingStatement] = Field(default_factory=list)
    tier2: List[UnderstandingStatement] = Field(default_factory=list)
    tier2_grounding_signature: Optional[str] = None
    tier2_computed_at_turn: Optional[int] = None


class Tier2Statement(BaseModel):
    """
    Raw LLM output for one synthesized Tier 2 statement -- NOT the
    stored shape (see UnderstandingStatement). `grounding_item_ids` is
    never trusted uncritically (see tier2_engine.py::_enforce_grounding,
    same discipline as src/insight/engine.py's own session-id
    filtering): filtered down to ids actually offered as candidates,
    and any statement with zero surviving ids after filtering is
    dropped entirely, never kept ungrounded.
    """

    text: str
    grounding_item_ids: List[str] = Field(default_factory=list)


class Tier2Batch(BaseModel):
    statements: List[Tier2Statement] = Field(default_factory=list)
