"""
Tests for src/api/db.py::get_session_texts_for_insights -- the query
that feeds scripts/run_insight_detection.py's one LLM call per account.
Mirrors tests/test_pom_aggregation.py's own style (direct db-layer
tests, no HTTP client, no mocked LLM calls -- this function is pure SQL
plus WorldState/debug_json parsing).

Focus: the recency-window-vs-existing-evidence fix (2026-07-19, backlog
#293, see engine/decisions.md "Insight Engine: keep re-offering existing
evidence sessions across runs") -- a session that's evidence for an
existing Insight must stay in the pool this function returns even after
it ages out of the MAX_SESSIONS_FOR_INSIGHT recency window, so the next
run's LLM call still gets a chance to re-cite it.
"""

from __future__ import annotations

import json

from src.api import db
from src.insight.schema import MAX_SESSIONS_FOR_INSIGHT, Insight
from src.state.world_state import WorldState


def _create_session_with_judgment(user_id: str, primary_problem: str) -> str:
    """A session with just enough debug_json to pass
    get_session_texts_for_insights' own `judgment` presence check --
    building a full Judgment object isn't needed since this function
    only ever reads `debug["judgment"]["primary_problem"]`."""
    session_id = db.create_session(user_id=user_id)
    with db._connect() as conn:
        conn.execute(
            "UPDATE sessions SET debug_json = ? WHERE id = ?",
            (json.dumps({"judgment": {"primary_problem": primary_problem}}), session_id),
        )
    return session_id


def test_returns_a_sessions_own_judgment_text(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db(tmp_path / "test.db")
    session_id = _create_session_with_judgment("user-1", "Transfer is stalled.")

    texts = db.get_session_texts_for_insights("user-1")

    assert texts == [(session_id, "", "Transfer is stalled.")]


def test_session_with_no_debug_json_is_excluded(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db(tmp_path / "test.db")
    db.create_session(user_id="user-1")  # never completed a turn

    assert db.get_session_texts_for_insights("user-1") == []


def test_an_existing_insights_evidence_session_survives_rotating_out_of_the_recency_window(tmp_path, monkeypatch):
    """The direct regression test for backlog #293's narrow fix: an old
    session that's evidence for an existing Insight must still be
    returned even once MAX_SESSIONS_FOR_INSIGHT newer sessions have
    pushed it out of the plain recency-ordered window."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db(tmp_path / "test.db")

    old_session_id = _create_session_with_judgment("user-1", "Old evidence session.")
    with db._connect() as conn:
        conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            ("2020-01-01T00:00:00", old_session_id),
        )
    db.replace_insights("user-1", [
        Insight(theme="Avoidance", detail="Delays hard conversations.", evidence_session_ids=[old_session_id]),
    ])

    # Push old_session_id out of the plain top-N recency window.
    for i in range(MAX_SESSIONS_FOR_INSIGHT):
        newer_id = _create_session_with_judgment("user-1", f"Newer session {i}.")
        with db._connect() as conn:
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (f"2021-01-{i + 1:02d}T00:00:00", newer_id),
            )

    session_ids = {sid for sid, _, _ in db.get_session_texts_for_insights("user-1")}

    assert old_session_id in session_ids
    assert len(session_ids) == MAX_SESSIONS_FOR_INSIGHT + 1


def test_an_evidence_session_belonging_to_another_account_is_never_pulled_in(tmp_path, monkeypatch):
    """The union with insight_sessions must stay scoped to THIS account's
    own insights -- confirmed via the `insights.user_id = ?` join
    condition, not just insight_sessions' own session_id column (which
    carries no owner of its own)."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db(tmp_path / "test.db")

    other_session_id = _create_session_with_judgment("user-2", "Someone else's session.")
    db.replace_insights("user-2", [
        Insight(theme="Someone else's theme", detail="...", evidence_session_ids=[other_session_id]),
    ])

    assert db.get_session_texts_for_insights("user-1") == []
