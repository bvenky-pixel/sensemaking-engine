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

Two more tables, added for Phase 1 Learning (see
engine/specs/architecture-roadmap-v1.md and src/learning/engine.py):
- `behavioral_events`: the Memory Store -- an append-only log of every
  BehavioralEvent (src/instrumentation/events.py) detected across every
  turn, every session. Deliberately spans the whole DB with no user_id
  column: there is no `users` table or auth anywhere in this codebase
  today, so this is a stated single-user simplification, not a silent
  gap -- revisit if/when multi-user support exists.
- `learned_patterns`: Learning's own output (src/learning/engine.py,
  computed offline by scripts/run_learning.py, never inside a live
  request). TRUNCATE-AND-REPLACE semantics on every run, not append --
  see replace_learned_patterns below -- mirroring `sessions.world_state_json`'s
  existing overwrite-on-write precedent (save_turn_result), since only
  the latest computed patterns are ever meaningful; an append-only table
  here would let stale/contradicted patterns accumulate forever.

`sessions.bookmarked` (added for the Home redesign, see
frontend/decisions.md): a plain `INTEGER` (0/1) flag, no separate table
needed for a single boolean-per-session. `_SCHEMA`'s `CREATE TABLE IF
NOT EXISTS` already includes it for brand-new databases; `init_db`
additionally runs an idempotent `ALTER TABLE` for any database created
before this column existed (the deployed Fly.io database included) --
the same additive-migration pattern this "no ORM, no migrations"
codebase already uses implicitly (new tables are additive; this is the
first additive column on an existing table).

Two more tables, added for the cross-session Insight Engine (see
src/insight/engine.py, engine/decisions.md "Major update"):
- `insights`: Insight Engine's own output (computed offline by
  scripts/run_insight_detection.py, never inside a live request).
  TRUNCATE-AND-REPLACE, same precedent as `learned_patterns`.
- `insight_sessions`: a join table, not a JSON column on `insights` --
  `list_sessions` below needs a cheap reverse lookup per session ("does
  this session evidence any insight"), and every other many-to-many-
  shaped table in this codebase (`behavioral_events`, `messages`)
  already keys on `session_id` directly rather than as a JSON blob.
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

from src.api.schema import InsightOut, LearnedPatternOut, MessageOut, SessionSummary
from src.insight.schema import MAX_SESSIONS_FOR_INSIGHT, Insight
from src.instrumentation.events import BehavioralEvent, is_events_enabled
from src.judgment.engine import compute_stagnation_signals
from src.learning.engine import Pattern
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
    updated_at TEXT NOT NULL,
    bookmarked INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    options_json TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS behavioral_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    turn INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    detail TEXT NOT NULL,
    old_status TEXT NOT NULL,
    new_status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS learned_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_type TEXT NOT NULL,
    detail TEXT NOT NULL,
    evidence_count INTEGER NOT NULL,
    computed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS insights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    theme TEXT NOT NULL,
    detail TEXT NOT NULL,
    computed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS insight_sessions (
    insight_id INTEGER NOT NULL,
    session_id TEXT NOT NULL,
    FOREIGN KEY (insight_id) REFERENCES insights(id),
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
        # Additive migration for any database created before `bookmarked`
        # existed (see module docstring) -- a no-op (caught below) for a
        # brand-new database, since _SCHEMA above already includes it.
        try:
            conn.execute("ALTER TABLE sessions ADD COLUMN bookmarked INTEGER NOT NULL DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        # Same pattern for `options_json` (see Response v3 -- real choice
        # buttons, engine/decisions.md): a message row from before this
        # column existed has no options, which is exactly what NULL ->
        # `[]` (see get_messages below) already means.
        try:
            conn.execute("ALTER TABLE messages ADD COLUMN options_json TEXT")
        except sqlite3.OperationalError:
            pass


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


def list_sessions(bookmarked_only: bool = False) -> List[SessionSummary]:
    """
    Added for the real frontend's Home screen (see
    frontend/decisions.md "Build the real Confidant frontend") --
    Information Architecture specifies Home as a list of a person's
    Journeys, which no endpoint could previously support (every prior
    one is scoped to a single, already-known session id). Ordered
    most-recently-updated first, matching how a calm "recent Journeys"
    list should read.

    `preview_text` (see engine/decisions.md "Frontend UX pass"): sourced
    from the session's FIRST user message (a single extra query, joined
    via a session_id -> content dict, same "no ORM, separate query
    joined in Python" style already used for insight_theme/insight_detail
    below) -- NOT `state.surface_complaint`, which is overwritten every
    turn and would make a session's own Home-screen label change on
    every message rather than staying a stable "what this Journey is
    about." Falls back to `state.surface_complaint` (empty string for a
    brand-new session) only for a session with zero messages yet, which
    the frontend already renders as "A new Journey".

    `bookmarked_only` (added for the Home redesign): filters to
    `bookmarked = 1` rows. `has_stagnation_signal` (also added then) is
    computed per session via compute_stagnation_signals (pure function
    of WorldState alone, src/judgment/engine.py) being non-empty --
    deliberately just a boolean flag, not the mechanical signal's raw
    text or Judgment's own worded stagnation_notes (see
    frontend/decisions.md for why: the raw text is internal, and
    surfacing Judgment's actual wording would need an extra debug_json
    read per session for a first pass that doesn't need it yet).

    `insight_theme`/`insight_detail` (major update, see engine/decisions.md):
    unlike has_stagnation_signal, this deliberately deviates from the
    boolean-only precedent and surfaces real Insight Engine theme text --
    an explicit product decision, not an oversight. A separate query
    builds a session_id -> (theme, detail) map (picking the
    most-recently-computed insight if a session ever evidences more than
    one -- a documented simplification, not a silent one) rather than a
    SQL JOIN + GROUP BY, matching this file's "no ORM" simplicity.
    """
    query = "SELECT id, world_state_json, updated_at, bookmarked FROM sessions"
    if bookmarked_only:
        query += " WHERE bookmarked = 1"
    query += " ORDER BY updated_at DESC"
    with _connect() as conn:
        rows = conn.execute(query).fetchall()
        insight_rows = conn.execute(
            "SELECT insight_sessions.session_id, insights.theme, insights.detail "
            "FROM insight_sessions JOIN insights ON insights.id = insight_sessions.insight_id "
            "ORDER BY insights.id ASC"
        ).fetchall()
        first_message_rows = conn.execute(
            "SELECT m.session_id, m.content FROM messages m "
            "INNER JOIN (SELECT session_id, MIN(id) AS first_id FROM messages "
            "WHERE role = 'user' GROUP BY session_id) first_msg "
            "ON m.session_id = first_msg.session_id AND m.id = first_msg.first_id"
        ).fetchall()
    # Later rows win on conflict (ORDER BY insights.id ASC, dict overwrite) --
    # "most-recently-computed insight" per the docstring above.
    session_insight = {session_id: (theme, detail) for session_id, theme, detail in insight_rows}
    first_message = {session_id: content for session_id, content in first_message_rows}

    summaries = []
    for session_id, world_state_json, updated_at, bookmarked in rows:
        state = WorldState.model_validate_json(world_state_json)
        theme, detail = session_insight.get(session_id, (None, None))
        summaries.append(
            SessionSummary(
                id=session_id,
                preview_text=first_message.get(session_id) or state.surface_complaint,
                updated_at=updated_at,
                bookmarked=bool(bookmarked),
                has_stagnation_signal=bool(compute_stagnation_signals(state)),
                insight_theme=theme,
                insight_detail=detail,
            )
        )
    return summaries


def set_bookmark(session_id: str, bookmarked: bool) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE sessions SET bookmarked = ? WHERE id = ?", (1 if bookmarked else 0, session_id)
        )


def delete_session(session_id: str) -> None:
    """Removes a Journey and everything that references it -- added for
    Settings' Data section (see engine/decisions.md "Frontend UX pass").
    No `ON DELETE CASCADE` in `_SCHEMA` above, so child rows are deleted
    explicitly, in dependency order, in one transaction (`_connect`'s own
    `with` block commits on success / rolls back on any exception -- see
    its own docstring). `insight_sessions` (this session's OWN evidence
    link) is removed, but `insights` themselves are NOT -- an Insight is
    a cross-session theme that may still be evidenced by other sessions,
    so deleting one session must not delete a theme other sessions still
    support. Silently a no-op if `session_id` doesn't exist (same
    "caller already checked existence via session_exists" pattern every
    other per-session function here assumes -- see _require_session in
    src/api/server.py)."""
    with _connect() as conn:
        conn.execute("DELETE FROM insight_sessions WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM behavioral_events WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))


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


def get_all_sessions_raw() -> List[Tuple[str, str]]:
    """Read-only, used only by scripts/backfill_knowledge_item_ids.py --
    (id, world_state_json) for EVERY session, uncapped (unlike
    get_session_texts_for_insights' MAX_SESSIONS_FOR_INSIGHT cap; a
    one-time migration needs to reach every session, not a recency-capped
    subset)."""
    with _connect() as conn:
        rows = conn.execute("SELECT id, world_state_json FROM sessions").fetchall()
    return [(r[0], r[1]) for r in rows]


def save_world_state_for_backfill(session_id: str, state: WorldState) -> None:
    """Writes world_state_json only -- used only by
    scripts/backfill_knowledge_item_ids.py. Deliberately does NOT bump
    updated_at or touch debug_json (unlike save_turn_result): a backfill
    run touching every session must not reorder list_sessions' recency
    ordering or make untouched sessions look freshly active on Home."""
    with _connect() as conn:
        conn.execute(
            "UPDATE sessions SET world_state_json = ? WHERE id = ?",
            (state.model_dump_json(), session_id),
        )


def load_debug(session_id: str) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT debug_json FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
    if row is None:
        raise KeyError(f"No session {session_id!r}")
    return json.loads(row[0]) if row[0] else None


def append_message(
    session_id: str, role: str, content: str, options: Optional[List[dict]] = None
) -> None:
    """`options` (Response v3 -- real choice buttons): only ever
    meaningful for an `assistant` message -- persisted as JSON so a page
    reload (GET /sessions/{id}/messages) still shows the same tappable
    buttons the person saw live, not just a plain paragraph. `None`
    (the default, and every `user` message) stores NULL, which
    get_messages below treats identically to an empty list. Each dict is
    `{"label": ..., "description": ...}` (see ResponseOptionOut) -- stored
    as plain JSON, not a ResponseOptionOut instance, since this module
    has no business depending on that API-layer type; get_messages below
    hands the same shape back and MessageOut's own field coerces it.
    """
    with _connect() as conn:
        conn.execute(
            "INSERT INTO messages (session_id, role, content, created_at, options_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, role, content, _now(), json.dumps(options) if options else None),
        )


def get_messages(session_id: str) -> List[MessageOut]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT role, content, created_at, options_json FROM messages "
            "WHERE session_id = ? ORDER BY id ASC",
            (session_id,),
        ).fetchall()
    return [
        MessageOut(role=r[0], content=r[1], created_at=r[2], options=json.loads(r[3]) if r[3] else [])
        for r in rows
    ]


def save_events(session_id: str, events: List[BehavioralEvent]) -> None:
    """Appends this turn's behavioral events (usually empty -- most turns
    change nothing's status) to the Memory Store. Called from
    src/api/server.py::send_message after run_turn returns, mirroring how
    save_turn_result is already called there.

    Gated on CONFIDANT_RECORD_EVENTS (off by default, see
    src/instrumentation/events.py::is_events_enabled) -- this is the
    persistence boundary where that gate belongs: diff_behavioral_events
    itself stays a pure, environment-independent function, but whether
    real behavioral data actually accumulates in the Memory Store is the
    privacy-relevant decision trust-and-privacy-ux-v1.md's Principle 6
    (amended for this feature) says must not happen by silent default."""
    if not events or not is_events_enabled():
        return
    with _connect() as conn:
        conn.executemany(
            "INSERT INTO behavioral_events "
            "(session_id, turn, event_type, detail, old_status, new_status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (session_id, e.turn, e.event_type, e.detail, e.old_status, e.new_status, e.timestamp)
                for e in events
            ],
        )


def get_all_events() -> List[BehavioralEvent]:
    """Read-only, used only by scripts/run_learning.py -- the entire
    Memory Store across every session (single-user scope, see module
    docstring)."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT event_type, session_id, turn, detail, old_status, new_status, created_at "
            "FROM behavioral_events ORDER BY id ASC"
        ).fetchall()
    return [
        BehavioralEvent(
            event_type=r[0], session_id=r[1], turn=r[2], detail=r[3],
            old_status=r[4], new_status=r[5], timestamp=r[6],
        )
        for r in rows
    ]


def replace_learned_patterns(patterns: List[Pattern]) -> None:
    """Truncate-and-replace, not append -- see module docstring's
    reasoning (mirrors save_turn_result's overwrite-on-write precedent).
    Called only by scripts/run_learning.py, never from a live request."""
    now = _now()
    with _connect() as conn:
        conn.execute("DELETE FROM learned_patterns")
        if patterns:
            conn.executemany(
                "INSERT INTO learned_patterns (pattern_type, detail, evidence_count, computed_at) "
                "VALUES (?, ?, ?, ?)",
                [(p.pattern_type, p.detail, p.evidence_count, now) for p in patterns],
            )


def get_learned_patterns() -> List[LearnedPatternOut]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT pattern_type, detail, evidence_count FROM learned_patterns ORDER BY id ASC"
        ).fetchall()
    return [LearnedPatternOut(pattern_type=r[0], detail=r[1], evidence_count=r[2]) for r in rows]


def get_session_texts_for_insights() -> List[Tuple[str, str, str]]:
    """Read-only, used only by scripts/run_insight_detection.py. Same
    guard as src/api/server.py's get_clarity_brief endpoint -- only
    sessions whose debug_json actually has a completed `judgment` (a
    session with no completed turn has nothing to extract a
    surface_complaint/primary_problem pair from). Capped at
    MAX_SESSIONS_FOR_INSIGHT most-recently-updated sessions, same cost/
    latency reasoning as src/insight/schema.py's docstring."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, world_state_json, debug_json FROM sessions "
            "ORDER BY updated_at DESC LIMIT ?",
            (MAX_SESSIONS_FOR_INSIGHT,),
        ).fetchall()
    texts: List[Tuple[str, str, str]] = []
    for session_id, world_state_json, debug_json in rows:
        if not debug_json:
            continue
        debug = json.loads(debug_json)
        judgment = debug.get("judgment")
        if not judgment:
            continue
        state = WorldState.model_validate_json(world_state_json)
        texts.append((session_id, state.surface_complaint, judgment["primary_problem"]))
    return texts


def replace_insights(insights: List[Insight]) -> None:
    """Truncate-and-replace both tables, not append -- see module
    docstring's reasoning (mirrors replace_learned_patterns' precedent).
    Called only by scripts/run_insight_detection.py, never from a live
    request."""
    now = _now()
    with _connect() as conn:
        conn.execute("DELETE FROM insight_sessions")
        conn.execute("DELETE FROM insights")
        for insight in insights:
            cursor = conn.execute(
                "INSERT INTO insights (theme, detail, computed_at) VALUES (?, ?, ?)",
                (insight.theme, insight.detail, now),
            )
            insight_id = cursor.lastrowid
            conn.executemany(
                "INSERT INTO insight_sessions (insight_id, session_id) VALUES (?, ?)",
                [(insight_id, sid) for sid in insight.evidence_session_ids],
            )


def get_insights() -> List[InsightOut]:
    with _connect() as conn:
        insight_rows = conn.execute(
            "SELECT id, theme, detail FROM insights ORDER BY id ASC"
        ).fetchall()
        evidence_rows = conn.execute(
            "SELECT insight_id, session_id FROM insight_sessions"
        ).fetchall()
    evidence_by_insight: dict = {}
    for insight_id, session_id in evidence_rows:
        evidence_by_insight.setdefault(insight_id, []).append(session_id)
    return [
        InsightOut(theme=theme, detail=detail, evidence_session_ids=evidence_by_insight.get(insight_id, []))
        for insight_id, theme, detail in insight_rows
    ]
