"""
Provider configuration and raw HTTP calls -- OpenRouter is the sole LLM
provider -- shared by every layer that makes an LLM call: Interpretation
(src/interpretation/engine.py), Judgment (src/judgment/engine.py),
Planner (src/planner/engine.py), Response (src/response/engine.py), and
the evaluation harness (src/evaluation/baselines.py).

Previously this module's logic was DUPLICATED verbatim between
src/interpretation/providers.py and src/judgment/providers.py, on the
reasoning that interpretation/* is frozen v1.0 and duplicating avoided
any dependency on/risk to it. That reasoning applied to protecting
frozen grounding-filter logic in engine.py, not to this file -- this is
raw HTTP/parsing plumbing with no calibration-specific behavior, so it
belongs in one place, same as src/instrumentation/ (new, independent
infrastructure belonging to neither package). Consolidated here after a
real bug -- a malformed OpenRouter response with content=None crashed
with an unhandled AttributeError instead of a caught ProviderCallError --
was found in BOTH duplicated copies during the Judgment v2 evaluation
smoke test (see engine/decisions.md). `src/interpretation/providers.py`
and `src/judgment/providers.py` no longer exist; both engine.py files and
src/evaluation/baselines.py import directly from here.

REMOVED: a local Ollama fallback used to sit behind OpenRouter here (see
engine/decisions.md "Ollama stays for MVP, Claude swap deferred
deliberately" for its original rationale). It was pulled out entirely
(see engine/decisions.md "Ollama removed, OpenRouter-only") after the
validation experiment showed the automatic openrouter->ollama fallback
firing under sustained free-tier rate-limit pressure and producing
severely degraded output at whichever stage fell back to it -- a silent
reliability problem, not a safety net. IMPORTANT CAVEAT carried over
from that era: the six v1.0 exit criteria and every grounding threshold
in src/interpretation/engine.py were validated via live n=10 testing
against Ollama's output (llama3.2:3b) specifically. The model actually
configured via OPENROUTER_MODEL has never been through that same
validation -- re-run the n=10 methodology against it before trusting it
the way the old Ollama path was trusted.

SECOND CAVEAT, specific to the default `openrouter/free` (see
engine/decisions.md "Switch default to OpenRouter's free-model auto-
router"): this is NOT a single pinned model -- it's OpenRouter's own
router that randomly selects among whatever free models are currently
available, per request. That means two calls in the same run (even two
calls in the same conversation turn) can silently be answered by two
different underlying models. This directly conflicts with the "model
invariance" control the Judgment v2 evaluation design
(engine/specs/judgment-v2-evaluation-design.md Sec. 1) depends on --
pin OPENROUTER_MODEL to one specific `:free`-suffixed model instead of
`openrouter/free` before running that evaluation again. (Pinning to a
single free model has its own documented failure mode -- see
engine/decisions.md -- that specific model getting rate-limited harder
than the rotating pool as a whole; `openrouter/free` is the default for
every other kind of run for exactly that reason.)

Robustness contract: every call_openrouter call either returns a
non-empty string or raises ProviderCallError -- never any other
exception type, and never an empty/whitespace-only string. This is
enforced explicitly (not just by not crashing) so that a caller looping
over resolve_provider_chain() gets a clean, typed failure on ANY
malformed/incomplete response (missing fields, non-JSON body,
content=None, content="", a request that times out) -- see
tests/test_llm_providers.py for the exact malformed-response cases this
guards against.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, List, Optional

import requests

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - python-dotenv is a soft dependency
    pass

from src.instrumentation.usage import (
    ParsedUsage,
    UsageTracker,
    build_usage,
    extract_openai_compatible_usage,
)


class ProviderCallError(Exception):
    """Raised when a single provider's call fails for any reason --
    unreachable, timed out, non-2xx, or a 2xx response whose body is
    missing, malformed, or empty. The caller should try the next
    provider in the chain; this is the ONLY exception type
    call_openrouter ever raises."""


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
    parsed: ParsedUsage,
    raw_usage: Optional[dict],
    latency_ms: float,
) -> None:
    """Best-effort instrumentation -- must never affect the actual call.
    Any failure here is swallowed, not raised."""
    if tracker is None:
        return
    try:
        tracker.record(
            build_usage(
                component,
                provider,
                model,
                parsed.prompt_tokens,
                parsed.completion_tokens,
                latency_ms,
                reasoning_tokens=parsed.reasoning_tokens,
                cached_tokens=parsed.cached_tokens,
                raw_usage=raw_usage,
            )
        )
    except Exception:
        pass


def _extract_message_content(payload: Any, path: List[Any], provider_name: str) -> str:
    """Walks `payload` through `path` (a sequence of dict keys / list
    indices) to reach the assistant's text content, raising
    ProviderCallError -- not a bare KeyError/IndexError/TypeError/
    AttributeError -- for every way that walk can fail: a missing key,
    wrong-shaped payload (e.g. a list where a dict was expected), or a
    content value that is present but None or not a string. Also rejects
    an empty/whitespace-only string, since that's just as useless to the
    caller as a missing one -- both are "this provider gave us nothing
    usable," not different failure modes."""
    node = payload
    try:
        for step in path:
            node = node[step]
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderCallError(f"Unexpected {provider_name} response shape: {exc}") from exc

    if not isinstance(node, str) or not node.strip():
        raise ProviderCallError(
            f"{provider_name} response content was empty or not a string (got {type(node).__name__})"
        )

    return node.strip()


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
    assistant text content, or raises ProviderCallError -- see module
    docstring's robustness contract.
    """
    base_url = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    api_key = _first_env("OPENROUTER_API_KEY", "LLM_API_KEY")
    model = os.environ.get("OPENROUTER_MODEL", "openrouter/free")

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
        # Covers connection errors AND timeouts -- requests.exceptions.Timeout
        # is itself a RequestException subclass.
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
    except ValueError as exc:
        raise ProviderCallError(f"OpenRouter response was not valid JSON: {exc}") from exc

    content = _extract_message_content(payload, ["choices", 0, "message", "content"], "OpenRouter")

    parsed_usage = extract_openai_compatible_usage(payload)
    raw_usage = payload.get("usage")
    _record_usage(tracker, component, "openrouter", model, parsed_usage, raw_usage, latency_ms)

    return content


_PROVIDER_CALLERS = {
    "openrouter": call_openrouter,
}


def resolve_provider_chain() -> List[str]:
    """Returns the configured provider as a single-element chain (LLM_PROVIDER
    env var, default "openrouter" -- the only registered provider today).
    Kept as a list, and callers still loop over it, so a second provider can
    be registered here again later without changing any call site."""
    primary = os.environ.get("LLM_PROVIDER", "openrouter").lower()
    if primary not in _PROVIDER_CALLERS:
        raise ValueError(
            f"Unknown LLM_PROVIDER '{primary}'; expected one of {sorted(_PROVIDER_CALLERS)}"
        )
    return [primary]


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
