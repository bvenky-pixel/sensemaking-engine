"""Tests for src/response/streaming.py's ResponseTextStreamExtractor
(2026-07-22, backlog #233, see engine/decisions.md "Stream Response text
token-by-token")."""

from __future__ import annotations

import json
import random

from src.response.streaming import ResponseTextStreamExtractor


def _stream_full_object(full_json: str, chunk_sizes) -> str:
    """Feeds `full_json` through a fresh extractor in the given chunk
    sizes, returning the concatenated (still JSON-escaped) output."""
    extractor = ResponseTextStreamExtractor()
    out = []
    i = 0
    for size in chunk_sizes:
        out.append(extractor.feed(full_json[i : i + size]))
        i += size
    if i < len(full_json):
        out.append(extractor.feed(full_json[i:]))
    return "".join(out)


def test_extracts_response_text_when_fed_as_one_whole_chunk():
    full = json.dumps({"response_text": "Hello there.", "confidence": 0.6, "options": []})
    extractor = ResponseTextStreamExtractor()
    assert extractor.feed(full) == "Hello there."


def test_extracts_response_text_split_across_many_small_chunks():
    full = json.dumps({"response_text": "What's the real blocker here?", "confidence": 0.6, "options": []})
    out = _stream_full_object(full, [1] * len(full))
    assert out == "What's the real blocker here?"


def test_handles_the_key_marker_itself_split_across_chunk_boundaries():
    full = json.dumps({"response_text": "Short.", "confidence": 0.5, "options": []})
    key_pos = full.index('"response_text"')
    # Split right in the middle of the key name -- the marker only
    # completes on the second chunk.
    split_at = key_pos + 5
    out = _stream_full_object(full, [split_at, len(full) - split_at])
    assert out == "Short."


def test_handles_escaped_quotes_and_backslashes_inside_the_value():
    full = json.dumps({"response_text": 'You called it "real" — literally.', "confidence": 0.5, "options": []})
    out = _stream_full_object(full, [3] * len(full))
    # Raw streamed output is still JSON-escaped (see the class's own
    # docstring) -- unescape the way the real caller's final json.loads
    # would before comparing to the original text.
    assert json.loads(f'"{out}"') == 'You called it "real" — literally.'


def test_handles_escaped_newline_inside_the_value():
    full = json.dumps({"response_text": "Line one.\nLine two.", "confidence": 0.5, "options": []})
    out = _stream_full_object(full, [2] * len(full))
    assert json.loads(f'"{out}"') == "Line one.\nLine two."


def test_stops_emitting_once_the_closing_quote_is_seen():
    full = json.dumps({"response_text": "Done.", "confidence": 0.5, "options": [{"label": "a", "description": "b"}]})
    extractor = ResponseTextStreamExtractor()
    out = extractor.feed(full)
    assert out == "Done."
    # Everything after the closing quote (confidence, options -- never
    # user-facing) must never be emitted, even if fed more later.
    assert extractor.feed("more text that should never appear") == ""


def test_never_streams_anything_if_response_text_key_never_appears():
    """A malformed/unexpected model output (e.g. confidence emitted
    first) must degrade to "nothing streamed," never a crash or garbage
    output -- the eventual real Response still comes from the normal
    json.loads + Pydantic validation path, unaffected."""
    full = json.dumps({"confidence": 0.5, "options": []})
    out = _stream_full_object(full, [1] * len(full))
    assert out == ""


def test_random_chunk_boundaries_always_round_trip_correctly():
    """Property-style check: for many random texts and random chunk
    splits, the streamed (unescaped) output always exactly equals the
    original response_text."""
    rng = random.Random(42)
    samples = [
        "Simple.",
        "What's the \"real\" blocker here?\nReally?",
        "Backslash test: C:\\Users\\test and a \"quote\".",
        "",  # handled by Response's own empty-string rejection upstream, not this class
        "Emoji and unicode: café, 日本語, — em dash.",
    ]
    for text in samples:
        if not text:
            continue  # Response.response_text can't be empty; this class doesn't need to special-case it
        full = json.dumps({"response_text": text, "confidence": 0.7, "options": []})
        sizes = []
        remaining = len(full)
        while remaining > 0:
            n = rng.randint(1, 5)
            sizes.append(n)
            remaining -= n
        out = _stream_full_object(full, sizes)
        assert json.loads(f'"{out}"') == text, f"mismatch for {text!r}"
