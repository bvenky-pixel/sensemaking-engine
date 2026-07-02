"""
StateUpdater: calls the Claude API (Anthropic Messages API) to produce an
updated ConversationState from the current state + the running transcript.

Design notes:
- The model is instructed to return ONLY the updated state as strict JSON,
  matching a Pydantic schema. We use Claude's built-in Structured Outputs
  feature (client.messages.parse(..., output_format=PydanticModel)), which
  compiles the schema into a constrained-decoding grammar server-side --
  Claude literally cannot emit a shape that doesn't match the schema.
- The SDK already validates the response against the Pydantic model for us
  (response.parsed_output). We still check response.stop_reason, because a
  safety refusal or a max_tokens cutoff can both return a 200 with
  parsed_output that's missing or doesn't reflect a real update.
- The updater never mutates the passed-in state in place; it returns a new
  ConversationState instance (or raises StateUpdateError).
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, replace
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, ValidationError

from engine.state import ConversationState

try:
    from anthropic import Anthropic
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "The 'anthropic' package is required for StateUpdater. Install it "
        "with `pip install anthropic`."
    ) from exc


DEFAULT_MODEL = "claude-sonnet-5"
DEFAULT_MAX_TOKENS = 1024


# ---------------------------------------------------------------------------
# Typed schema
# ---------------------------------------------------------------------------
# Mirrors ConversationState field-for-field so the model's output can be
# validated before it ever touches the real state object. `urgency` is
# constrained to a closed set since ConversationState treats it as a category,
# not free text -- tighten/loosen this if that assumption doesn't hold.
class ConversationStateSchema(BaseModel):
    emotion: str = ""
    emotion_intensity: int = Field(default=0, ge=0, le=10)

    urgency: Literal["low", "medium", "high"] = "low"

    core_problem: str = ""

    facts: List[str] = Field(default_factory=list)
    interpretations: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    unknowns: List[str] = Field(default_factory=list)

    stakeholders: List[str] = Field(default_factory=list)

    agency_level: float = Field(default=0.0, ge=0.0, le=1.0)
    clarity_level: float = Field(default=0.0, ge=0.0, le=1.0)

    decision: str = ""

    history_summary: str = ""

    def to_state(self) -> ConversationState:
        return ConversationState(**self.model_dump())


class StateUpdateError(Exception):
    """Raised when the model's output can't be parsed into a valid state."""

    def __init__(self, message: str, raw_output: Optional[str] = None):
        super().__init__(message)
        self.raw_output = raw_output


# ---------------------------------------------------------------------------
# StateUpdater
# ---------------------------------------------------------------------------
class StateUpdater:
    """
    Given the current ConversationState and a transcript, asks Claude to
    produce an updated state and returns it as a validated ConversationState.
    """

    SYSTEM_PROMPT = (
        "You maintain a structured ConversationState object for an ongoing "
        "conversation between a user and an assistant.\n\n"
        "You will be given:\n"
        "1. The CURRENT STATE as JSON.\n"
        "2. The CONVERSATION TRANSCRIPT so far.\n\n"
        "Your job is to return an UPDATED STATE, and ONLY the updated state, "
        "as JSON matching the required schema exactly.\n\n"
        "Rules:\n"
        "- Do not invent facts, stakeholders, or decisions that are not "
        "supported by the transcript.\n"
        "- Carry forward any field from the current state that the "
        "transcript gives no reason to change.\n"
        "- Only change a field when the transcript provides new or "
        "contradicting information for it.\n"
        "- 'facts' are things stated as true. 'interpretations' are the "
        "user's or assistant's read on what facts mean. 'assumptions' are "
        "unstated beliefs being relied on. 'unknowns' are open questions "
        "still unresolved.\n"
        "- agency_level and clarity_level are floats from 0.0 to 1.0 "
        "representing how much control the user feels they have, and how "
        "clearly the problem is understood, respectively.\n"
    )

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        client: Optional["Anthropic"] = None,
    ):
        """
        api_key: falls back to ANTHROPIC_API_KEY env var if not provided.
        client: pass an existing Anthropic client instance (e.g. for testing
                with a mock), otherwise one is constructed.
        """
        self.model = model
        self.max_tokens = max_tokens
        self.client = client or Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))

    def update(
        self,
        current_state: ConversationState,
        transcript: str,
    ) -> ConversationState:
        """
        Calls the Claude API and returns a new, validated ConversationState.
        Raises StateUpdateError on any failure to obtain a valid state
        (network/API error, refusal, truncated output, schema validation
        failure).
        """
        current_state_json = json.dumps(asdict(current_state), indent=2)

        user_input = (
            f"CURRENT STATE:\n{current_state_json}\n\n"
            f"CONVERSATION TRANSCRIPT:\n{transcript}"
        )

        try:
            response = self.client.messages.parse(
                model=self.model,
                max_tokens=self.max_tokens,
                system=self.SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_input}],
                output_format=ConversationStateSchema,
            )
        except Exception as exc:  # network/auth/API-level failures
            raise StateUpdateError(f"Claude API call failed: {exc}") from exc

        raw_text = self._extract_raw_text(response)

        if getattr(response, "stop_reason", None) == "refusal":
            raise StateUpdateError(
                "Claude refused to produce a state update for this turn.",
                raw_output=raw_text,
            )
        if getattr(response, "stop_reason", None) == "max_tokens":
            raise StateUpdateError(
                "Response was truncated (max_tokens reached) before a "
                "complete state was returned. Try increasing max_tokens.",
                raw_output=raw_text,
            )

        parsed = getattr(response, "parsed_output", None)
        if parsed is None:
            # SDK didn't give us a validated object -- fall back to manual
            # parse/validate so we can surface a precise error either way.
            if raw_text is None:
                raise StateUpdateError(
                    "No output found in the API response.", raw_output=str(response)
                )
            try:
                parsed_json = json.loads(raw_text)
            except json.JSONDecodeError as exc:
                raise StateUpdateError(
                    f"Model output was not valid JSON: {exc}", raw_output=raw_text
                ) from exc
            try:
                parsed = ConversationStateSchema.model_validate(parsed_json)
            except ValidationError as exc:
                raise StateUpdateError(
                    f"Model output failed schema validation: {exc}",
                    raw_output=raw_text,
                ) from exc

        return parsed.to_state()

    @staticmethod
    def _extract_raw_text(response) -> Optional[str]:
        """Best-effort extraction of the raw text content, used only for
        error messages / fallback parsing -- not the primary success path."""
        for block in getattr(response, "content", []) or []:
            text = getattr(block, "text", None)
            if text:
                return text
        return None


# ---------------------------------------------------------------------------
# MockStateUpdater
# ---------------------------------------------------------------------------
class MockStateUpdater:
    """
    Deterministic, keyword-rule stand-in for StateUpdater.

    Makes NO API or LLM calls of any kind. Useful for local development,
    unit tests, or running conversation_runner.py without an API key or
    network access, while still exercising the rest of the pipeline
    (ConversationState updates -> StateInspector rendering).

    Exposes exactly one public method: update(state, transcript).
    """

    # Urgency escalates one step at a time rather than jumping straight to
    # "high" -- keeps repeated "should I" mentions meaningfully different
    # from a single one.
    _URGENCY_STEPS = ["low", "medium", "high"]

    def update(self, state: ConversationState, transcript: str) -> ConversationState:
        """
        Accepts the current ConversationState and the full conversation
        transcript, applies simple keyword rules against the transcript,
        and returns a NEW ConversationState. The input `state` is never
        mutated in place -- any field the rules below don't touch is
        carried forward unchanged into the returned copy.
        """
        text = transcript.lower()

        # Start from a copy of the current state so untouched fields carry
        # forward as-is.
        updated = replace(state)

        # --- Emotion ---------------------------------------------------
        # "anxious"/"worried"/"stress" all map to the same emotion label;
        # checked before "angry" so a transcript can't set both -- last
        # matching rule wins if you reorder these.
        if any(keyword in text for keyword in ("anxious", "worried", "stress")):
            updated.emotion = "anxious"
        elif "angry" in text:
            updated.emotion = "angry"

        # --- Core problem ------------------------------------------------
        if "job" in text:
            updated.core_problem = "Career decision"

        # --- Stakeholders --------------------------------------------------
        # Append rather than overwrite, and avoid duplicate entries if
        # "boss" shows up again in a later turn.
        if "boss" in text and "Manager" not in updated.stakeholders:
            updated.stakeholders = updated.stakeholders + ["Manager"]

        # --- Urgency -----------------------------------------------------
        # "should I" reads as decision-seeking language -- bump urgency up
        # one step (low -> medium -> high), capped at "high".
        if "should i" in text:
            current_index = (
                self._URGENCY_STEPS.index(updated.urgency)
                if updated.urgency in self._URGENCY_STEPS
                else 0
            )
            next_index = min(current_index + 1, len(self._URGENCY_STEPS) - 1)
            updated.urgency = self._URGENCY_STEPS[next_index]

        return updated