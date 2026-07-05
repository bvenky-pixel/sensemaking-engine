"""
Judgment Engine v2 -- calls an LLM to turn the accumulated WorldState into
a Judgment: an objective assessment of the user's current situation.

Implements engine/specs/judgment-specification-v2.md. Explicit scope
decisions made before implementation (see engine/decisions.md for the
full discussion):
- Input is WorldState ONLY -- never the raw Interpretation or transcript.
  Urgency/emotion are not passed through; if they matter, they should
  first become part of WorldState, not be smuggled in here.
- `resolved_since_last_turn` and `trajectory` are dropped from the v2
  spec's output for now -- both need a delta against a previous
  WorldState/Judgment, which WorldState v1 (no turn numbers, no retained
  history of transitions) can't supply. See src/judgment/schema.py.
- This is NOT a rule engine and NOT a hybrid -- the entire Judgment
  object, including fields that look like plain filters (open_unknowns,
  active_decisions), comes from one LLM call over the full WorldState.
  Deliberate simplicity: one call, one schema, no hybrid complexity.
- `phase` (Prepare/Discover/Discern/...) is NOT part of Judgment's LLM
  output at all -- kept as a separate, deterministic
  `recommend_phase_transition` function below, explicitly legacy-only.
  Its long-term owner is the future Planner, not Judgment.
"""

from __future__ import annotations

import json
from typing import List, Optional

from pydantic import ValidationError

from src.instrumentation.usage import UsageTracker, default_tracker
from src.judgment.prompt import build_messages
from src.llm.providers import ProviderCallError, call_provider, resolve_provider_chain
from src.judgment.schema import Judgment
from src.state.world_state import WorldState

TEMPERATURE = 0.15  # low: this is assessment/reasoning, not creative generation

# --- Legacy phase-transition thresholds, ported unchanged from Judgment v1 ---
# Minimum core_question_confidence before we consider the "real question"
# actually found (Phase 2 success: the conversation moves from "why is
# this happening" to "what can I do").
DISCOVER_TO_DISCERN_THRESHOLD = 0.6

# Phase 3 success (partial, MVP heuristic): at least one assumption or
# bias has been surfaced. The full success criterion in the constitution
# also requires the user to *recognize* it, which this layer can't judge
# on its own -- that needs a future turn's language, not this one.
DISCERN_MIN_SIGNALS = 1


class JudgmentError(Exception):
    """Raised when no configured provider could produce a valid Judgment."""

    def __init__(self, message: str, raw_output: Optional[str] = None):
        super().__init__(message)
        self.raw_output = raw_output


def run_judgment(state: WorldState, tracker: Optional[UsageTracker] = None) -> Judgment:
    """
    Calls an LLM to produce a Judgment from the given WorldState. Tries
    each configured provider in order (see src/llm/providers.py),
    same OpenRouter-primary/Ollama-fallback pattern as Interpretation.
    Raises JudgmentError if every provider fails.

    Callers should update WorldState with the current turn's Interpretation
    BEFORE calling this -- Judgment only ever sees WorldState, so if it's
    called against stale state, it has no way to know about anything just
    said this turn.

    tracker: optional UsageTracker (src/instrumentation/usage.py) to record
    token/cost/latency into. Defaults to the shared default_tracker if not
    given -- recording itself is still a no-op unless CONFIDANT_TRACK_USAGE
    is set, so this has no effect on normal runs either way.
    """
    world_state_json = state.model_dump_json(indent=2)
    system_prompt, messages = build_messages(world_state_json)
    schema = Judgment.model_json_schema()
    tracker = tracker or default_tracker

    failures: List[str] = []
    for provider_name in resolve_provider_chain():
        try:
            raw = call_provider(
                provider_name, system_prompt, messages, schema, TEMPERATURE,
                component="Judgment", tracker=tracker,
            )
        except ProviderCallError as exc:
            failures.append(f"{provider_name}: {exc}")
            continue

        raw = raw.replace("```json", "").replace("```", "").strip()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            failures.append(f"{provider_name}: model output was not valid JSON: {exc}")
            continue

        try:
            return Judgment(**data)
        except ValidationError as exc:
            failures.append(f"{provider_name}: model output failed schema validation: {exc}")
            continue

    raise JudgmentError("All configured LLM providers failed: " + "; ".join(failures))


def recommend_phase_transition(state: WorldState) -> Optional[str]:
    """
    Deterministic, legacy-compatibility phase recommendation -- NOT part
    of the Judgment v2 LLM output. Ported from Judgment v1's logic,
    translated to read off accumulated WorldState fields instead of a
    single turn's Interpretation (state.assumptions/state.biases are the
    full accumulated lists, arguably a better signal than one turn's
    count ever was). Kept deliberately unexpanded: this only decides
    whether to recommend staying or advancing phase, nothing else.

    Returns None if no transition is recommended.
    """
    current_phase = getattr(state, "phase", "prepare")

    if current_phase == "prepare" and state.surface_complaint:
        return "discover"
    if current_phase == "discover" and state.core_question_confidence >= DISCOVER_TO_DISCERN_THRESHOLD:
        return "discern"
    if current_phase == "discern":
        signal_count = len(state.assumptions) + len(state.biases)
        if signal_count >= DISCERN_MIN_SIGNALS:
            return "discern"  # stays; advancing to challenge is undrafted in the constitution

    return None
