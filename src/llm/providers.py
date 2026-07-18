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

PER-COMPONENT PAID MODEL PINNING (2026-07-18, see engine/decisions.md
"Per-component paid model pinning" and its two follow-up entries,
"rebalanced for net savings" and "primary/fallback chain + cheaper
Response model"): production previously pinned ONE model
(`openai/gpt-4o-mini`) uniformly across every component via
`OPENROUTER_MODEL` in fly.toml. Went through three iterations before
landing here -- a three-band split by reasoning depth (reverted: it was
a net cost INCREASE vs gpt-4o-mini, not the savings that was asked
for), then a two-band rebalance (cheap tier for everything but
Response), now a primary/fallback CHAIN per component rather than a
single pinned model, replacing `_resolve_model`'s old
str-returning signature with `_resolve_model_chain` returning an
ordered `List[str]`:

- Shared reasoning tier (Interpretation, Tier2, Judgment, Planner,
  Insight, POM) -- `qwen/qwen3-32b` PRIMARY ($0.08 in / $0.28 out per
  1M, cheaper than the prior `google/gemini-2.5-flash-lite` pin on both
  axes), with `google/gemini-2.5-flash-lite` ($0.10/$0.40) as FALLBACK
  if Qwen3-32B's call fails for any reason (unreachable, timeout,
  malformed response -- anything `call_openrouter` already surfaces as
  `ProviderCallError`). Qwen3 is routed through third-party inference
  providers on OpenRouter rather than a direct-from-lab route, so a
  fallback here is a real reliability hedge, not a formality.
- Response -- `deepseek/deepseek-chat` (DeepSeek V3, $0.20 in / $0.80
  out), replacing `openai/gpt-4.1-mini` ($0.40/$1.60) -- half the price
  on both axes, chosen specifically (not just "the cheapest option")
  for DeepSeek V3's established reputation for natural conversational
  writing quality, since Response's raw output is literally what a
  person reads. No fallback chain here (single model) -- not asked for,
  and Response's user-facing quality is the one dimension this file
  isn't trying to also gate behind an automatic downgrade.

Prices below are per OpenRouter's published per-million-token rates,
gathered via web search on 2026-07-18 (direct fetches to openrouter.ai
and third-party pricing aggregators were blocked by this environment's
egress policy/bot protection at the time -- these are believed accurate
as of that date but were not cross-checked against OpenRouter's own
live model list; re-verify at openrouter.ai/models before leaning on
exact figures for a cost projection):
  qwen/qwen3-32b                $0.08 in / $0.28 out per 1M tokens
  google/gemini-2.5-flash-lite  $0.10 in / $0.40 out per 1M tokens
  deepseek/deepseek-chat        $0.20 in / $0.80 out per 1M tokens
(for reference, the original universal pin, openai/gpt-4o-mini, was
$0.15 in / $0.60 out; the immediately-prior Response pin,
openai/gpt-4.1-mini, was $0.40 in / $1.60 out.)

Considered and declined as the shared-tier primary/fallback:
`nvidia/nemotron-3-super-120b-a12b` ($0.08/$0.45, roughly a wash vs
Qwen3-32B) -- no strong reason to prefer it over Qwen3-32B specifically,
so not added as a third link in the chain; revisit only if Qwen3-32B's
real compliance/reliability turns out worse than Gemini's in practice.

`OPENROUTER_MODEL`, if explicitly set, still overrides EVERY component
uniformly with a single model (no fallback chain) -- unchanged
behavior, since the existing calibration workflows
(worldstate-walkthrough.yml, knowledge-correction-calibration.yml,
pom-computation.yml) depend on being able to force one single model
across an entire run for controlled comparison. The per-component chain
map below is only consulted when no explicit override is set -- which
is now fly.toml's own production configuration (see fly.toml's own
comment on why OPENROUTER_MODEL was removed from `[env]`).

Robustness contract: every call_openrouter call either returns a
non-empty string or raises ProviderCallError -- never any other
exception type, and never an empty/whitespace-only string. This is
enforced explicitly (not just by not crashing) so that a caller looping
over resolve_provider_chain() gets a clean, typed failure on ANY
malformed/incomplete response (missing fields, non-JSON body,
content=None, content="", a request that times out) -- see
tests/test_llm_providers.py for the exact malformed-response cases this
guards against. This contract now also covers the per-component MODEL
chain internally: call_openrouter only raises ProviderCallError once
every model in the resolved chain has failed; a failure on the primary
model that recovers on the fallback is invisible to the caller (returns
normally, same as a first-attempt success).
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


