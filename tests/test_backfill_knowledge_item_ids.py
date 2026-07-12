"""
Tests for scripts/backfill_knowledge_item_ids.py -- the one-time
migration for already-persisted WorldState sessions that predate
KnowledgeItem.id (see src/state/world_state.py, engine/decisions.md
"Understanding layer -- Journey-scoped identity").

Simulates a genuinely pre-migration session by dumping a real WorldState
and stripping every "id" key from the raw dict before writing it
directly into the DB -- a real pre-id WorldState object can no longer be
constructed once the field exists (its default_factory would just fill
it back in), so this is the only way to reproduce the actual on-disk
shape old sessions have.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.backfill_knowledge_item_ids import _count_missing_ids, main as backfill_main
from src.api import db
from src.state.world_state import Fact, Goal, WorldState


def _seed_pre_migration_session(session_id: str) -> None:
    state = WorldState()
    state.facts.append(Fact(content="A fact."))
    state.goals.append(Goal(content="A goal."))
    raw = json.loads(state.model_dump_json())
    for field in ("facts", "goals"):
        for item in raw[field]:
            del item["id"]
    with db._connect() as conn:
        conn.execute(
            "UPDATE sessions SET world_state_json = ? WHERE id = ?",
            (json.dumps(raw), session_id),
        )


def test_dry_run_reports_missing_ids_without_writing(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    session_id = db.create_session()
    _seed_pre_migration_session(session_id)

    monkeypatch.setattr(sys, "argv", ["backfill_knowledge_item_ids.py", "--db-path", str(tmp_path / "test.db"), "--dry-run"])
    backfill_main()

    out = capsys.readouterr().out
    assert "2 item(s) missing an id across 1 session(s)" in out
    # Confirm nothing was actually written -- ids are still missing.
    row = db.get_all_sessions_raw()[0]
    assert _count_missing_ids(row[1]) == 2


def test_backfill_persists_ids_stably_across_independent_reloads(monkeypatch, tmp_path, capsys):
    """The core regression test: fails if save_world_state_for_backfill
    didn't actually persist, since a second independent load would then
    regenerate different ids via default_factory."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    session_id = db.create_session()
    _seed_pre_migration_session(session_id)

    monkeypatch.setattr(sys, "argv", ["backfill_knowledge_item_ids.py", "--db-path", str(tmp_path / "test.db")])
    backfill_main()

    first_load = db.load_state(session_id)
    second_load = db.load_state(session_id)
    assert first_load.facts[0].id == second_load.facts[0].id
    assert first_load.goals[0].id == second_load.goals[0].id
    assert first_load.facts[0].id  # non-empty


def test_backfill_is_idempotent(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    session_id = db.create_session()
    _seed_pre_migration_session(session_id)

    argv = ["backfill_knowledge_item_ids.py", "--db-path", str(tmp_path / "test.db")]
    monkeypatch.setattr(sys, "argv", argv)
    backfill_main()
    ids_after_first_run = [f.id for f in db.load_state(session_id).facts]

    capsys.readouterr()
    backfill_main()
    out = capsys.readouterr().out
    assert "No sessions needed backfilling" in out
    ids_after_second_run = [f.id for f in db.load_state(session_id).facts]
    assert ids_after_first_run == ids_after_second_run


def test_backfill_does_not_bump_updated_at(monkeypatch, tmp_path):
    """save_world_state_for_backfill deliberately does not touch
    updated_at -- a migration run touching every session must not
    reorder list_sessions' recency ordering."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    session_id = db.create_session()
    _seed_pre_migration_session(session_id)

    with db._connect() as conn:
        before = conn.execute("SELECT updated_at FROM sessions WHERE id = ?", (session_id,)).fetchone()[0]

    monkeypatch.setattr(sys, "argv", ["backfill_knowledge_item_ids.py", "--db-path", str(tmp_path / "test.db")])
    backfill_main()

    with db._connect() as conn:
        after = conn.execute("SELECT updated_at FROM sessions WHERE id = ?", (session_id,)).fetchone()[0]
    assert before == after
