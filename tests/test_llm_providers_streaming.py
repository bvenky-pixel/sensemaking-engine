"""Tests for src/llm/providers.py's streaming path (`on_delta`, 2026-07-22,
backlog #233, see engine/decisions.md "Stream Response text
token-by-token"). Separate file from tests/test_llm_providers.py's own
non-streaming coverage, same "one concern per file" split this codebase
already uses elsewhere (e.g. test_response_streaming.py alongside
test_response_engine.py)."""

from __future__ import annotations

import json

import pytest

from src.llm.providers import ProviderCallError, call_openrouter

SYSTEM_PROMPT = "system"
MESSAGES = [{"role": "user", "content": "hi"}]
SCHEMA = {"type": "object"}
TEMPERATURE = 0.5


class _FakeStreamingResponse:
    """Mimics requests.Response enough for _consume_openrouter_stream:
    .ok, .iter_lines() yielding raw SSE lines (some blank, matching a
    real server's keep-alive blank lines between events)."""

    def __init__(self, lines):
        self.ok = True
        self.status_code = 200
        self._lines = lines

    def iter_lines(self, decode_unicode=True):
        yield from self._lines


def _sse_lines(*chunks_and_final_usage):
    """Builds SSE `data: {...}` lines for a sequence of content deltas,
    ending with a usage-only chunk (no `choices`) then `data: [DONE]` --
    the exact shape OpenRouter's own streaming docs specify when
    stream_options.include_usage is set."""
    lines = []
    for delta in chunks_and_final_usage:
        lines.append(f"data: {json.dumps({'choices': [{'delta': {'content': delta}}]})}")
        lines.append("")  # SSE frames are blank-line-terminated
    lines.append(f"data: {json.dumps({'choices': [], 'usage': {'prompt_tokens': 10, 'completion_tokens': 4}})}")
    lines.append("data: [DONE]")
    return lines


@pytest.fixture(autouse=True)
def _set_openrouter_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")


def test_on_delta_receives_each_fragment_in_order(monkeypatch):
    seen = []
    monkeypatch.setattr(
        "src.llm.providers.requests.post",
        lambda *a, **k: _FakeStreamingResponse(_sse_lines('{"response_text": ', '"Hello', " world.\"}")),
    )
    result = call_openrouter(SYSTEM_PROMPT, MESSAGES, SCHEMA, TEMPERATURE, on_delta=seen.append)
    assert seen == ['{"response_text": ', '"Hello', ' world."}']
    assert result == '{"response_text": "Hello world."}'


def test_streaming_request_sets_stream_true_and_include_usage(monkeypatch):
    captured = {}

    def _spy_post(url, headers, json, timeout, **kwargs):
        captured["json"] = json
        captured["kwargs"] = kwargs
        return _FakeStreamingResponse(_sse_lines('{"response_text": "hi"}'))

    monkeypatch.setattr("src.llm.providers.requests.post", _spy_post)
    call_openrouter(SYSTEM_PROMPT, MESSAGES, SCHEMA, TEMPERATURE, on_delta=lambda d: None)

    assert captured["json"]["stream"] is True
    assert captured["json"]["stream_options"] == {"include_usage": True}
    assert captured["kwargs"]["stream"] is True


def test_non_streaming_request_never_sets_stream_kwarg(monkeypatch):
    """Direct regression test for backward compatibility: every call
    site/test double that mocks requests.post without an on_delta
    argument must see the exact same request shape as before #233 --
    no `stream` key in the JSON body, no `stream=` kwarg to requests.post."""
    captured = {}

    def _fake_post(url, headers, json, timeout, **kwargs):
        captured["json"] = json
        captured["kwargs"] = kwargs
        class _Resp:
            ok = True
            status_code = 200
            def json(self):
                return {"choices": [{"message": {"content": "hi"}}]}
        return _Resp()

    monkeypatch.setattr("src.llm.providers.requests.post", _fake_post)
    call_openrouter(SYSTEM_PROMPT, MESSAGES, SCHEMA, TEMPERATURE)

    assert "stream" not in captured["json"]
    assert "stream_options" not in captured["json"]
    assert captured["kwargs"] == {}


def test_empty_streamed_content_raises_provider_call_error(monkeypatch):
    monkeypatch.setattr(
        "src.llm.providers.requests.post",
        lambda *a, **k: _FakeStreamingResponse(_sse_lines()),
    )
    with pytest.raises(ProviderCallError, match="empty"):
        call_openrouter(SYSTEM_PROMPT, MESSAGES, SCHEMA, TEMPERATURE, on_delta=lambda d: None)


def test_usage_only_final_chunk_does_not_get_forwarded_to_on_delta(monkeypatch):
    """The final usage-only chunk has no `choices` at all -- must not
    call on_delta with anything for it (there's no content to stream)."""
    seen = []
    monkeypatch.setattr(
        "src.llm.providers.requests.post",
        lambda *a, **k: _FakeStreamingResponse(_sse_lines('{"response_text": "ok"}')),
    )
    call_openrouter(SYSTEM_PROMPT, MESSAGES, SCHEMA, TEMPERATURE, on_delta=seen.append)
    assert all(chunk for chunk in seen)  # every forwarded chunk is real, non-empty content
    assert "".join(seen) == '{"response_text": "ok"}'


def test_malformed_sse_line_is_skipped_not_fatal(monkeypatch):
    lines = ["data: not valid json", "", f"data: {json.dumps({'choices': [{'delta': {'content': 'ok'}}]})}", "", "data: [DONE]"]
    monkeypatch.setattr("src.llm.providers.requests.post", lambda *a, **k: _FakeStreamingResponse(lines))
    result = call_openrouter(SYSTEM_PROMPT, MESSAGES, SCHEMA, TEMPERATURE, on_delta=lambda d: None)
    assert result == "ok"
