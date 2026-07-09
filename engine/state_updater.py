"""
StateUpdater: calls an LLM (OpenRouter by default, with Ollama as an
automatic local fallback) to produce an updated ConversationState from the
current state + the running transcript.

Design notes:
- The model is asked for a JSON object (`response_format={"type":
  "json_object"}`) matching a Pydantic schema described in the system
  prompt. Unlike Claude's constrained-decoding Structured Outputs, JSON mode
  only guarantees syntactically valid JSON, not schema conformance -- so we
  validate the result against ConversationStateSchema ourselves and treat a
  validation failure the same as any other provider failure (i.e. it can
  trigger falling through to the next provider).
- Providers are tried in order (see engine.llm_config.resolve_provider_chain):
  the configured primary first, then any other configured provider as a
  backup. This means an OpenRouter outage, rate limit, or missing/expired key
  doesn't need to take the whole updater down if a local Ollama is available,
  and vice versa.
- The updater never mutates the passed-in state in place; it returns a new
  ConversationState instance (or raises StateUpdateError if every provider
  in the chain fails).
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, ValidationError

from engine.llm_client import LLMClient
from engine.llm_config import ProviderConfig, resolve_provider_chain
from engine.state import ConversationState

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
    emotion_source: Literal["", "explicit", "inferred"] = ""

    urgency: Literal["low", "medium", "high"] = "low"
    impact_domains: List[Literal["personal", "professional", "financial", "health", "legal", "safety", "other"]] = Field(default_factory=list)

    core_problem: str = ""
    core_problem_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    surface_complaint: str = ""

    observed_facts: List[str] = Field(default_factory=list)
    claims: List[str] = Field(default_factory=list)
    goals: List[str] = Field(default_factory=list)
    decision_options: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    inferences: List[str] = Field(default_factory=list)
    unknowns: List[str] = Field(default_factory=list)
    biases: List[str] = Field(default_factory=list)

    stakeholders: List[str] = Field(default_factory=list)

    clarity_level: float = Field(default=0.0, ge=0.0, le=1.0)
    # v0.9: agency_level removed -- was never wired to anything. See
    # engine/specs/interpretation-spec-v0.9.md Part 4.

    phase: Literal["prepare", "discover", "discern", "challenge", "resolve", "commit"] = "prepare"

    decision: str = ""

    history_summary: str = ""

    def to_state(self) -> ConversationState:
        return ConversationState(**self.model_dump())


class StateUpdateError(Exception):
    """Raised when no provider in the chain could produce a valid state."""

    def __init__(self, message: str, raw_output: Optional[str] = None):
        super().__init__(message)
        self.raw_output = raw_output


# ---------------------------------------------------------------------------
# StateUpdater
# ---------------------------------------------------------------------------
class StateUpdater:
    """
    Given the current ConversationState and a transcript, asks an LLM to
    produce an updated state and returns it as a validated ConversationState.
    """

    SYSTEM_PROMPT = (
        "You maintain a structured ConversationState object for an ongoing "
        "conversation between a user and an assistant.\n\n"
        "You will be given:\n"
        "1. The CURRENT STATE as JSON.\n"
        "2. The CONVERSATION TRANSCRIPT so far.\n\n"
        "Your job is to return an UPDATED STATE, and ONLY the updated state, "
        "as a single JSON object matching this schema exactly:\n"
        f"{json.dumps(ConversationStateSchema.model_json_schema())}\n\n"
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
        "- clarity_level is a float from 0.0 to 1.0 representing how "
        "clearly the problem is understood.\n"
    )

    def __init__(
        self,
        providers: Optional[List[ProviderConfig]] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        clients: Optional[List[LLMClient]] = None,
    ):
        """
        providers: ordered list of ProviderConfig to try (first is primary,
                   rest are fallbacks). Defaults to
                   engine.llm_config.resolve_provider_chain(), which reads
                   LLM_PROVIDER / OPENROUTER_* / OLLAMA_* env vars.
        clients: pass pre-built LLMClient instances (e.g. for testing with a
                 fake), otherwise one is constructed per provider.
        """
        self.providers = providers or resolve_provider_chain()
        self.max_tokens = max_tokens
        self.clients = clients or [LLMClient(p) for p in self.providers]

    def update(
        self,
        current_state: ConversationState,
        transcript: str,
    ) -> ConversationState:
        """
        Tries each configured provider in order and returns a new, validated
        ConversationState from the first one that succeeds. Raises
        StateUpdateError, with every provider's failure reason, if all of
        them fail (network/API error, refusal/content filter, truncated
        output, or schema validation failure).
        """
        current_state_json = json.dumps(asdict(current_state), indent=2)

        user_prompt = (
            f"CURRENT STATE:\n{current_state_json}\n\n"
            f"CONVERSATION TRANSCRIPT:\n{transcript}"
        )

        failures: List[str] = []
        last_raw_output: Optional[str] = None

        for provider, client in zip(self.providers, self.clients):
            try:
                parsed, raw_text = self._call_provider(client, user_prompt)
            except _ProviderFailure as exc:
                failures.append(f"{provider.name}: {exc}")
                last_raw_output = exc.raw_output or last_raw_output
                continue

            return parsed.to_state()

        raise StateUpdateError(
            "All configured LLM providers failed: " + "; ".join(failures),
            raw_output=last_raw_output,
        )

    def _call_provider(self, client: LLMClient, user_prompt: str):
        try:
            response = client.complete_json(
                system_prompt=self.SYSTEM_PROMPT,
                user_prompt=user_prompt,
                max_tokens=self.max_tokens,
            )
        except Exception as exc:  # network/auth/API-level failures
            raise _ProviderFailure(f"API call failed: {exc}") from exc

        raw_text = LLMClient.extract_text(response)
        finish_reason = LLMClient.finish_reason(response)

        if finish_reason == "content_filter":
            raise _ProviderFailure(
                "Model refused to produce a state update for this turn.",
                raw_output=raw_text,
            )
        if finish_reason == "length":
            raise _ProviderFailure(
                "Response was truncated (max_tokens reached) before a "
                "complete state was returned. Try increasing max_tokens.",
                raw_output=raw_text,
            )
        if raw_text is None:
            raise _ProviderFailure(
                "No output found in the API response.", raw_output=str(response)
            )

        try:
            parsed_json = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise _ProviderFailure(
                f"Model output was not valid JSON: {exc}", raw_output=raw_text
            ) from exc

        try:
            parsed = ConversationStateSchema.model_validate(parsed_json)
        except ValidationError as exc:
            raise _ProviderFailure(
                f"Model output failed schema validation: {exc}",
                raw_output=raw_text,
            ) from exc

        return parsed, raw_text


class _ProviderFailure(Exception):
    """Internal: one provider's attempt failed, try the next one."""

    def __init__(self, message: str, raw_output: Optional[str] = None):
        super().__init__(message)
        self.raw_output = raw_output
