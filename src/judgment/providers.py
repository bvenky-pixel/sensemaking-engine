"""
Provider configuration and raw HTTP calls for the Judgment Engine.

Deliberately DUPLICATED from src/interpretation/providers.py (same
OpenRouter-primary/Ollama-fallback mechanics, same env vars) rather than
imported -- same reasoning as src/state/builder.py's duplicated
_word_overlap: interpretation/* is frozen v1.0, and this avoids any
dependency on / risk to it for what's otherwise generic HTTP/provider
plumbing. Reuses the same env vars (OPENROUTER_API_KEY, OPENROUTER_MODEL,
OLLAMA_BASE_URL, OLLAMA_MODEL, LLM_PROVIDER) rather than introducing a
separate Judgment-specific config axis -- one key/model configuration
works for both layers by default.

Judgment has no prior calibration history the way Interpretation's
grounding filters do (those went through live n=10/n=20 testing against
Ollama specifically) -- this is a brand-new component, untested against
any live model yet. Treat its output as unvalidated until it's actually
exercised the way Interpretation was.
"""

from __future__ import annotations

import json
import os
import time
from typing import List, Optional

import requests

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - python-dotenv is a soft dependency
    pass

from src.instrumentation.usage import (
    UsageTracker,
    build_usage,
    extract_openai_compatible_usage,
    extract_ollama_usage,
)


class ProviderCallError(Exception):
    """Raised when a single provider's call fails; caller should try the next one."""


def _first_env(*names: str) -> Optional[str]:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def _record_usage(
    tracker: Optional[UsageTracker],
    component: str,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: float,
) -> None:
    """Best-effort instrumentation -- must never affect the actual call.
    Any failure here is swallowed, not raised."""
    if tracker is None:
        return
    try:
        tracker.record(build_usage(component, provider, model, input_tokens, output_tokens, latency_ms))
    except Exception:
        pass


def call_openrouter(
    system_prompt: str,
    messages: list,
    schema: dict,
    temperature: float,
    component: str = "unknown",
    tracker: Optional[UsageTracker] = None,
) -> str:
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
    model = os.environ.get("OPENROUTER_MODEL", "nvidia/nemotron-3-ultra-550b-a55b:free")

    if not api_key:
        raise ProviderCallError("OPENROUTER_API_KEY (or LLM_API_KEY) is not set")

    schema_hint = (
        "\n\nReturn ONLY a single JSON object matching this schema exactly "
        f"(no prose, no markdown fences):\n{json.dumps(schema)}"
    )

    start = time.monotonic()
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
    latency_ms = (time.monotonic() - start) * 1000

    if not response.ok:
        try:
            detail = response.json().get("error", response.text)
        except ValueError:
            detail = response.text
        raise ProviderCallError(f"OpenRouter returned {response.status_code}: {detail}")

    try:
        payload = response.json()
        content = payload["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, ValueError) as exc:
        raise ProviderCallError(f"Unexpected OpenRouter response shape: {exc}") from exc

    input_tokens, output_tokens = extract_openai_compatible_usage(payload)
    _record_usage(tracker, component, "openrouter", model, input_tokens, output_tokens, latency_ms)

    return content


def call_ollama(
    system_prompt: str,
    messages: list,
    schema: dict,
    temperature: float,
    component: str = "unknown",
    tracker: Optional[UsageTracker] = None,
) -> str:
    """
    POSTs to a local Ollama's native /api/chat endpoint, passing the real
    JSON schema so generation is grammar-constrained (requires Ollama >=
    0.3.0) -- same mechanism src/interpretation/providers.py's call_ollama
    uses. Returns the raw assistant text content.
    """
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    model = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")

    start = time.monotonic()
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
    latency_ms = (time.monotonic() - start) * 1000

    if not response.ok:
        try:
            detail = response.json().get("error", response.text)
        except ValueError:
            detail = response.text
        raise ProviderCallError(f"Ollama returned {response.status_code}: {detail}")

    try:
        payload = response.json()
        content = payload["message"]["content"].strip()
    except (KeyError, ValueError) as exc:
        raise ProviderCallError(f"Unexpected Ollama response shape: {exc}") from exc

    input_tokens, output_tokens = extract_ollama_usage(payload)
    _record_usage(tracker, component, "ollama", model, input_tokens, output_tokens, latency_ms)

    return content


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


def call_provider(
    name: str,
    system_prompt: str,
    messages: list,
    schema: dict,
    temperature: float,
    component: str = "unknown",
    tracker: Optional[UsageTracker] = None,
) -> str:
    return _PROVIDER_CALLERS[name](
        system_prompt, messages, schema, temperature, component=component, tracker=tracker
    )
