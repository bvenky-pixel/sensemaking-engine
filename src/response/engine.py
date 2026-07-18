"""
Response Generator Engine v1 -- calls an LLM to turn WorldState + Judgment
+ Planner into a Response: the actual natural-language message the user
reads. This is the final stage of the pipeline and the first stage whose
output is shown to the user directly -- every earlier artifact
(Interpretation, WorldState, Judgment, Planner) stays internal.

Implements engine/specs/response-generator-specification-v1.md. Explicit
scope decisions made before implementation (see engine/decisions.md for
the full discussion):
- Input is WorldState + Judgment + Planner ONLY -- never the raw
  conversation or Interpretation, per the spec's Inputs section.
- TEMPERATURE is 0.7, NOT the 0.15 used by Judgment and Planner. Those
  two are assessment/reasoning tasks reusing the same low-temperature
  rationale; Response Generator is explicitly EXPRESSION, not cognition
  -- natural-language generation benefits from more variation than
  analytical reasoning does. This is a deliberate, documented departure,
  not an oversight, and (like every fresh layer's first parameter choice
  on this branch) an unvalidated first guess pending real output review.
- This is a full LLM call, not a rule engine or template system -- same
  "one call, one schema" simplicity already chosen for Judgment v2 and
  Planner v1.
"""

from __future__ import annotations

import json
from typing import List, Optional

from pydantic import ValidationError

from src.instrumentation.usage import AttemptRecord, UsageTracker, default_tracker
from src.judgment.schema import Judgment
from src.llm.providers import ProviderCallError, call_provider, resolve_provider_chain
from src.orchestrator.modes import response_mode_focus_note
from src.planner.schema import Planner
from src.response.prompt import build_messages
from src.response.schema import Response
from src.state.world_state import PROMPT_EXCLUDED_FIELDS, WorldState

TEMPERATURE = 0.7  # higher than Judgment/Planner's 0.15: this is expression, not assessment


class ResponseGeneratorError(Exception):
    """Raised when no configured provider could produce a valid Response."""

    def __init__(self, message: str, raw_output: Optional[str] = None):
        super().__init__(message)
        self.raw_output = raw_output


def run_response_generator(
    state: WorldState,
    judgment: Judgment,
    planner: Planner,
    tracker: Optional[UsageTracker] = None,
    mode: Optional[str] = None,
) -> Response:
    """
    Calls an LLM to produce a Response from the given WorldState, Judgment,
    and Planner. Tries each configured provider in order (see
    src/llm/providers.py -- OpenRouter is the only registered provider
    today, same as every other layer). Raises ResponseGeneratorError if
    every provider fails.

    Callers should call this AFTER run_planner, on the same Judgment and
    Planner objects for this turn -- Response Generator's whole job is to
    faithfully express that specific plan, not a stale one.

    tracker: optional UsageTracker (src/instrumentation/usage.py) to record
    token/cost/latency into. Defaults to the shared default_tracker if not
    given -- recording itself is still a no-op unless CONFIDANT_TRACK_USAGE
    is set, so this has no effect on normal runs either way.

    mode: optional Counseling mode id (see src/orchestrator/modes.py) --
    same raw session-level value passed to run_planner, resolved to its
    prompt-injection note here via response_mode_focus_note. `state.turn_count`
    is passed through too (2026-07-18, see engine/decisions.md "Realign
    rotation precomputed in Python") -- Realign's own note uses it to
    resolve which concept sentence 2 should draw on THIS turn in Python,
    rather than asking the model to compute `turn_count % 5` itself;
    every other mode's note ignores this value entirely.
    """
    world_state_json = state.model_dump_json(indent=2, exclude=PROMPT_EXCLUDED_FIELDS)
    judgment_json = judgment.model_dump_json(indent=2)
    planner_json = planner.model_dump_json(indent=2)
    system_prompt, messages = build_messages(
        world_state_json, judgment_json, planner_json,
        response_mode_focus_note(mode, state.turn_count),
    )
    schema = Response.model_json_schema()
    tracker = tracker or default_tracker

    failures: List[str] = []
    for provider_name in resolve_provider_chain():
        try:
            raw = call_provider(
                provider_name, system_prompt, messages, schema, TEMPERATURE,
                component="Response", tracker=tracker,
            )
        except ProviderCallError as exc:
            failures.append(f"{provider_name}: {exc}")
            tracker.record_outcome(AttemptRecord(
                component="Response", provider=provider_name,
                outcome="provider_call_error", detail=str(exc),
            ))
            continue

        raw = raw.replace("```json", "").replace("```", "").strip()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            failures.append(f"{provider_name}: model output was not valid JSON: {exc}")
            tracker.record_outcome(AttemptRecord(
                component="Response", provider=provider_name,
                outcome="invalid_json", detail=str(exc),
            ))
            continue

        try:
            result = Response(**data)
        except ValidationError as exc:
            failures.append(f"{provider_name}: model output failed schema validation: {exc}")
            tracker.record_outcome(AttemptRecord(
                component="Response", provider=provider_name,
                outcome="schema_validation_failed", detail=str(exc),
            ))
            continue

        tracker.record_outcome(AttemptRecord(
            component="Response", provider=provider_name, outcome="success",
        ))
        return result

    raise ResponseGeneratorError("All configured LLM providers failed: " + "; ".join(failures))
