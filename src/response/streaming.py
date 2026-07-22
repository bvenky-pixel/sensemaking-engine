"""
Incremental extractor for Response's `response_text` field specifically
(2026-07-22, backlog #233, see engine/decisions.md "Stream Response text
token-by-token").

Response's provider call still asks for the same structured JSON object
it always has (`response_format: json_object`, unchanged prompt/schema --
see src/response/engine.py's own module docstring on why that's
deliberately NOT being restructured just to make streaming easier). What
changes is that the model's raw text now arrives as it's generated
rather than all at once, and this class picks the `response_text` STRING
VALUE specifically out of that growing, not-yet-valid-JSON text, so the
frontend can show a person's words as they're written instead of a
static loading label until the whole object (response_text, confidence,
options -- none of which the person needs to see arrive early) is done.

Scans for the literal `"response_text"` key substring wherever it
appears in the growing text, so it works regardless of field order --
Response's own field order (see src/response/schema.py) just makes
`response_text` the common case of "appears early," not a hard
requirement. What genuinely IS a real assumption, not a guarantee: that
the key appears at all, quoted exactly that way, before any prior text
that could coincidentally contain the same substring (not a realistic
risk in a JSON object emitted from this exact schema). If a model's
output is malformed enough that the key never appears as expected, this
class simply never starts streaming for that turn (feed() keeps
returning "") and the person sees nothing until the final, already-
validated Response arrives from POST /messages -- exactly today's non-
streaming experience, not a broken one. Nothing about the ACTUAL parsed
Response object depends on this class being right; run_response_generator
still does full
json.loads + Pydantic validation on the complete accumulated text
afterward, unchanged.
"""

from __future__ import annotations

_KEY_MARKER = '"response_text"'


class ResponseTextStreamExtractor:
    """Feed raw text deltas in as they arrive (`feed`); each call returns
    the new substring of `response_text`'s value that just became
    available, or "" if there's nothing new to show yet (still looking
    for the key, or already finished). Handles a JSON string value's own
    escaping (`\\"`, `\\\\`) so an escaped quote inside the text doesn't
    look like the closing quote."""

    def __init__(self) -> None:
        self._buffer = ""  # only ever holds pre-value text (before the opening quote), bounded and small
        self._in_value = False
        self._done = False
        self._escaped = False

    def feed(self, chunk: str) -> str:
        if self._done or not chunk:
            return ""

        if not self._in_value:
            self._buffer += chunk
            key_pos = self._buffer.find(_KEY_MARKER)
            if key_pos == -1:
                # Keep the buffer from growing unboundedly while still
                # scanning -- only the tail could possibly complete the
                # marker on the next chunk.
                self._buffer = self._buffer[-len(_KEY_MARKER):]
                return ""
            after_key = self._buffer[key_pos + len(_KEY_MARKER):]
            colon_pos = after_key.find(":")
            quote_pos = after_key.find('"', colon_pos) if colon_pos != -1 else -1
            if quote_pos == -1:
                # Marker found but its ":" and/or opening value-quote
                # hasn't arrived yet -- wait for more chunks. Small,
                # bounded buffer (a key name plus a few punctuation/
                # whitespace characters at most).
                self._buffer = self._buffer[key_pos:]
                return ""
            self._in_value = True
            remainder = after_key[quote_pos + 1:]
            self._buffer = ""
            chunk = remainder  # fall through to value-scanning below with whatever's left of this chunk

        emitted = []
        i = 0
        while i < len(chunk):
            char = chunk[i]
            if self._escaped:
                emitted.append(char)
                self._escaped = False
            elif char == "\\":
                self._escaped = True
                emitted.append(char)
            elif char == '"':
                self._done = True
                self._in_value = False
                break
            else:
                emitted.append(char)
            i += 1

        if not emitted:
            return ""

        # json.loads will unescape properly at the very end (engine.py's
        # existing parse of the full accumulated text) -- what streams
        # live here is the raw, still-escaped JSON text, so `\n` shows as
        # two literal characters mid-stream rather than a real newline
        # until the final render replaces it. A cosmetic gap during the
        # few seconds of streaming, not a correctness one -- corrected
        # the instant the real Response object lands.
        return "".join(emitted)
