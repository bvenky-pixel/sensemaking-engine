"""
SQLite persistence for the MVP API layer.

WorldState was, until this file, never actually reloaded from JSON
anywhere in this codebase -- every existing call site (conversation_runner.py,
scripts/run_worldstate_walkthrough.py, src/evaluation/confidant_runner.py,
every test) only ever constructs a fresh `WorldState()` and carries it
forward in-process for the life of one script run. An HTTP API has no
such luxury -- state must survive between one request and the next -- so
this is the first place `WorldState.model_validate_json` actually gets
exercised, not just `model_dump_json`.

Two tables, intentionally minimal:
- `sessions`: one row per conversation, storing the current WorldState as
  JSON. `debug_json` additionally stores the last turn's full
  `TurnResult` (Interpretation/Judgment/Planner/Response, all internal
  cognitive artifacts never meant for the actual product UI -- see
  src/api/schema.py) purely for a developer/demo debug endpoint, mirroring
  what conversation_runner.py already prints to a terminal.
- `messages`: the raw transcript (role, content) -- WorldState only holds
  *structured extraction* of what was said, never the raw text itself, so
  a UI restoring a scrollback on page reload needs this separately.

No ORM, no migrations -- a single `CREATE TABLE IF NOT EXISTS` pair run
at startup, consistent with this being a minimal MVP proof, not a
production data layer.
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, List, Optional

from src.api.schema import MessageOut, SessionSummary
from src.orchestrator.schema import TurnResult
from src.state.world_state import WorldState

# Deployment (see .github/workflows/deploy.yml, fly.toml) mounts a
# persistent volume and points CONFIDANT_DB_PATH at a file inside it --
# without this, the SQLite file would live in the container's own
# ephemeral filesystem and every redeploy/restart would silently wipe
# all session history, even with a volume declared. Defaults to a
# repo-root-relative path for local dev, matching the original behavior.
DB_PATH = Path(
    os.environ.get(
        "CONFIDANT_DB_PATH",
        str(Path(__file__).resolve().parent.parent.parent / "confidant_mvp.db"),
    )
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    world_state_json TEXT NOT NULL,
    debug_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: Optional[Path] = None) -> None:
    """Idempotent -- safe to call on every server startup."""
    global DB_PATH
    if db_path is not None:
        DB_PATH = db_path
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.executescript(_SCHEMA)


def create_session() -> str:
    session_id = str(uuid.uuid4())
    now = _now()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO sessions (id, world_state_json, debug_json, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, WorldState().model_dump_json(), None, now, now),
        )
    return session_id


def session_exists(session_id: str) -> bool:
    with _connect() as conn:
        row = conn.execute("SELECT 1 FROM sessions WHERE id = ?", (session_id,)).fetchone()
    return row is not None


def list_sessions() -> List[SessionSummary]:
    """
    Added for the real frontend's Home screen (see
    frontend/decisions.md "Build the real Confidant frontend") --
    Information Architecture specifies Home as a list of a person's
    Journeys, which no endpoint could previously support (every prior
    one is scoped to a single, already-known session id). No schema
    migration needed -- `surface_complaint` is extracted from the same
    `world_state_json` blob every other endpoint already reads.
    Ordered most-recently-updated first, matching how a calm "recent
    Journeys" list should read.
    """
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, world_state_json, updated_at FROM sessions ORDER BY updated_at DESC"
        ).fetchall()
    summaries = []
    for session_id, world_state_json, updated_at in rows:
        state = WorldState.model_validate_json(world_state_json)
        summaries.append(
            SessionSummary(id=session_id, surface_complaint=state.surface_complaint, updated_at=updated_at)
        )
    return summaries


def load_state(session_id: str) -> WorldState:
    with _connect() as conn:
        row = conn.execute(
            "SELECT world_state_json FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
    if row is None:
        raise KeyError(f"No session {session_id!r}")
    return WorldState.model_validate_json(row[0])


def save_turn_result(session_id: str, result: TurnResult) -> None:
    """Persists the new WorldState (always taken from `result.state`,
    accurate at every failure point -- see TurnResult's own docstring)
    plus the full TurnResult for the debug endpoint."""
    with _connect() as conn:
        conn.execute(
            "UPDATE sessions SET world_state_json = ?, debug_json = ?, updated_at = ? WHERE id = ?",
            (result.state.model_dump_json(), result.model_dump_json(), _now(), session_id),
        )


def load_debug(session_id: str) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT debug_json FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
    if row is None:
        raise KeyError(f"No session {session_id!r}")
    return json.loads(row[0]) if row[0] else None


def append_message(session_id: str, role: str, content: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (session_id, role, content, _now()),
        )


def get_messages(session_id: str) -> List[MessageOut]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY id ASC",
            (session_id,),
        ).fetchall()
    return [MessageOut(role=r[0], content=r[1], created_at=r[2]) for r in rows]
