"""
In-memory rate limiting (2026-07-19, backlog #229, see engine/decisions.md
"Rate limiting added to auth and message endpoints").

Deliberately per-process, not distributed -- no Redis, no shared store,
same "no ORM, no external services, plain stdlib" discipline the rest
of src/api already follows. Correct for this app's current deployment:
`fly.toml` has no autoscaling/concurrency section, and
`min_machines_running = 0` only means it scales to ZERO when idle, not
that it ever runs more than one machine at once. If this app is ever
scaled to run multiple concurrent machines, each machine would enforce
its own independent limit -- a real gap to revisit then, not a silent
one now (see decisions.md for the full reasoning).

Sliding-window counter via a deque of call timestamps per (bucket, key)
pair. `bucket` namespaces independent limits (e.g. "auth_request_link"
vs "send_message") sharing the same key space -- an email, an IP, an
account/anonymous id -- without colliding. Thread-safe: FastAPI runs
plain `def` routes (every route in this codebase) in a worker thread
pool, not on the event loop, so concurrent requests genuinely race
here, unlike the rest of this single-threaded-feeling module.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Tuple

from fastapi import HTTPException, Request

_lock = threading.Lock()
_hits: Dict[Tuple[str, str], Deque[float]] = defaultdict(deque)


def check_rate_limit(bucket: str, key: str, limit: int, window_seconds: float) -> None:
    """Raises HTTPException(429, detail="rate_limited") if `key` has
    already made `limit` calls to `bucket` within the trailing
    `window_seconds`; otherwise records this call and returns
    normally. Call this BEFORE doing any real work (an email send, an
    LLM call) -- same "reject before paying any cost" discipline
    send_message's own response-limit check already follows."""
    now = time.monotonic()
    cache_key = (bucket, key)
    with _lock:
        hits = _hits[cache_key]
        while hits and now - hits[0] > window_seconds:
            hits.popleft()
        if len(hits) >= limit:
            raise HTTPException(status_code=429, detail="rate_limited")
        hits.append(now)


def client_ip(request: Request) -> str:
    """Best-effort caller IP for the per-IP half of a rate limit --
    `request.client` is None only in edge cases (some ASGI test
    transports), never in real deployment traffic; a plain shared
    fallback key there just means those callers share one limit bucket
    instead of each having none at all."""
    return request.client.host if request.client else "unknown"


def reset_all() -> None:
    """Test-only -- clears every bucket's state so one test's rate-limit
    hits can't bleed into the next. Not called from any live request
    path."""
    with _lock:
        _hits.clear()
