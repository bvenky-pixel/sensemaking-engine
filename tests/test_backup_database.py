"""
Tests for scripts/backup_database.py (2026-07-19, backlog #231, see
engine/decisions.md "Backup strategy for the production SQLite
volume") -- the whole point of a backup script is that it round-trips
real data correctly, so that's what these test directly rather than
just "it doesn't crash."
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from scripts.backup_database import main as backup_main
from src.api import db


def _seed(tmp_path: Path) -> Path:
    db_path = tmp_path / "seed.db"
    db.init_db(db_path)
    user_id = db.get_or_create_user("backup-test@example.com")
    session_id = db.create_session(user_id=user_id)
    db.append_message(session_id, role="user", content="A real message.")
    return db_path


def test_backup_dumps_data_that_restores_correctly(tmp_path, monkeypatch, capsys):
    db_path = _seed(tmp_path)

    monkeypatch.setattr(sys, "argv", ["backup_database.py", "--db-path", str(db_path)])
    backup_main()
    dump_sql = capsys.readouterr().out

    restored = sqlite3.connect(":memory:")
    restored.executescript(dump_sql)
    users = restored.execute("SELECT email FROM users").fetchall()
    sessions = restored.execute("SELECT user_id FROM sessions").fetchall()
    messages = restored.execute("SELECT content FROM messages").fetchall()

    assert users == [("backup-test@example.com",)]
    assert len(sessions) == 1
    assert messages == [("A real message.",)]


def test_backup_never_modifies_the_source_database(tmp_path, monkeypatch, capsys):
    """Opened read-only (mode=ro) -- confirms this deliberately, not
    just by inspecting the source, since a bug here would be a script
    that's supposed to be safe to run against a live production
    database silently writing to it instead."""
    db_path = _seed(tmp_path)
    before = db_path.read_bytes()

    monkeypatch.setattr(sys, "argv", ["backup_database.py", "--db-path", str(db_path)])
    backup_main()
    capsys.readouterr()

    assert db_path.read_bytes() == before


def test_backup_of_an_empty_database_still_restores_cleanly(tmp_path, monkeypatch, capsys):
    db_path = tmp_path / "empty.db"
    db.init_db(db_path)

    monkeypatch.setattr(sys, "argv", ["backup_database.py", "--db-path", str(db_path)])
    backup_main()
    dump_sql = capsys.readouterr().out

    restored = sqlite3.connect(":memory:")
    restored.executescript(dump_sql)
    assert restored.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
