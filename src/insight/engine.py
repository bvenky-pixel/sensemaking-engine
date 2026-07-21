"""
Insight Engine -- calls an LLM to detect recurring cross-session themes
(see engine/decisions.md "Major update").

Explicit scope decisions made before implementation:
- Runs OFFLINE ONLY (scripts/run_insight_detection.py), never inside a
  live request -- same "Learning never computes inside a live
  conversation turn" boundary this codebase already enforces for
  src/learning/engine.py (see engine/specs/system-architecture-v2-specification.md).
  Nothing in src/api/server.py calls this module.
- One call, one schema, same simplicity as Judgment/Planner/Response.
- Engine-level grounding enforcement, not just prompt wording (mirroring
  src/interpretation/engine.py's own code-level grounding filters):
  after the LLM call, every Insight's evidence_session_ids is filtered
  down to the intersection with session ids actually sent in the prompt,
  and any Insight whose surviving evidence count falls below
  MIN_EVIDENCE_SESSIONS is dropped entirely. The model's own ids are
  never trusted uncritically -- a hallucinated or duplicated id must not
  let a genuinely under-evidenced theme slip through.

Insight-triggered conversational callback (2026-07-19, backlog #210,
see engine/decisions.md): `select_relevant_insight` below is the one
piece of this module that runs LIVE, inside a turn (called from
src/response/engine.py::run_response_generator) -- everything else here
stays offline-only. Deliberately mechanical, not a second LLM call:
same "grounded word-overlap over invented ML" discipline as
src/pom/engine.py's own _is_evidence_grounded, chosen over genuine
semantic/embedding matching per the founder's own explicit direction
(confirmed over the "most-recently-computed insight" alternative,
despite Retrieval/Need State Inference elsewhere in this codebase both
being deliberately "label-only, not filtering" by prior design choice --
this is a narrower, single-purpose selection, not a general relevance-
filtering system).
"""

from __future__ import annotations

import json
import re
from typing import List, Optional, Tuple

from pydantic import ValidationError

from src.instrumentation.usage import AttemptRecord, UsageTracker, default_tracker
from src.insight.prompt import build_messages
from src.insight.schema import MIN_EVIDENCE_SESSIONS, Insight, InsightBatch
from src.llm.providers import ProviderCallError, call_provider, resolve_provider_chain
from src.state.world_state import WorldState

TEMPERATURE = 0.15  # low: this is assessment/classification, not creative generation

_WORD_RE = re.compile(r"[a-z0-9']+")


def _words(text: str) -> set:
    return set(_WORD_RE.findall(text.lower()))


def _render_state_content(state: WorldState) -> str:
    """Plain text blob of what THIS Journey has actually said so far,
    for mechanical word-overlap matching only (see
    select_relevant_insight) -- not a user-facing rendering. Duplicated
    rendering, same category as src/pom/engine.py's own
    _render_entity_text: small, per-package rendering helpers are
    deliberately duplicated across engine packages in this codebase
    rather than imported."""
    parts = [f.content for f in state.facts]
    parts += [c.content for c in state.claims]
    parts += [g.content for g in state.goals]
    parts += [d.content for d in state.decisions]
    parts += [e.name for e in state.entities]
    return " ".join(parts)


def select_relevant_insight(insights: List[Insight], state: WorldState) -> Optional[Insight]:
    """Insight-triggered conversational callback (2026-07-19, backlog
    #210) -- scores each Insight's theme+detail against what THIS
    Journey has actually said so far (this turn's own WorldState) by
    shared-word overlap, and returns the single highest-scoring one.
    Returns None when there's nothing to select from, or when every
    insight has zero real word overlap with this conversation -- a
    callback referencing something with no genuine connection to what's
    being discussed would read as a non sequitur, worse than saying
    nothing. Ties broken by list order (whichever insight comes first in
    `insights`, itself already ordered by src.api.db.get_insights) --
    never re-sorted or randomized."""
    if not insights:
        return None
    content_words = _words(_render_state_content(state))
    if not content_words:
        return None
    scored = [
        (insight, len(_words(f"{insight.theme} {insight.detail}") & content_words))
        for insight in insights
    ]
    best_insight, best_score = max(scored, key=lambda pair: pair[1])
    return best_insight if best_score > 0 else None


class InsightEngineError(Exception):
    """Raised when no configured provider could produce a valid InsightBatch."""

    def __init__(self, message: str, raw_output: Optional[str] = None):
        super().__init__(message)
        self.raw_output = raw_output


def _enforce_grounding(insights: List[Insight], known_session_ids: set) -> List[Insight]:
    """Never trust the model's own evidence_session_ids uncritically --
    filter to real ids actually sent, then drop anything that falls
    below the evidence floor as a result. See module docstring."""
    grounded: List[Insight] = []
    for insight in insights:
        real_ids = [sid for sid in insight.evidence_session_ids if sid in known_session_ids]
        if len(real_ids) < MIN_EVIDENCE_SESSIONS:
            continue
        grounded.append(insight.model_copy(update={"evidence_session_ids": real_ids}))
    return grounded


def run_insight_detection(
    session_texts: List[Tuple[str, str, str]], tracker: Optional[UsageTracker] = None
) -> List[Insight]:
    """
    Calls an LLM to detect recurring themes across the given sessions.
    `session_texts` is a list of (session_id, surface_complaint,
    primary_problem) tuples -- see src/api/db.py::get_session_texts_for_insights,
    which already caps this at MAX_SESSIONS_FOR_INSIGHT and only includes
    sessions with a completed Judgment. Tries each configured provider in
    order, same as every other engine in this codebase. Raises
    InsightEngineError if every provider fails.

    Returns an empty list, not an error, when session_texts has fewer
    than MIN_EVIDENCE_SESSIONS entries -- there is structurally no way to
    ground a recurring theme in fewer sessions than the evidence floor
    requires, so this short-circuits before spending an LLM call on it.
    """
    if len(session_texts) < MIN_EVIDENCE_SESSIONS:
        return []

    known_session_ids = {sid for sid, _, _ in session_texts}
    system_prompt, messages = build_messages(session_texts)
    schema = InsightBatch.model_json_schema()
    tracker = tracker or default_tracker

    failures: List[str] = []
    for provider_name in resolve_provider_chain():
        try:
            raw = call_provider(
                provider_name, system_prompt, messages, schema, TEMPERATURE,
                component="Insight", tracker=tracker,
            )
        except ProviderCallError as exc:
            failures.append(f"{provider_name}: {exc}")
            tracker.record_outcome(AttemptRecord(
                component="Insight", provider=provider_name,
                outcome="provider_call_error", detail=str(exc),
            ))
            continue

        raw = raw.replace("```json", "").replace("```", "").strip()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            failures.append(f"{provider_name}: model output was not valid JSON: {exc}")
            tracker.record_outcome(AttemptRecord(
                component="Insight", provider=provider_name,
                outcome="invalid_json", detail=str(exc),
            ))
            continue

        try:
            result = InsightBatch(**data)
        except ValidationError as exc:
            failures.append(f"{provider_name}: model output failed schema validation: {exc}")
            tracker.record_outcome(AttemptRecord(
                component="Insight", provider=provider_name,
                outcome="schema_validation_failed", detail=str(exc),
            ))
            continue

        tracker.record_outcome(AttemptRecord(
            component="Insight", provider=provider_name, outcome="success",
        ))
        return _enforce_grounding(result.insights, known_session_ids)

    raise InsightEngineError("All configured LLM providers failed: " + "; ".join(failures))
