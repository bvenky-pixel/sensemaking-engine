"""
Provider configuration and raw HTTP calls for the Interpretation Engine.

OpenRouter is the primary provider; Ollama is kept as an automatic local
fallback. Ollama (llama3.2:3b) was the original v1.0 provider, and every
grounding-filter threshold in engine.py was empirically calibrated against
its specific fabrication patterns (see engine/decisions.md) -- keeping it
as a fallback means a local Ollama install still works exactly as before
if OpenRouter is unreachable.

IMPORTANT CAVEAT (see engine/decisions.md "Ollama stays for MVP, Claude
swap deferred deliberately" and the v1.0 freeze entries): the six v1.0
exit criteria and every grounding threshold were validated via live n=10
testing against Ollama's output specifically. Making OpenRouter the
primary provider means the model most turns actually run against has NOT
been through that same validation. Re-run the n=10 methodology against
whatever OPENROUTER_MODEL is configured before trusting it the way the
Ollama path is trusted.
"""

from __future__ import annotations

import json
import os
from typing import List, Optional

import requests

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - python-dotenv is a soft dependency
    pass


class ProviderCallError(Exception):
    """Raised when a single provider's call fails; caller should try the next one."""


def _first_env(*names: str) -> Optional[str]:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def call_openrouter(system_prompt: str, messages: list, schema: dict, temperature: float) -> str:
    """
    POSTs to OpenRouter's OpenAI-compatible /chat/completions endpoint.
    Uses plain JSON mode (response_format: json_object) rather than OpenAI's
    strict json_schema mode -- strict mode requires every object in the
    schema (including nested ones) to explicitly set
    `additionalProperties: false`, which Pydantic's model_json_schema()
    doesn't add, and not every model routed through OpenRouter supports it
    anyway. The schema is instead appended to the system prompt as a text
    hint, and the caller (engine.py) already does full Pydantic validation
    on the result -- same belt-and-suspenders pattern as
    engine/state_updater.py on the main-line branch. Returns the raw
    assistant text content.
    """
    base_url = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    api_key = _first_env("OPENROUTER_API_KEY", "LLM_API_KEY")
    model = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")

    if not api_key:
        raise ProviderCallError("OPENROUTER_API_KEY (or LLM_API_KEY) is not set")

    schema_hint = (
        "\n\nReturn ONLY a single JSON object matching this schema exactly "
        f"(no prose, no markdown fences):\n{json.dumps(schema)}"
    )

    try:
        response = requests.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [{"role": "system", "content": system_prompt + schema_hint}] + messages,
                "temperature": temperature,
                "response_format": {"type": "json_object"},
            },
            timeout=180,
        )
    except requests.RequestException as exc:
        raise ProviderCallError(f"OpenRouter request failed: {exc}") from exc

    if not response.ok:
        try:
            detail = response.json().get("error", response.text)
        except ValueError:
            detail = response.text
        raise ProviderCallError(f"OpenRouter returned {response.status_code}: {detail}")

    try:
        return response.json()["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, ValueError) as exc:
        raise ProviderCallError(f"Unexpected OpenRouter response shape: {exc}") from exc


def call_ollama(system_prompt: str, messages: list, schema: dict, temperature: float) -> str:
    """
    POSTs to a local Ollama's native /api/chat endpoint, passing the real
    JSON schema so generation is grammar-constrained (requires Ollama >=
    0.3.0) -- this is the exact call the v1.0 interpretation layer was
    calibrated against. Returns the raw assistant text content.
    """
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    model = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")

    try:
        response = requests.post(
            f"{base_url}/api/chat",
            json={
                "model": model,
                "system": system_prompt,
                "messages": messages,
                "stream": False,
                "format": schema,
                "options": {"temperature": temperature},
            },
            timeout=180,
        )
    except requests.RequestException as exc:
        raise ProviderCallError(f"Ollama request failed: {exc}") from exc

    if not response.ok:
        try:
            detail = response.json().get("error", response.text)
        except ValueError:
            detail = response.text
        raise ProviderCallError(f"Ollama returned {response.status_code}: {detail}")

    try:
        return response.json()["message"]["content"].strip()
    except (KeyError, ValueError) as exc:
        raise ProviderCallError(f"Unexpected Ollama response shape: {exc}") from exc


_PROVIDER_CALLERS = {
    "openrouter": call_openrouter,
    "ollama": call_ollama,
}


def resolve_provider_chain() -> List[str]:
    """Primary provider (LLM_PROVIDER env var, default "openrouter") first,
    then every other known provider as a fallback."""
    primary = os.environ.get("LLM_PROVIDER", "openrouter").lower()
    if primary not in _PROVIDER_CALLERS:
        raise ValueError(
            f"Unknown LLM_PROVIDER '{primary}'; expected one of {sorted(_PROVIDER_CALLERS)}"
        )
    chain = [primary]
    chain.extend(name for name in _PROVIDER_CALLERS if name != primary)
    return chain


def call_provider(name: str, system_prompt: str, messages: list, schema: dict, temperature: float) -> str:
    return _PROVIDER_CALLERS[name](system_prompt, messages, schema, temperature)
