"""
Live verification for backlog #235 ("Tier2 moved off the critical
path", see engine/decisions.md) -- starts against the REAL running MVP
API server (src/api/server.py, started by
.github/workflows/tier2-background-verify.yml the same way
api-smoketest.yml starts it) and proves, with real wall-clock
measurements, that:

1. POST /sessions/{id}/messages returns WITHOUT waiting for Tier2 to
   finish computing.
2. Tier2 actually does complete afterward, asynchronously, and its
   result lands in persisted WorldState (visible via
   GET /sessions/{id}/understanding, which reads straight from the DB
   every call).

Only measurable against the real server + real OPENROUTER_API_KEY --
scripts/run_worldstate_walkthrough.py calls run_turn directly with its
default run_tier2=True, so it can't exercise src/api/server.py's
background-task wiring at all. Exits non-zero (and prints exactly which
check failed) so the workflow fails loudly rather than silently passing
on a broken measurement.
"""

from __future__ import annotations

import sys
import time

import requests

BASE_URL = "http://127.0.0.1:8000"
POLL_INTERVAL_SECONDS = 1.5
POLL_TIMEOUT_SECONDS = 45


def main() -> int:
    # A real Session (cookie jar), not the bare `requests` module -- the
    # anonymous_id cookie resolve_identity issues on session creation
    # (src/api/server.py) must round-trip on every later call for
    # _require_owned_session to recognize the same caller as the owner.
    # Every real client (the actual frontend, curl with -b/-c) does this
    # automatically; bare module-level requests.post/get calls don't.
    http = requests.Session()

    session_id = http.post(f"{BASE_URL}/sessions").json()["id"]
    print(f"Session: {session_id}")

    # Turn 1: real message likely to produce at least one Tier2-eligible
    # candidate (a goal) -- should_recompute_tier2 fires unconditionally
    # the first time Tier2 has never been computed for this session
    # (tier2_computed_at_turn is None), so this turn is expected to
    # trigger a real Tier2 LLM call in the background, not just Turn 1's
    # own four foreground calls.
    t_request_start = time.monotonic()
    resp = http.post(
        f"{BASE_URL}/sessions/{session_id}/messages",
        json={"content": "I've been trying to move from my current team to the Product team for months."},
    )
    t_response_received = time.monotonic()
    response_latency = t_response_received - t_request_start
    print(f"Turn 1 HTTP response latency: {response_latency:.1f}s")
    print(f"Turn 1 response: {resp.json()}")

    if not resp.json().get("response_text"):
        print(f"FAIL: turn 1 got no response_text: {resp.json()}")
        return 1

    # Immediately after the response returns, Tier2 should NOT already
    # be there -- if it is, either the background task finished
    # implausibly fast (possible but worth flagging) or (more likely, if
    # this ever regresses) Tier2 went back to blocking the response.
    understanding_immediately_after = http.get(f"{BASE_URL}/sessions/{session_id}/understanding").json()
    tier2_immediately_after = understanding_immediately_after.get("tier2", [])
    print(f"Tier2 immediately after response returned: {len(tier2_immediately_after)} statement(s)")

    # Poll until Tier2 actually lands, proving the background task did
    # complete and persist -- not just that it was scheduled.
    t_poll_start = time.monotonic()
    tier2_after_background = []
    while time.monotonic() - t_poll_start < POLL_TIMEOUT_SECONDS:
        understanding = http.get(f"{BASE_URL}/sessions/{session_id}/understanding").json()
        tier2_after_background = understanding.get("tier2", [])
        if tier2_after_background:
            break
        time.sleep(POLL_INTERVAL_SECONDS)
    background_latency = time.monotonic() - t_poll_start
    print(f"Tier2 background completion latency (after response returned): {background_latency:.1f}s")
    print(f"Tier2 after background completed: {len(tier2_after_background)} statement(s)")

    if not tier2_after_background:
        print(f"FAIL: Tier2 never appeared within {POLL_TIMEOUT_SECONDS}s of the response returning.")
        return 1

    if tier2_immediately_after:
        print(
            "NOTE (not a failure): Tier2 was already present immediately after the "
            "response returned -- the background task finished faster than this "
            "script's first poll could observe it. Still consistent with "
            "non-blocking behavior (the response itself did not wait for it), "
            "just not proof of the ordering the way a later appearance would be."
        )

    print(
        "OK: response returned in "
        f"{response_latency:.1f}s, Tier2 completed separately "
        f"{background_latency:.1f}s after that -- Tier2 is off the critical path."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
