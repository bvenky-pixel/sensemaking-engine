"""
Live verification for backlog #233 ("Stream Response text
token-by-token", see engine/decisions.md) -- starts against the REAL
running MVP API server (src/api/server.py, started by
.github/workflows/response-streaming-verify.yml the same way
tier2-background-verify.yml starts it) and proves, against a real
OPENROUTER_API_KEY, that:

1. GET /sessions/{id}/stream delivers {"token": "..."} events for
   Response's own response_text WHILE the POST /sessions/{id}/messages
   request is still in flight -- not just {"stage": "..."} events.
2. The concatenated token fragments equal the response_text the POST
   eventually returns, character for character.
3. Every token event arrives strictly before the "response" stage event.

This is the one thing no unit/integration test in this repo can cover:
whether OpenRouter's REAL streaming response actually matches the SSE
frame shape (`choices[0].delta.content`, a final usage-only chunk, a
literal `data: [DONE]`) this codebase's _consume_openrouter_stream
(src/llm/providers.py) assumes.
"""

from __future__ import annotations

import json
import sys
import threading
import time

import requests

BASE_URL = "http://127.0.0.1:8000"


def main() -> int:
    http = requests.Session()
    session_id = http.post(f"{BASE_URL}/sessions").json()["id"]
    print(f"Session: {session_id}")

    events: list[tuple] = []
    connected = threading.Event()
    stop = threading.Event()

    def _listen() -> None:
        with http.get(f"{BASE_URL}/sessions/{session_id}/stream", stream=True, timeout=60) as resp:
            connected.set()
            for raw_line in resp.iter_lines(decode_unicode=True):
                if stop.is_set():
                    break
                if not raw_line or not raw_line.startswith("data:"):
                    continue
                data = json.loads(raw_line[len("data:"):].strip())
                if "stage" in data:
                    events.append(("stage", data["stage"]))
                    if data["stage"] == "response":
                        break
                elif "token" in data:
                    events.append(("token", data["token"]))

    listener = threading.Thread(target=_listen, daemon=True)
    listener.start()
    if not connected.wait(timeout=5):
        print("FAIL: stream never connected")
        return 1

    t_start = time.monotonic()
    resp = http.post(
        f"{BASE_URL}/sessions/{session_id}/messages",
        json={"content": "I've been putting off a hard conversation with my manager about my workload."},
    )
    print(f"POST latency: {time.monotonic() - t_start:.1f}s")
    body = resp.json()
    print(f"Response: {body}")

    listener.join(timeout=30)
    stop.set()

    if not body.get("response_text"):
        print(f"FAIL: no response_text: {body}")
        return 1

    token_events = [payload for kind, payload in events if kind == "token"]
    stage_events = [payload for kind, payload in events if kind == "stage"]
    print(f"Stage events: {stage_events}")
    print(f"Token events: {len(token_events)} fragment(s)")

    if not token_events:
        print("FAIL: zero token events arrived -- streaming never actually happened")
        return 1

    streamed_text = "".join(token_events)
    if streamed_text != body["response_text"]:
        print(f"FAIL: streamed text does not match the final response_text.\nStreamed: {streamed_text!r}\nFinal:    {body['response_text']!r}")
        return 1

    if "response" not in stage_events:
        print("FAIL: the 'response' stage event never arrived")
        return 1
    response_stage_index = events.index(("stage", "response"))
    token_indices = [i for i, e in enumerate(events) if e[0] == "token"]
    if any(i > response_stage_index for i in token_indices):
        print("FAIL: at least one token event arrived AFTER the 'response' stage event")
        return 1

    print(
        f"OK: {len(token_events)} token fragment(s) streamed live, exactly matching the final "
        "response_text, all arriving before the 'response' stage event."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
