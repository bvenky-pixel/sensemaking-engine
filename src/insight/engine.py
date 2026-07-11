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
"""

from __future__ import annotations

import json
from typing import List, Optional, Tuple

from pydantic import ValidationError

from src.instrumentation.usage import AttemptRecord, UsageTracker, default_tracker
from src.insight.prompt import build_messages
from src.insight.schema import MIN_EVIDENCE_SESSIONS, Insight, InsightBatch
from src.llm.providers import ProviderCallError, call_provider, resolve_provider_chain

TEMPERATURE = 0.15  # low: this is assessment/classification, not creative generation


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