# Per-component paid model pinning (2026-07-18, see module docstring's own
# "PER-COMPONENT PAID MODEL PINNING" section for the full rationale/pricing).
# Keys are exactly the `component` strings each engine.py already passes to
# call_provider/call_openrouter -- Baseline-B2-summary (evaluation harness
# only, never a live request path) is deliberately absent, so it falls
# through to _FALLBACK_CHAIN below like any other unmapped component.
# Values are ORDERED chains -- call_openrouter tries each model in turn,
# only raising ProviderCallError once every model in the chain has failed.
_SHARED_REASONING_CHAIN = ["qwen/qwen3-32b", "google/gemini-2.5-flash-lite"]

_DEFAULT_COMPONENT_MODELS = {
    "Interpretation": _SHARED_REASONING_CHAIN,
    "Tier2": _SHARED_REASONING_CHAIN,
    "Judgment": _SHARED_REASONING_CHAIN,
    "Planner": _SHARED_REASONING_CHAIN,
    "Insight": _SHARED_REASONING_CHAIN,
    "POM": _SHARED_REASONING_CHAIN,
    "Response": ["deepseek/deepseek-chat"],
}

# Same default this file has always used for anything not otherwise pinned
# (OpenRouter's free auto-router -- see module docstring's "SECOND CAVEAT").
_FALLBACK_CHAIN = ["openrouter/free"]


def _resolve_model_chain(component: str) -> List[str]:
    """An explicit OPENROUTER_MODEL env var always wins, applied uniformly
    across every component as a SINGLE model (no fallback chain) --
    unchanged from this file's behavior before per-component pinning
    existed, since the calibration workflows
    (worldstate-walkthrough.yml, knowledge-correction-calibration.yml,
    pom-computation.yml) depend on being able to force one single model
    for a controlled comparison. Only when no override is set does this
    fall through to the per-component default chain map."""
    override = os.environ.get("OPENROUTER_MODEL")
    if override:
        return [override]
    return _DEFAULT_COMPONENT_MODELS.get(component, _FALLBACK_CHAIN)


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


def _call_openrouter_with_model(
    model: str,
    system_prompt: str,
    messages: list,
    schema: dict,
    temperature: float,
    component: str,
    tracker: Optional[UsageTracker],
    api_key: str,
    base_url: str,
) -> str:
    """One HTTP attempt against OpenRouter for a single, already-resolved
    `model` -- the part of call_openrouter's old body that actually talks
    to the network, split out so call_openrouter can retry it across a
    chain of models (see module docstring's "PER-COMPONENT PAID MODEL
    PINNING" section) without duplicating the request/parsing logic.
    Raises ProviderCallError -- see module docstring's robustness
    contract -- never any other exception type."""
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
        raise ProviderCallError(f"OpenRouter request failed ({model}): {exc}") from exc
    latency_ms = (time.monotonic() - start) * 1000

    if not response.ok:
        try:
            detail = response.json().get("error", response.text)
        except ValueError:
            detail = response.text
        raise ProviderCallError(f"OpenRouter returned {response.status_code} ({model}): {detail}")

    try:
        payload = response.json()
    except ValueError as exc:
        raise ProviderCallError(f"OpenRouter response was not valid JSON ({model}): {exc}") from exc

    content = _extract_message_content(payload, ["choices", 0, "message", "content"], "OpenRouter")

    parsed_usage = extract_openai_compatible_usage(payload)
    raw_usage = payload.get("usage")
    _record_usage(tracker, component, "openrouter", model, parsed_usage, raw_usage, latency_ms)

    return content


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

    Tries every model in `_resolve_model_chain(component)` IN ORDER,
    returning on the first success; only raises ProviderCallError once
    every model in the chain has failed (see module docstring's
    "PER-COMPONENT PAID MODEL PINNING" section for why the shared
    reasoning tier has a fallback and Response doesn't).
    """
    base_url = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    api_key = _first_env("OPENROUTER_API_KEY", "LLM_API_KEY")

    if not api_key:
        raise ProviderCallError("OPENROUTER_API_KEY (or LLM_API_KEY) is not set")

    failures: List[str] = []
    for model in _resolve_model_chain(component):
        try:
            return _call_openrouter_with_model(
                model, system_prompt, messages, schema, temperature, component, tracker, api_key, base_url,
            )
        except ProviderCallError as exc:
            failures.append(str(exc))
            continue

    raise ProviderCallError("Every model in the chain failed: " + "; ".join(failures))


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
