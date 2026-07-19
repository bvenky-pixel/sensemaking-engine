"""Unit tests for src/api/rate_limit.py (2026-07-19, backlog #229) --
the module itself, independent of any FastAPI route. Server-level
behavior (the actual /auth/request-link and /sessions/{id}/messages
checks) is covered in tests/test_api_server.py."""

from __future__ import annotations

import time

import pytest
from fastapi import HTTPException

from src.api import rate_limit


@pytest.fixture(autouse=True)
def _reset():
    rate_limit.reset_all()
    yield
    rate_limit.reset_all()


def test_allows_calls_under_the_limit():
    for _ in range(3):
        rate_limit.check_rate_limit("bucket", "key", limit=3, window_seconds=60)


def test_blocks_the_call_that_exceeds_the_limit():
    for _ in range(3):
        rate_limit.check_rate_limit("bucket", "key", limit=3, window_seconds=60)
    with pytest.raises(HTTPException) as exc_info:
        rate_limit.check_rate_limit("bucket", "key", limit=3, window_seconds=60)
    assert exc_info.value.status_code == 429
    assert exc_info.value.detail == "rate_limited"


def test_different_keys_have_independent_limits():
    for _ in range(3):
        rate_limit.check_rate_limit("bucket", "key-a", limit=3, window_seconds=60)
    # key-b's own bucket is untouched by key-a's hits.
    rate_limit.check_rate_limit("bucket", "key-b", limit=3, window_seconds=60)


def test_different_buckets_have_independent_limits_for_the_same_key():
    """Same key (e.g. one email), two different buckets (e.g. auth vs
    message) -- namespacing exists precisely so these don't collide."""
    for _ in range(3):
        rate_limit.check_rate_limit("bucket-a", "shared-key", limit=3, window_seconds=60)
    rate_limit.check_rate_limit("bucket-b", "shared-key", limit=3, window_seconds=60)


def test_old_hits_expire_out_of_the_window():
    for _ in range(3):
        rate_limit.check_rate_limit("bucket", "key", limit=3, window_seconds=0.05)
    with pytest.raises(HTTPException):
        rate_limit.check_rate_limit("bucket", "key", limit=3, window_seconds=0.05)

    time.sleep(0.1)
    # The window has fully elapsed -- this must succeed, not still be
    # blocked by hits that are no longer within window_seconds.
    rate_limit.check_rate_limit("bucket", "key", limit=3, window_seconds=0.05)
