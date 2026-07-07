"""
Regression tests for src/llm/providers.py -- the shared provider layer
(consolidated from the formerly-duplicated src/interpretation/providers.py
and src/judgment/providers.py after a real bug was found in both copies:
an OpenRouter response with content=None crashed with an unhandled
AttributeError instead of a caught ProviderCallError, killing the whole
process instead of falling back to the next provider).

Contract under test (see src/llm/providers.py's module docstring):
call_openrouter either returns a non-empty string or raises
ProviderCallError -- never any other exception, never an empty string.
Covers every way a "successful" (2xx) HTTP response can still be
useless: missing fields, content=None, invalid JSON, and empty/
whitespace-only content, plus a genuine request timeout, then verifies
resolve_provider_chain + call_provider surface that failure as a clean
ProviderCallError rather than propagating something call_provider's
caller can't catch.

All deterministic -- requests.post is mocked, no real HTTP.
"""

from __future__ import annotations

import json

import pytest
import requests

from src.llm.providers import (
    ProviderCallError,
    call_openrouter,
    call_provider,
    resolve_provider_chain,
)

SYSTEM_PROMPT = "system"
MESSAGES = [{"role": "user", "content": "hi"}]
SCHEMA = {"type": "object"}
TEMPERATURE = 0.15


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None, text="", json_raises=False):
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self._json_data = json_data
        self.text = text
        self._json_raises = json_raises

    def json(self):
        if self._json_raises:
            raise ValueError("Expecting value: line 1 column 1 (char 0)")
        return self._json_data


@pytest.fixture(autouse=True)
def _set_openrouter_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")


# --- call_openrouter: every malformed-response case must become ProviderCallError ---


def test_openrouter_missing_choices_key_raises_provider_call_error(monkeypatch):
    monkeypatch.setattr(
        "src.llm.providers.requests.post",
        lambda *a, **k: _FakeResponse(json_data={"id": "abc"}),  # no "choices" at all
    )
    with pytest.raises(ProviderCallError, match="Unexpected OpenRouter response shape"):
        call_openrouter(SYSTEM_PROMPT, MESSAGES, SCHEMA, TEMPERATURE)


def test_openrouter_content_none_raises_provider_call_error(monkeypatch):
    monkeypatch.setattr(
        "src.llm.providers.requests.post",
        lambda *a, **k: _FakeResponse(
            json_data={"choices": [{"message": {"content": None}}]}
        ),
    )
    with pytest.raises(ProviderCallError, match="empty or not a string"):
        call_openrouter(SYSTEM_PROMPT, MESSAGES, SCHEMA, TEMPERATURE)


def test_openrouter_invalid_json_raises_provider_call_error(monkeypatch):
    monkeypatch.setattr(
        "src.llm.providers.requests.post",
        lambda *a, **k: _FakeResponse(json_raises=True, text="not json"),
    )
    with pytest.raises(ProviderCallError, match="not valid JSON"):
        call_openrouter(SYSTEM_PROMPT, MESSAGES, SCHEMA, TEMPERATURE)


def test_openrouter_empty_string_content_raises_provider_call_error(monkeypatch):
    monkeypatch.setattr(
        "src.llm.providers.requests.post",
        lambda *a, **k: _FakeResponse(
            json_data={"choices": [{"message": {"content": "   "}}]}
        ),
    )
    with pytest.raises(ProviderCallError, match="empty or not a string"):
        call_openrouter(SYSTEM_PROMPT, MESSAGES, SCHEMA, TEMPERATURE)


def test_openrouter_timeout_raises_provider_call_error(monkeypatch):
    def _raise_timeout(*a, **k):
        raise requests.exceptions.Timeout("timed out after 180s")

    monkeypatch.setattr("src.llm.providers.requests.post", _raise_timeout)
    with pytest.raises(ProviderCallError, match="request failed"):
        call_openrouter(SYSTEM_PROMPT, MESSAGES, SCHEMA, TEMPERATURE)


def test_openrouter_valid_response_returns_stripped_content(monkeypatch):
    monkeypatch.setattr(
        "src.llm.providers.requests.post",
        lambda *a, **k: _FakeResponse(
            json_data={"choices": [{"message": {"content": "  {\"ok\": true}  "}}]}
        ),
    )
    result = call_openrouter(SYSTEM_PROMPT, MESSAGES, SCHEMA, TEMPERATURE)
    assert result == '{"ok": true}'


# --- Provider chain: single-provider today, but call_provider's caller ---
# must still see a clean ProviderCallError (not some other exception) for
# every one of the malformed-response categories above.


@pytest.mark.parametrize(
    "broken_openrouter_response",
    [
        _FakeResponse(json_data={"id": "no choices key"}),
        _FakeResponse(json_data={"choices": [{"message": {"content": None}}]}),
        _FakeResponse(json_raises=True, text="not json"),
        _FakeResponse(json_data={"choices": [{"message": {"content": "   "}}]}),
    ],
    ids=["missing_choices", "content_none", "invalid_json", "empty_string"],
)
def test_provider_chain_surfaces_provider_call_error_for_each_malformed_response(
    monkeypatch, broken_openrouter_response
):
    monkeypatch.setattr(
        "src.llm.providers.requests.post", lambda *a, **k: broken_openrouter_response
    )
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")

    failures = []
    result = None
    for provider_name in resolve_provider_chain():
        try:
            result = call_provider(provider_name, SYSTEM_PROMPT, MESSAGES, SCHEMA, TEMPERATURE)
            break
        except ProviderCallError as exc:
            failures.append(f"{provider_name}: {exc}")
            continue

    assert result is None
    assert len(failures) == 1
    assert failures[0].startswith("openrouter:")


def test_provider_chain_surfaces_provider_call_error_after_timeout(monkeypatch):
    def _raise_timeout(*a, **k):
        raise requests.exceptions.Timeout("timed out")

    monkeypatch.setattr("src.llm.providers.requests.post", _raise_timeout)
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")

    failures = []
    result = None
    for provider_name in resolve_provider_chain():
        try:
            result = call_provider(provider_name, SYSTEM_PROMPT, MESSAGES, SCHEMA, TEMPERATURE)
            break
        except ProviderCallError as exc:
            failures.append(f"{provider_name}: {exc}")
            continue

    assert result is None
    assert len(failures) == 1


def test_resolve_provider_chain_is_single_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    assert resolve_provider_chain() == ["openrouter"]


def test_resolve_provider_chain_rejects_unknown_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
        resolve_provider_chain()
