"""
Tier 2 synthesis engine -- see engine/decisions.md "Tier 2 design"
(design pass) and this module's own functions for the implementation
that followed it.

Explicit scope decisions carried over from that design pass:
- Runs INSIDE the live turn (unlike src/insight/, which is
  offline-only) -- Tier 2 lives directly on ONE Journey's own
  WorldState (src/understanding/schema.py::UnderstandingState), the
  same "single call-site" design the original deferred plan called
  sound. src/orchestrator/engine.py::run_turn is that single call site.
- NON-BLOCKING failure mode: unlike Interpretation/Judgment/Planner/
  Response, a Tier 2 failure (any exception -- provider error, invalid
  JSON, schema validation) must never abort the turn or leave WorldState
  worse off. update_tier2 below catches everything and leaves
  state.understanding.tier2* fields exactly as they were on any failure.
- CONDITIONAL, not every-turn: this is the whole point of the design
  pass -- computing Tier 2 every turn would add a 5th LLM call on top
  of the existing 4/turn (see CLAUDE.md's free-tier rate-limit
  discussion). should_recompute_tier2 below gates the actual LLM call
  behind a real candidate-pool change or a staleness backstop, so most
  turns skip it entirely, leaving the previous turn's tier2 untouched.
- Engine-level grounding enforcement, not just prompt wording (same
  discipline as src/insight/engine.py's own evidence_session_ids
  filtering): every Tier2Statement's grounding_item_ids is filtered down
  to the intersection with ids actually offered as candidates, and any
  statement with fewer than MIN_GROUNDING_ITEMS surviving ids is dropped
  entirely -- the model's own ids are never trusted uncritically.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Dict, List, Optional, Tuple

from pydantic import ValidationError

from src.instrumentation.usage import AttemptRecord, UsageTracker, default_tracker
from src.llm.providers import ProviderCallError, call_provider, resolve_provider_chain
from src.state.world_state import WorldState
from src.understanding.engine import build_tier1_statements
from src.understanding.schema import Tier2Batch, UnderstandingStatement
from src.understanding.tier2_prompt import build_messages

TEMPERATURE = 0.15  # low: this is assessment/synthesis, not creative generation

# A synthesis statement grounded in fewer than this many surviving
# (real, offered) candidate ids is a paraphrase of one candidate, not a
# synthesis of several -- see the prompt's own law 3/6. Rejected
# entirely, same "an empty/smaller list is correct, not a gap" framing
# as src/insight/engine.py's MIN_EVIDENCE_SESSIONS.
MIN_GROUNDING_ITEMS = 2

# "Thread" kinds: Goal/Decision/Unknown (rendered as Tier 1 kind
# "uncertainty"). Confirmed by the validation report's own Area 1/5 data
# to stay naturally small in practice (a person has a handful of
# concurrently open decisions, not dozens) while individually going
# silently stale for long stretches -- so these stay Tier 2 candidates
# for as long as they're non-terminal, regardless of recency. See
# engine/decisions.md "Tier 2 design" Q2.
_THREAD_KINDS = {"goal", "decision", "uncertainty"}

# Non-terminal statuses per thread kind -- stricter than Tier 1's own
# VISIBLE_STATUSES filters in src/understanding/engine.py (which
# deliberately include "completed"/terminal states, since Tier 1 is a
# complete record). A completed Goal's thread is closed; it shouldn't
# stay in the Tier 2 pool indefinitely the way a still-open one does.
_TIER2_OPEN_STATUSES_BY_KIND: Dict[str, set] = {
    "goal": {"active", "paused"},
    "decision": {"open", "deferred"},
    "uncertainty": {"open"},
}

# "Detail" kinds: Fact/Claim/Assumption/Inference/Entity/EmotionalSignalItem.
# Confirmed unbounded by Area 5 (~1 new assumption per 4-5 turns, linear
# fact/claim growth, no retraction path today) -- recency-windowed so
# the Tier 2 candidate pool stays bounded regardless of Journey length.
# First-cut, explicitly uncalibrated placeholder (same convention as
# every other threshold in this codebase, e.g.
# UNKNOWN_RESOLUTION_OVERLAP_THRESHOLD, INFERENCE_CONFIDENCE_FLOOR) --
# not chosen from real evidence yet, since Tier 2 doesn't exist to
# generate that evidence until it ships.
TIER2_RECENCY_WINDOW_TURNS = 10

# Hard backstop, independent of the grounding-signature hash: force a
# recompute at least this often even when the candidate pool's hash
# hasn't changed, since the hash can't catch every staleness cause
# (e.g. the conversation's emphasis shifting with no new WorldState
# item at all). Same "first-cut, not the final word" status as the
# recency window above.
TIER2_STALENESS_TURNS = 5


def _knowledge_item_lookup(state: WorldState) -> Tuple[Dict[str, str], Dict[str, int]]:
    """Every KnowledgeItem's id -> (status, provenance.last_updated),
    across all eight subtypes -- Tier 1's own UnderstandingStatement
    doesn't carry status/provenance, so candidate selection needs this
    separate lookup back into WorldState."""
    status_by_id: Dict[str, str] = {}
    last_updated_by_id: Dict[str, int] = {}
    all_items = (
        state.facts + state.claims + state.goals + state.decisions
        + state.unknowns + state.entities + state.assumption_items
        + state.inference_items + state.emotional_signal_items
    )
    for item in all_items:
        status_by_id[item.id] = item.status
        last_updated_by_id[item.id] = item.provenance.last_updated if item.provenance else 0
    return status_by_id, last_updated_by_id


def select_tier2_candidates(state: WorldState) -> List[UnderstandingStatement]:
    """
    The Tier 2 candidate pool, per engine/decisions.md "Tier 2 design"
    Q2: starts from Tier 1's own rendering (reusing its status filters
    and text templates rather than duplicating them), then narrows
    further by kind:
    - thread kinds (goal/decision/uncertainty): kept as long as the
      grounding item's real status is still non-terminal, regardless of
      how long ago it was last touched.
    - detail kinds (everything else): kept only if the grounding item
      was created or updated within TIER2_RECENCY_WINDOW_TURNS turns.

    Statements with no grounding_item_ids (should not occur for any
    current Tier 1 loop, but defensive) are excluded -- there's nothing
    to look up a status/recency for.
    """
    status_by_id, last_updated_by_id = _knowledge_item_lookup(state)
    candidates: List[UnderstandingStatement] = []

    for stmt in build_tier1_statements(state):
        if not stmt.grounding_item_ids:
            continue
        item_id = stmt.grounding_item_ids[0]

        if stmt.kind in _THREAD_KINDS:
            allowed = _TIER2_OPEN_STATUSES_BY_KIND.get(stmt.kind, set())
            if status_by_id.get(item_id) in allowed:
                candidates.append(stmt)
        else:
            last_updated = last_updated_by_id.get(item_id, 0)
            if state.turn_count - last_updated <= TIER2_RECENCY_WINDOW_TURNS:
                candidates.append(stmt)

    return candidates


def compute_tier2_grounding_signature(
    candidates: List[UnderstandingStatement], state: WorldState
) -> str:
    """
    Hash of the CURRENT CANDIDATE POOL -- id + real status + text per
    candidate -- not just the ids a previously-computed Tier 2 statement
    happens to cite. See engine/decisions.md "Tier 2 design" Q1 for why
    hashing only already-cited items misses a new near-duplicate arrival:
    pool membership itself is recomputed fresh every call (via
    select_tier2_candidates), so a new item entering/leaving the pool,
    or an existing pooled item's status changing, both change this hash
    even when nothing previously CITED by an existing Tier 2 statement
    changed at all.
    """
    status_by_id, _ = _knowledge_item_lookup(state)
    parts = sorted(
        f"{c.grounding_item_ids[0]}:{status_by_id.get(c.grounding_item_ids[0], '')}:{c.text}"
        for c in candidates
        if c.grounding_item_ids
    )
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def should_recompute_tier2(state: WorldState, new_signature: str) -> bool:
    """True when the candidate pool's signature changed since the last
    computed Tier 2, OR Tier 2 has never been computed, OR the staleness
    backstop (TIER2_STALENESS_TURNS) has tripped regardless of the
    signature matching."""
    u = state.understanding
    if u.tier2_grounding_signature != new_signature:
        return True
    if u.tier2_computed_at_turn is None:
        return True
    return state.turn_count - u.tier2_computed_at_turn >= TIER2_STALENESS_TURNS


def _enforce_grounding(
    statements: list, known_ids: set
) -> List[UnderstandingStatement]:
    """Never trust the model's own grounding_item_ids uncritically --
    filter to real candidate ids actually offered, then drop anything
    that falls below MIN_GROUNDING_ITEMS as a result. Same discipline as
    src/insight/engine.py's _enforce_grounding. Assigns a fresh id and
    tier=2 to each surviving statement -- a Tier 2 statement's identity
    is its own cached-until-regenerated text, not a 1:1 mapping to one
    grounding item (see UnderstandingStatement's own docstring)."""
    grounded: List[UnderstandingStatement] = []
    for stmt in statements:
        real_ids = [gid for gid in stmt.grounding_item_ids if gid in known_ids]
        if len(real_ids) < MIN_GROUNDING_ITEMS:
            continue
        grounded.append(UnderstandingStatement(
            id=f"tier2:{uuid.uuid4()}", tier=2, kind="synthesis",
            text=stmt.text, grounding_item_ids=real_ids,
        ))
    return grounded


class Tier2EngineError(Exception):
    """Raised when no configured provider could produce a valid Tier2Batch."""

    def __init__(self, message: str, raw_output: Optional[str] = None):
        super().__init__(message)
        self.raw_output = raw_output


def run_tier2_synthesis(
    candidates: List[UnderstandingStatement], tracker: Optional[UsageTracker] = None
) -> List[UnderstandingStatement]:
    """
    Calls an LLM to synthesize Tier 2 statements from the given
    candidates. Tries each configured provider in order, same as every
    other engine in this codebase. Raises Tier2EngineError if every
    provider fails -- callers inside the live turn (update_tier2 below)
    must catch this, per this module's non-blocking design.

    Returns an empty list, not an error, when candidates has fewer than
    MIN_GROUNDING_ITEMS entries -- structurally no way to synthesize
    across multiple candidates from fewer than that many, so this
    short-circuits before spending an LLM call on it.
    """
    if len(candidates) < MIN_GROUNDING_ITEMS:
        return []

    known_ids = {c.id for c in candidates}
    system_prompt, messages = build_messages(candidates)
    schema = Tier2Batch.model_json_schema()
    tracker = tracker or default_tracker

    failures: List[str] = []
    for provider_name in resolve_provider_chain():
        try:
            raw = call_provider(
                provider_name, system_prompt, messages, schema, TEMPERATURE,
                component="Tier2", tracker=tracker,
            )
        except ProviderCallError as exc:
            failures.append(f"{provider_name}: {exc}")
            tracker.record_outcome(AttemptRecord(
                component="Tier2", provider=provider_name,
                outcome="provider_call_error", detail=str(exc),
            ))
            continue

        raw = raw.replace("```json", "").replace("```", "").strip()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            failures.append(f"{provider_name}: model output was not valid JSON: {exc}")
            tracker.record_outcome(AttemptRecord(
                component="Tier2", provider=provider_name,
                outcome="invalid_json", detail=str(exc),
            ))
            continue

        try:
            result = Tier2Batch(**data)
        except ValidationError as exc:
            failures.append(f"{provider_name}: model output failed schema validation: {exc}")
            tracker.record_outcome(AttemptRecord(
                component="Tier2", provider=provider_name,
                outcome="schema_validation_failed", detail=str(exc),
            ))
            continue

        tracker.record_outcome(AttemptRecord(
            component="Tier2", provider=provider_name, outcome="success",
        ))
        return _enforce_grounding(result.statements, known_ids)

    raise Tier2EngineError("All configured LLM providers failed: " + "; ".join(failures))


def update_tier2(state: WorldState, tracker: Optional[UsageTracker] = None) -> WorldState:
    """
    The single call site (see module docstring) -- called from
    src/orchestrator/engine.py::run_turn once per turn. Computes the
    candidate pool and its signature UNCONDITIONALLY (cheap, no LLM
    call), but only actually calls the LLM when should_recompute_tier2
    says so; otherwise returns state completely unchanged, leaving the
    previous turn's tier2/signature/computed_at_turn in place.

    NON-BLOCKING: any exception raised by run_tier2_synthesis (provider
    failure, invalid JSON, schema validation) is caught here and
    swallowed -- state is returned unchanged on failure, exactly as if
    should_recompute_tier2 had said no this turn. A Tier 2 failure must
    never abort the turn or regress WorldState, per this module's
    explicit scope decision (see module docstring).
    """
    candidates = select_tier2_candidates(state)
    new_signature = compute_tier2_grounding_signature(candidates, state)

    if not should_recompute_tier2(state, new_signature):
        return state

    try:
        tier2_statements = run_tier2_synthesis(candidates, tracker=tracker)
    except Exception:
        return state

    new_state = state.model_copy(deep=True)
    new_state.understanding.tier2 = tier2_statements
    new_state.understanding.tier2_grounding_signature = new_signature
    new_state.understanding.tier2_computed_at_turn = state.turn_count
    return new_state
