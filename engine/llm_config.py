"""
Provider configuration for the LLM layer.

Both OpenRouter and Ollama expose an OpenAI-compatible `/v1/chat/completions`
endpoint, so a single client implementation (see llm_client.py) can talk to
either one -- only the base_url/api_key/model differ. That's what makes the
API key "interchangeable": switching providers, or rotating a key, is an env
var change, not a code change.

LLM_PROVIDER selects the primary provider ("openrouter" or "ollama", default
"openrouter"). Whichever provider isn't primary is kept as an automatic
fallback so a StateUpdater call can survive an outage, an expired key, or a
missing local Ollama install without crashing the whole turn.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - python-dotenv is a soft dependency
    pass


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    base_url: str
    api_key: str
    model: str


def _first_env(*names: str) -> Optional[str]:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def openrouter_config() -> ProviderConfig:
    return ProviderConfig(
        name="openrouter",
        base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        # LLM_API_KEY is a generic fallback so a single env var can be reused
        # across providers if that's all the deployment sets. Falls back to
        # a placeholder (rather than "") so client construction never fails
        # just because a key is missing -- the actual API call will fail
        # with an auth error instead, which the provider fallback chain
        # already handles.
        api_key=_first_env("OPENROUTER_API_KEY", "LLM_API_KEY") or "unset",
        model=os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
    )


def ollama_config() -> ProviderConfig:
    return ProviderConfig(
        name="ollama",
        base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        # Ollama doesn't check the key, but the OpenAI SDK requires a
        # non-empty string to construct a client.
        api_key=_first_env("OLLAMA_API_KEY", "LLM_API_KEY") or "ollama",
        model=os.environ.get("OLLAMA_MODEL", "llama3.1"),
    )


_PROVIDER_BUILDERS = {
    "openrouter": openrouter_config,
    "ollama": ollama_config,
}


def resolve_provider_chain(primary: Optional[str] = None) -> List[ProviderConfig]:
    """
    Returns an ordered list of provider configs to try: the configured
    primary first, then every other known provider as a fallback. Callers
    should try each in order and only move to the next on failure.
    """
    primary_name = (primary or os.environ.get("LLM_PROVIDER", "openrouter")).lower()

    if primary_name not in _PROVIDER_BUILDERS:
        raise ValueError(
            f"Unknown LLM_PROVIDER '{primary_name}'; expected one of "
            f"{sorted(_PROVIDER_BUILDERS)}"
        )

    chain = [_PROVIDER_BUILDERS[primary_name]()]
    chain.extend(
        builder() for name, builder in _PROVIDER_BUILDERS.items() if name != primary_name
    )
    return chain
