"""
Thin OpenAI-compatible chat client, shared by every provider.

OpenRouter and Ollama both implement the OpenAI `/v1/chat/completions`
contract, so this one class is all either of them needs -- provider
differences live entirely in ProviderConfig (engine/llm_config.py).
"""

from __future__ import annotations

from typing import Optional

try:
    from openai import OpenAI
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "The 'openai' package is required for LLMClient (it's also the "
        "client used to talk to OpenRouter and Ollama). Install it with "
        "`pip install openai`."
    ) from exc

from engine.llm_config import ProviderConfig


class LLMClient:
    """Wraps a single provider's OpenAI-compatible chat completions endpoint."""

    def __init__(self, provider: ProviderConfig):
        self.provider = provider
        self._client = OpenAI(base_url=provider.base_url, api_key=provider.api_key)

    def complete_json(self, system_prompt: str, user_prompt: str, max_tokens: int):
        """
        Sends a chat completion request asking for a JSON object back.
        Returns the raw response object; callers are responsible for
        extracting/validating the content (see StateUpdater).
        """
        return self._client.chat.completions.create(
            model=self.provider.model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )

    @staticmethod
    def extract_text(response) -> Optional[str]:
        """Best-effort extraction of the assistant's text content."""
        choices = getattr(response, "choices", None) or []
        if not choices:
            return None
        message = getattr(choices[0], "message", None)
        return getattr(message, "content", None) if message else None

    @staticmethod
    def finish_reason(response) -> Optional[str]:
        choices = getattr(response, "choices", None) or []
        if not choices:
            return None
        return getattr(choices[0], "finish_reason", None)
