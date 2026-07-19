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

One more table, added for Privacy, made real (see frontend/decisions.md):
- `privacy_settings`: originally a true singleton ("id INTEGER PRIMARY
  KEY CHECK (id = 1)" -- `personal_operating_model` used to share this
  exact shape before "POM made per-user" below gave it a real `user_id`
  key). **Made per-account 2026-07-19** (see engine/decisions.md
  "privacy_settings made per-account") -- `user_id TEXT PRIMARY KEY`,
  same shape POM's own table now has; no eager row-per-account insert
  the way the old singleton's `INSERT OR IGNORE` guaranteed one row
  from startup -- `get_cross_session_learning_enabled(user_id)`
  defaults to `True` (opt-out, not opt-in, same default the old
  singleton shipped with) when no row exists yet for that account, and
  `set_cross_session_learning_enabled` upserts on first write, same
  "no row until first computed/set" pattern
  `replace_personal_operating_model` already established.
  Currently one column, `cross_session_learning_enabled`: when false
  for THIS account, `send_message` stops reading that account's own
  `learned_patterns`/`insights`/`personal_operating_model` into a live
  turn's Retrieved Context, and `scripts/run_learning.py`/
  `run_insight_detection.py`/`run_pom_computation.py` each skip THAT
  account (continuing on to the next, not exiting outright) rather than
  writing new rows for it -- the same opt-out honored at both the read
  path (what a live conversation sees) and the write path (what gets
  computed about this person in the first place), now genuinely
  per-account on both sides rather than one global switch every
  account shared.

Three more tables, added for basic auth (2026-07-18, see
frontend/decisions.md "Auth, the low-friction way" and engine/decisions.md):
this is the "revisit if/when multi-user support exists" moment the
`behavioral_events` docstring above already flagged -- there was no
`users` table or any notion of data ownership anywhere in this
codebase until now, meaning every visitor to the deployed app saw the
exact same global Journey list. Fixed by giving `sessions` two new
nullable owner columns (`user_id`, `anonymous_id` -- see the `sessions`
ALTER TABLE block in `init_db`) rather than a separate ownership table,
matching this file's own "plain columns over join tables for a single
scalar fact" precedent (`bookmarked`, `mode`). Exactly one of the two
is set on any session created after this round: a session begun while
signed in gets `user_id`; a session begun anonymously gets
`anonymous_id` (a random id the server mints into a cookie on first
contact -- see src/api/server.py's `resolve_identity`) and, if that
browser later signs up, gets its `anonymous_id` cleared and `user_id`
set instead (`claim_anonymous_sessions` below) -- signing up must not
cost a person the Journeys they were already in the middle of. Sessions
created BEFORE this round have neither column set; per this file's own
"no ORM, no migrations, additive-only" discipline, no backfill migration
was written to guess an owner for them, so they are simply not returned
to anyone by the now-owner-scoped `list_sessions`/`_require_owned_session`
-- an honest consequence of introducing ownership after the fact, not
silently swept under a rug (flagged plainly in engine/decisions.md).
Scope was originally bounded to Journeys alone -- `personal_operating_model`
stayed a single global singleton in this same round, alongside
`privacy_settings`/`learned_patterns`/`insights`, as an explicit
out-of-scope carve-out.

**That carve-out was corrected the same day** (see engine/decisions.md
"POM made per-user"): a brand-new signed-in account was found to
inherit whatever POM had been computed from ANYONE's sessions, since
nothing distinguished one person's inferred profile from another's --
a real correctness bug, not a cosmetic gap, once real accounts existed
to be confused with each other. `personal_operating_model` now has a
`user_id` primary key (see this table's own creation SQL below and its
migration in `init_db`) and every accessor takes a `user_id`.
`privacy_settings` and `learned_patterns`/`insights` remained the
single, global, cross-visitor models they already were at the time --
the `behavioral_events` docstring's own "stated single-user
simplification." **`learned_patterns` was corrected 2026-07-18** (see
engine/decisions.md "Learning made per-account") and **`insights` was
corrected 2026-07-19** (see engine/decisions.md "Insight Engine made
per-account") -- both now have a real `user_id` and every accessor
takes one, closing the gap #257 first opened and then only partly
closed (its own title named all three; only Learning actually shipped
that round). `privacy_settings` remains the one genuinely global,
cross-visitor model left -- giving each person their own privacy
toggle is still a real, separate, out-of-scope project.

- `users`: one row per account. `email` is the only real field --
  magic-link auth never needs a password hash to store.
- `magic_links`: a one-time login token per requested link. `token` is
  the primary key (a `secrets.token_urlsafe` value, looked up directly
  -- opaque and DB-revocable, not a signed/self-describing JWT, matching
  this file's "no ORM, plain SQLite" simplicity elsewhere). `anonymous_id`
  travels with the request so `consume_magic_link` can hand it straight
  to `claim_anonymous_sessions` without a second round trip. `used_at`
  makes a token single-use -- set the moment it's consumed, checked
  before honoring one, so a link can't be replayed after its first
  click even if it's still within its expiry window.
- `auth_sessions`: the signed-in browser's own login session, looked up
  by the httpOnly cookie value on every request needing identity.
  Named `auth_sessions`, not `sessions`, specifically to avoid colliding
  with the pre-existing `sessions` table (which means "Journey"
  everywhere else in this codebase) -- reusing that name here would
  have been a genuinely confusing collision, not just a style nit.
"""

from __future__ import annotations

import json
import os
import secrets
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

from src.api.schema import InsightOut, LearnedPatternOut, MessageOut, SessionSummary
from src.insight.schema import MAX_SESSIONS_FOR_INSIGHT, Insight
from src.instrumentation.events import BehavioralEvent, is_events_enabled
from src.judgment.engine import compute_stagnation_signals
from src.learning.engine import Pattern
from src.orchestrator.schema import TurnResult
from src.pom.schema import PersonalOperatingModel
from src.state.world_state import Entity, WorldState

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
    bookmarked INTEGER NOT NULL DEFAULT 0,
    mode TEXT
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
    user_id TEXT NOT NULL,
    pattern_type TEXT NOT NULL,
    detail TEXT NOT NULL,
    evidence_count INTEGER NOT NULL,
    computed_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS insights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    theme TEXT NOT NULL,
    detail TEXT NOT NULL,
    computed_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS insight_sessions (
    insight_id INTEGER NOT NULL,
    session_id TEXT NOT NULL,
    FOREIGN KEY (insight_id) REFERENCES insights(id),
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS personal_operating_model (
    user_id TEXT PRIMARY KEY,
    pom_json TEXT NOT NULL,
    computed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS privacy_settings (
    user_id TEXT PRIMARY KEY,
    cross_session_learning_enabled INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS magic_links (
    token TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    anonymous_id TEXT,
    return_session_id TEXT,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used_at TEXT
);

CREATE TABLE IF NOT EXISTS auth_sessions (
    token TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
"""

# Magic links are single-use and short-lived -- long enough that a
# person checking a somewhat-delayed email notification doesn't lose
# the race, short enough that a link sitting unread in an inbox isn't a
# standing credential. Auth sessions (the signed-in cookie itself) are
# long-lived on purpose -- "as low friction as possible" (the founder's
# own framing) means not asking someone to log in again every few days.
MAGIC_LINK_LIFETIME = timedelta(minutes=15)
AUTH_SESSION_LIFETIME = timedelta(days=30)


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
        # Same pattern for `mode` (Counseling modes, see engine/decisions.md
        # and src/orchestrator/modes.py): a session from before this
        # feature existed has no mode, which is exactly what NULL ->
        # `planner_mode_focus_note(None) == ""` already means -- Planner/Response
        # behave exactly as they did before this feature for that session.
        try:
            conn.execute("ALTER TABLE sessions ADD COLUMN mode TEXT")
        except sqlite3.OperationalError:
            pass
        # Same pattern for the two new owner columns (basic auth, see
        # module docstring) -- a session from before this feature has
        # neither, which is exactly the "nobody's data, not returned to
        # anyone" state that docstring already explains.
        try:
            conn.execute("ALTER TABLE sessions ADD COLUMN user_id TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE sessions ADD COLUMN anonymous_id TEXT")
        except sqlite3.OperationalError:
            pass
        # Same pattern for `return_session_id` (response-limit login UX
        # gap fix, see engine/decisions.md "Return to the same Journey
        # after magic-link verify") -- a magic-link row from before this
        # feature has none, which is exactly what NULL -> "don't reopen
        # any particular Journey after verify, same as before this
        # feature existed" already means.
        try:
            conn.execute("ALTER TABLE magic_links ADD COLUMN return_session_id TEXT")
        except sqlite3.OperationalError:
            pass
        # privacy_settings made per-account (2026-07-19, see
        # engine/decisions.md "privacy_settings made per-account") --
        # same non-additive-migration reasoning as learned_patterns/
        # insights above: the OLD shape ("id INTEGER PRIMARY KEY CHECK
        # (id = 1)", one shared row for every account) cannot be
        # expressed by the new shape's "CREATE TABLE IF NOT EXISTS
        # privacy_settings" ("user_id TEXT PRIMARY KEY"), so a database
        # created before this round keeps the old table forever unless
        # migrated here. The one existing row (if any) is a preference
        # that was never actually attributable to any specific
        # account -- same "drop rather than guess an owner" conclusion
        # POM's/Learning's/Insight's own migrations already reached.
        # No eager row-per-account insert replaces it --
        # get_cross_session_learning_enabled(user_id) below defaults to
        # True (same opt-out, not opt-in, default the old singleton
        # shipped with) when no row exists yet for that account, same
        # "no row until first read/written" pattern
        # get_personal_operating_model already established.
        old_shape_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(privacy_settings)").fetchall()
        }
        if "id" in old_shape_columns:
            conn.execute("DROP TABLE privacy_settings")
            conn.execute(
                "CREATE TABLE privacy_settings ("
                "user_id TEXT PRIMARY KEY, cross_session_learning_enabled INTEGER NOT NULL DEFAULT 1, "
                "FOREIGN KEY (user_id) REFERENCES users(id))"
            )
        # POM made per-user (2026-07-18, basic auth follow-up, see
        # engine/decisions.md "POM made per-user") -- `personal_operating_model`
        # was a genuine "id INTEGER PRIMARY KEY CHECK (id = 1)" global
        # singleton before real accounts existed. Unlike every other
        # migration in this function, this ISN'T additive -- the whole
        # point is that the OLD shape (one row, no owner) can no longer
        # be expressed at all; a `user_id TEXT PRIMARY KEY` table and a
        # `CHECK (id = 1)` table cannot both satisfy `CREATE TABLE IF NOT
        # EXISTS personal_operating_model`, so a database created before
        # this round keeps its OLD table forever unless explicitly
        # migrated here. The one existing row (if any) is a computed
        # profile that was never actually attributable to any specific
        # account -- once real per-user computation exists, keeping it
        # around under nobody's name would be actively misleading (see
        # the founder's own report that a brand-new signed-in user was
        # seeing an unrelated pre-auth POM as if it were their own), so
        # this drops it outright rather than trying to guess an owner
        # for data that fundamentally has none. Detected via PRAGMA
        # table_info rather than a version table (this codebase has
        # none) -- the old shape's `id` column is the one thing the new
        # shape doesn't have.
        old_shape_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(personal_operating_model)").fetchall()
        }
        if "id" in old_shape_columns:
            conn.execute("DROP TABLE personal_operating_model")
            conn.execute(
                "CREATE TABLE personal_operating_model ("
                "user_id TEXT PRIMARY KEY, pom_json TEXT NOT NULL, computed_at TEXT NOT NULL)"
            )
        # Learning made per-account (2026-07-18, see engine/decisions.md
        # "Learning made per-account" and engine/specs/learning-
        # specification-v1.md) -- same non-additive-migration reasoning
        # as personal_operating_model just above: `learned_patterns` was
        # a genuine global aggregate with no owner column at all before
        # this round. Detected via the same PRAGMA table_info technique
        # -- the old shape's absence of `user_id` is the one thing that
        # differs (unlike POM's old shape, this table's `id` column
        # exists in BOTH old and new shape, so `user_id` is the correct
        # differentiator here instead). The existing aggregate rows (if
        # any) are, by construction, no more attributable to one account
        # than POM's old singleton was -- same "drop rather than guess
        # an owner" conclusion, not a special case.
        learned_patterns_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(learned_patterns)").fetchall()
        }
        if learned_patterns_columns and "user_id" not in learned_patterns_columns:
            conn.execute("DROP TABLE learned_patterns")
            conn.execute(
                "CREATE TABLE learned_patterns ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL, "
                "pattern_type TEXT NOT NULL, detail TEXT NOT NULL, "
                "evidence_count INTEGER NOT NULL, computed_at TEXT NOT NULL, "
                "FOREIGN KEY (user_id) REFERENCES users(id))"
            )
        # Insight Engine made per-account (2026-07-19, see engine/decisions.md
        # "Insight Engine made per-account") -- same non-additive-migration
        # reasoning as learned_patterns just above, closing the gap #257
        # left open (that round only actually fixed learned_patterns despite
        # its own title naming Insight too). `insights` was a genuine global
        # aggregate with no owner column, read across every account's
        # sessions and injected unscoped into every live conversation's
        # Retrieved Context -- a real cross-account leak once real,
        # semantically-clustered personal content existed to leak. Its own
        # child table `insight_sessions` carries no owner column of its own
        # (it never needs one -- see get_insights' join) but its rows key
        # off `insights.id`, which is about to be regenerated with fresh
        # autoincrement values, so it must be dropped and recreated
        # alongside `insights` rather than left pointing at ids that no
        # longer mean anything.
        insights_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(insights)").fetchall()
        }
        if insights_columns and "user_id" not in insights_columns:
            conn.execute("DROP TABLE IF EXISTS insight_sessions")
            conn.execute("DROP TABLE insights")
            conn.execute(
                "CREATE TABLE insights ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL, "
                "theme TEXT NOT NULL, detail TEXT NOT NULL, computed_at TEXT NOT NULL, "
                "FOREIGN KEY (user_id) REFERENCES users(id))"
            )
            conn.execute(
                "CREATE TABLE insight_sessions ("
                "insight_id INTEGER NOT NULL, session_id TEXT NOT NULL, "
                "FOREIGN KEY (insight_id) REFERENCES insights(id), "
                "FOREIGN KEY (session_id) REFERENCES sessions(id))"
            )


def create_session(
    mode: Optional[str] = None,
    user_id: Optional[str] = None,
    anonymous_id: Optional[str] = None,
) -> str:
    """`mode` (Counseling modes, see engine/decisions.md and
    src/orchestrator/modes.py): chosen once, at creation, and fixed for
    the Journey's lifetime -- there is no `set_mode`, matching how
    `bookmarked` is the only session-level field this codebase ever lets
    a person change after the fact; mode is deliberately not one of
    those. `None` (every caller before this feature existed, and a
    person who skips picking one) is a completely valid, permanent
    state, not a placeholder awaiting a later choice.

    `user_id`/`anonymous_id` (basic auth, see module docstring): the
    caller (src/api/server.py's `create_session`, via `resolve_identity`)
    passes exactly one of these, never both -- a session begun while
    signed in belongs to that account; a session begun anonymously
    belongs to that browser's own anonymous id until/unless it's later
    claimed (see `claim_anonymous_sessions`)."""
    session_id = str(uuid.uuid4())
    now = _now()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO sessions (id, world_state_json, debug_json, created_at, updated_at, mode, user_id, anonymous_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (session_id, WorldState().model_dump_json(), None, now, now, mode, user_id, anonymous_id),
        )
    return session_id


def session_owner(session_id: str) -> Optional[Tuple[Optional[str], Optional[str]]]:
    """Returns (user_id, anonymous_id) for an existing session, or None
    if it doesn't exist -- src/api/server.py's `_require_owned_session`
    uses this to decide whether the caller's own resolved identity
    matches. A pre-auth session (see module docstring) returns
    (None, None), which never matches any real identity -- it's owned
    by nobody, not by whoever happens to ask."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT user_id, anonymous_id FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
    return tuple(row) if row else None


def get_or_create_user(email: str) -> str:
    """One row per email, created the first time it's ever seen -- there
    is no separate signup step distinct from "request a magic link for
    an email we haven't seen before" (matching the "as low friction as
    possible" brief: no separate account-creation form). Idempotent on
    a repeat email, matching every other `get_or_create_*`-shaped
    function's own convention elsewhere in this codebase."""
    with _connect() as conn:
        row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if row:
            return row[0]
        user_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO users (id, email, created_at) VALUES (?, ?, ?)",
            (user_id, email, _now()),
        )
    return user_id


def get_user_email(user_id: str) -> Optional[str]:
    with _connect() as conn:
        row = conn.execute("SELECT email FROM users WHERE id = ?", (user_id,)).fetchone()
    return row[0] if row else None


def create_magic_link(
    email: str, anonymous_id: Optional[str] = None, return_session_id: Optional[str] = None
) -> str:
    """`anonymous_id` (the requesting browser's own, if any -- see
    src/api/server.py's `resolve_identity`) rides along with the token
    so `consume_magic_link` can hand it straight to
    `claim_anonymous_sessions` once the link is actually clicked,
    without asking the browser to prove it twice.

    `return_session_id` (response-limit login UX gap fix, 2026-07-18,
    see engine/decisions.md "Return to the same Journey after
    magic-link verify"): the Journey the caller was actually in when
    they hit a login wall, if any -- rides along the same way so
    `consume_magic_link` can hand it back to /auth/verify without a
    second, separately-tamperable round trip through the emailed URL
    itself."""
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    with _connect() as conn:
        conn.execute(
            "INSERT INTO magic_links (token, email, anonymous_id, return_session_id, created_at, expires_at, used_at) "
            "VALUES (?, ?, ?, ?, ?, ?, NULL)",
            (
                token, email, anonymous_id, return_session_id,
                now.isoformat(), (now + MAGIC_LINK_LIFETIME).isoformat(),
            ),
        )
    return token


def consume_magic_link(token: str) -> Optional[Tuple[str, Optional[str], Optional[str]]]:
    """Validates and immediately burns a magic-link token -- returns
    (email, anonymous_id, return_session_id) on success, None if the
    token is unknown, already used, or past its 15-minute window (three
    distinct failure modes src/api/server.py's own /auth/verify
    deliberately collapses into one generic "that link isn't valid"
    response, rather than telling a caller WHICH of the three it hit --
    confirming "used" or "expired" specifically to an unauthenticated
    caller would leak whether a given token was ever real). Single-use:
    `used_at` is set in the same transaction as the read, so a token
    can't be raced or replayed even if the two are milliseconds apart."""
    now = datetime.now(timezone.utc)
    with _connect() as conn:
        row = conn.execute(
            "SELECT email, anonymous_id, return_session_id, expires_at, used_at "
            "FROM magic_links WHERE token = ?",
            (token,),
        ).fetchone()
        if row is None:
            return None
        email, anonymous_id, return_session_id, expires_at, used_at = row
        if used_at is not None:
            return None
        if datetime.fromisoformat(expires_at) < now:
            return None
        conn.execute(
            "UPDATE magic_links SET used_at = ? WHERE token = ?", (now.isoformat(), token)
        )
    return email, anonymous_id, return_session_id


def create_auth_session(user_id: str) -> str:
    """The signed-in browser's own long-lived login session (see module
    docstring for why 30 days) -- the resulting token is what
    src/api/server.py sets as an httpOnly cookie. Opaque and
    DB-revocable by design (`delete_auth_session` is a plain row
    delete), not a signed/self-describing JWT -- no secret-rotation
    story needed for an MVP this size."""
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    with _connect() as conn:
        conn.execute(
            "INSERT INTO auth_sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token, user_id, now.isoformat(), (now + AUTH_SESSION_LIFETIME).isoformat()),
        )
    return token


def get_user_id_for_auth_session(token: str) -> Optional[str]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT user_id, expires_at FROM auth_sessions WHERE token = ?", (token,)
        ).fetchone()
    if row is None:
        return None
    user_id, expires_at = row
    if datetime.fromisoformat(expires_at) < datetime.now(timezone.utc):
        return None
    return user_id


def delete_auth_session(token: str) -> None:
    """Logout -- a plain row delete, same "no soft-delete" honesty as
    every other delete in this file. Silently a no-op for an
    already-gone/unknown token, matching `delete_session`'s own
    tolerance of a caller that's already lost the race."""
    with _connect() as conn:
        conn.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))


def claim_anonymous_sessions(anonymous_id: str, user_id: str) -> None:
    """Signing up must not cost a person the Journeys they were already
    in the middle of (see module docstring) -- every session this
    browser's anonymous id owns gets handed to the new account instead,
    `anonymous_id` cleared in the same statement so the row now has
    exactly one owner, same invariant every freshly-created session
    already holds. Called once, right after a magic link is consumed
    (src/api/server.py's /auth/verify) -- a no-op if this browser had no
    anonymous Journeys yet (a brand-new visitor logging in immediately)."""
    with _connect() as conn:
        conn.execute(
            "UPDATE sessions SET user_id = ?, anonymous_id = NULL WHERE anonymous_id = ?",
            (user_id, anonymous_id),
        )


def get_session_mode(session_id: str) -> Optional[str]:
    with _connect() as conn:
        row = conn.execute("SELECT mode FROM sessions WHERE id = ?", (session_id,)).fetchone()
    return row[0] if row else None


def session_exists(session_id: str) -> bool:
    with _connect() as conn:
        row = conn.execute("SELECT 1 FROM sessions WHERE id = ?", (session_id,)).fetchone()
    return row is not None


def list_sessions(
    bookmarked_only: bool = False,
    user_id: Optional[str] = None,
    anonymous_id: Optional[str] = None,
) -> List[SessionSummary]:
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

    Only populated after a real message is shared (2026-07-18, see
    frontend/decisions.md): a session is created the moment a person
    picks a mode, before they've typed anything -- direct founder
    feedback that backing out of that empty Journey without sending
    anything shouldn't leave a permanent "A new Journey" ghost entry
    here. Filtered to sessions with at least one user message, read-path
    half of a two-part fix (Journey.svelte's own back-navigation is the
    other half -- it deletes an empty session outright rather than
    leaving an orphaned row for this filter to just hide forever).
    `get_all_sessions_raw`/`get_aggregated_knowledge_for_pom`/etc.
    deliberately stay unfiltered -- an empty WorldState contributes
    nothing to Learning/Insight Engine/POM computation either way, so
    there's no reason to touch those.

    `user_id`/`anonymous_id` (basic auth, see module docstring): the
    caller passes exactly one, resolved from the request's own identity
    (src/api/server.py's `resolve_identity`) -- this is what actually
    fixes the pre-auth "everyone sees the same global list" gap, not
    just an additional filter alongside `bookmarked_only`. A session
    with neither owner column set (created before this feature existed)
    matches no identity and is simply never returned, same as
    `_require_owned_session`'s own treatment of one.
    """
    query = "SELECT id, world_state_json, updated_at, bookmarked, mode FROM sessions " \
            "WHERE id IN (SELECT DISTINCT session_id FROM messages WHERE role = 'user')"
    params: List[Optional[str]]
    if user_id is not None:
        query += " AND user_id = ?"
        params = [user_id]
    else:
        query += " AND anonymous_id = ?"
        params = [anonymous_id]
    if bookmarked_only:
        query += " AND bookmarked = 1"
    query += " ORDER BY updated_at DESC"
    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()
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
    for session_id, world_state_json, updated_at, bookmarked, mode in rows:
        state = WorldState.model_validate_json(world_state_json)
        theme, detail = session_insight.get(session_id, (None, None))
        summaries.append(
            SessionSummary(
                id=session_id,
                preview_text=first_message.get(session_id) or state.surface_complaint,
                updated_at=updated_at,
                bookmarked=bool(bookmarked),
                mode=mode,
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


def get_bookmark(session_id: str) -> bool:
    """Journey.svelte's own overflow menu (see frontend/decisions.md
    "Tuck destructive/secondary Journey actions behind an overflow
    menu") needs a session's CURRENT bookmark state before it can
    render the toggle correctly -- Home gets this for free from
    list_sessions (it already has the whole list), but Journey never
    fetches that. Same "SELECT one column WHERE id" shape as
    get_session_mode right above."""
    with _connect() as conn:
        row = conn.execute("SELECT bookmarked FROM sessions WHERE id = ?", (session_id,)).fetchone()
    return bool(row[0]) if row else False


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
    """Read-only, unscoped across every account -- kept only as an
    internal/test helper (used by tests/test_api_server.py's own
    behavioral-events assertions), never called from a live request or
    an offline computation script. Learning made per-account (2026-07-18,
    see engine/decisions.md "Learning made per-account") -- the real
    computation path is `get_events_for_user` below; this function
    intentionally stays a global, unscoped read, same "global views are
    for internal debugging only, never a live/user-facing surface"
    principle "POM made per-user" already established."""
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


def get_events_for_user(user_id: str) -> List[BehavioralEvent]:
    """Learning made per-account (2026-07-18, see engine/decisions.md
    "Learning made per-account") -- the real per-account counterpart to
    `get_all_events` above. `behavioral_events` has no `user_id` column
    of its own (only `session_id`), so this joins through `sessions` to
    scope to THIS account's own Journeys only, same pattern
    `get_aggregated_knowledge_for_pom` already uses for POM. What
    `scripts/run_learning.py` now actually calls, once per account."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT be.event_type, be.session_id, be.turn, be.detail, be.old_status, "
            "be.new_status, be.created_at FROM behavioral_events be "
            "JOIN sessions s ON be.session_id = s.id "
            "WHERE s.user_id = ? ORDER BY be.id ASC",
            (user_id,),
        ).fetchall()
    return [
        BehavioralEvent(
            event_type=r[0], session_id=r[1], turn=r[2], detail=r[3],
            old_status=r[4], new_status=r[5], timestamp=r[6],
        )
        for r in rows
    ]


def replace_learned_patterns(user_id: str, patterns: List[Pattern]) -> None:
    """Truncate-and-replace per account, not append or global truncate
    (2026-07-18, see engine/decisions.md "Learning made per-account") --
    same "latest wins, scoped to one owner" precedent
    `replace_personal_operating_model` already established for POM.
    Called only by scripts/run_learning.py, never from a live request."""
    now = _now()
    with _connect() as conn:
        conn.execute("DELETE FROM learned_patterns WHERE user_id = ?", (user_id,))
        if patterns:
            conn.executemany(
                "INSERT INTO learned_patterns (user_id, pattern_type, detail, evidence_count, computed_at) "
                "VALUES (?, ?, ?, ?, ?)",
                [(user_id, p.pattern_type, p.detail, p.evidence_count, now) for p in patterns],
            )


def get_learned_patterns(user_id: str) -> List[LearnedPatternOut]:
    """Learning made per-account (2026-07-18, see engine/decisions.md
    "Learning made per-account") -- returns None-equivalent empty list
    until scripts/run_learning.py has computed THIS account's own
    patterns at least once; never another account's, same "POM made
    per-user" precedent."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT pattern_type, detail, evidence_count FROM learned_patterns "
            "WHERE user_id = ? ORDER BY id ASC",
            (user_id,),
        ).fetchall()
    return [LearnedPatternOut(pattern_type=r[0], detail=r[1], evidence_count=r[2]) for r in rows]


def get_session_texts_for_insights(user_id: str) -> List[Tuple[str, str, str]]:
    """Insight Engine made per-account (2026-07-19, see engine/decisions.md
    "Insight Engine made per-account") -- reads THIS account's own
    sessions only. Before this, the unscoped query read the most-
    recently-updated sessions across every account on the server, which
    also meant a real bug beyond the privacy one: on a server with
    several active accounts, another account's more-recent activity
    could crowd this account's own sessions out of the
    MAX_SESSIONS_FOR_INSIGHT window entirely, occasionally leaving an
    account with real history seeing zero of its own sessions
    considered. Scoping to `user_id` first fixes both at once -- same
    guard as src/api/server.py's get_clarity_brief endpoint -- only
    sessions whose debug_json actually has a completed `judgment` (a
    session with no completed turn has nothing to extract a
    surface_complaint/primary_problem pair from). Capped at
    MAX_SESSIONS_FOR_INSIGHT most-recently-updated sessions -- now a
    genuine per-account recency cap, same cost/latency reasoning as
    src/insight/schema.py's docstring."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, world_state_json, debug_json FROM sessions "
            "WHERE user_id = ? ORDER BY updated_at DESC LIMIT ?",
            (user_id, MAX_SESSIONS_FOR_INSIGHT),
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


def replace_insights(user_id: str, insights: List[Insight]) -> None:
    """Insight Engine made per-account (2026-07-19) -- truncate-and-
    replace THIS account's own share only (mirrors
    replace_learned_patterns' precedent), not a global truncate.
    Called only by scripts/run_insight_detection.py, once per account,
    never from a live request."""
    now = _now()
    with _connect() as conn:
        conn.execute(
            "DELETE FROM insight_sessions WHERE insight_id IN "
            "(SELECT id FROM insights WHERE user_id = ?)",
            (user_id,),
        )
        conn.execute("DELETE FROM insights WHERE user_id = ?", (user_id,))
        for insight in insights:
            cursor = conn.execute(
                "INSERT INTO insights (user_id, theme, detail, computed_at) VALUES (?, ?, ?, ?)",
                (user_id, insight.theme, insight.detail, now),
            )
            insight_id = cursor.lastrowid
            conn.executemany(
                "INSERT INTO insight_sessions (insight_id, session_id) VALUES (?, ?)",
                [(insight_id, sid) for sid in insight.evidence_session_ids],
            )


def get_insights(user_id: str) -> List[InsightOut]:
    """Insight Engine made per-account (2026-07-19, see engine/decisions.md
    "Insight Engine made per-account") -- returns THIS account's own
    insights only; never another account's, same "POM made per-user"/
    "Learning made per-account" precedent."""
    with _connect() as conn:
        insight_rows = conn.execute(
            "SELECT id, theme, detail FROM insights WHERE user_id = ? ORDER BY id ASC",
            (user_id,),
        ).fetchall()
        insight_ids = [row[0] for row in insight_rows]
        evidence_rows = []
        if insight_ids:
            placeholders = ",".join("?" * len(insight_ids))
            evidence_rows = conn.execute(
                f"SELECT insight_id, session_id FROM insight_sessions WHERE insight_id IN ({placeholders})",
                insight_ids,
            ).fetchall()
    evidence_by_insight: dict = {}
    for insight_id, session_id in evidence_rows:
        evidence_by_insight.setdefault(insight_id, []).append(session_id)
    return [
        InsightOut(theme=theme, detail=detail, evidence_session_ids=evidence_by_insight.get(insight_id, []))
        for insight_id, theme, detail in insight_rows
    ]


def get_aggregated_knowledge_for_pom(user_id: str) -> Tuple[List[str], List[str], List[Entity], str]:
    """
    POM made per-user (2026-07-18, see engine/decisions.md "POM made
    per-user") -- reads every session OWNED BY THIS ACCOUNT (uncapped
    within that scope, same as get_all_sessions_raw's own "POM is an
    all-history model, not a recency-capped sample" reasoning, just no
    longer all-history across every account). An anonymous-owned
    session (never claimed via login) is correctly excluded -- POM only
    ever reflects a real, standing account's own claimed history, never
    a browser that hasn't signed up. Aggregates into what
    src/pom/engine.py::compute_personal_operating_model needs: (claims,
    assumptions, entities, aggregated_content) -- the first three feed
    the two mechanical systems directly; aggregated_content is a single
    plain-text rendering of everything (facts, claims, goals,
    decisions, entities, emotional signals) for the one LLM call that
    infers the other six systems.

    Read-only, used only by scripts/run_pom_computation.py -- this
    module has no opinion on POM itself, same separation as
    get_session_texts_for_insights above.
    """
    with _connect() as conn:
        rows = conn.execute(
            "SELECT world_state_json FROM sessions WHERE user_id = ?", (user_id,)
        ).fetchall()

    claims: List[str] = []
    assumptions: List[str] = []
    entities: List[Entity] = []
    lines: List[str] = []
    for (world_state_json,) in rows:
        state = WorldState.model_validate_json(world_state_json)
        claims += [c.content for c in state.claims]
        assumptions += list(state.assumptions)
        entities += list(state.entities)

        lines += [f"Fact: {f.content}" for f in state.facts]
        lines += [f"Claim: {c.content}" for c in state.claims]
        lines += [f"Goal: {g.content}" for g in state.goals]
        lines += [f"Decision: {d.content}" for d in state.decisions]
        lines += [f"Assumption: {a}" for a in state.assumptions]
        for entity in state.entities:
            attr_text = "; ".join(f"{a.attribute} is {a.value}" for a in entity.attributes)
            rel_text = "; ".join(entity.relationships)
            lines.append(f"Entity: {entity.name}" + (f" -- {attr_text} {rel_text}".rstrip() if attr_text or rel_text else ""))
        for signal in state.emotional_signal_items:
            lines.append(f"Emotional signal: {signal.emotion} (intensity={signal.intensity}, source={signal.source})")

    aggregated_content = "\n".join(lines)
    return claims, assumptions, entities, aggregated_content


def get_all_user_ids_with_sessions() -> List[str]:
    """Every account that owns at least one Journey -- what
    scripts/run_pom_computation.py loops over to compute one POM per
    account (see engine/decisions.md "POM made per-user"). Anonymous-only
    browsers (never signed in) have no `user_id` and are correctly
    excluded -- there's no stable account to attach a standing profile
    to yet."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT user_id FROM sessions WHERE user_id IS NOT NULL"
        ).fetchall()
    return [row[0] for row in rows]


def replace_personal_operating_model(user_id: str, pom: PersonalOperatingModel) -> None:
    """Truncate-and-replace per account, not append -- POM is one
    standing profile per person, not an accumulating log (same
    "latest wins" precedent as `learned_patterns`' own truncate-and-replace,
    just keyed per `user_id` now instead of one shared row). Called only
    by scripts/run_pom_computation.py."""
    with _connect() as conn:
        conn.execute(
            "INSERT INTO personal_operating_model (user_id, pom_json, computed_at) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET pom_json = excluded.pom_json, computed_at = excluded.computed_at",
            (user_id, pom.model_dump_json(), _now()),
        )


def get_personal_operating_model(user_id: str) -> Optional[PersonalOperatingModel]:
    """Returns None until scripts/run_pom_computation.py has computed
    THIS account's own POM at least once -- a brand-new account
    correctly has no POM yet, not an error state, and never inherits
    another account's (see engine/decisions.md "POM made per-user")."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT pom_json FROM personal_operating_model WHERE user_id = ?", (user_id,)
        ).fetchone()
    if row is None:
        return None
    return PersonalOperatingModel.model_validate_json(row[0])


# Privacy, made real (2026-07-18, see frontend/decisions.md): the first
# actual controls behind Settings' Privacy card, previously just a
# static sentence ("Controls for what Confidant remembers and how it's
# used") with nothing behind it.


def get_cross_session_learning_enabled(user_id: str) -> bool:
    """privacy_settings made per-account (2026-07-19, see
    engine/decisions.md "privacy_settings made per-account") -- returns
    THIS account's own preference; never another account's. Defaults to
    True (opt-out, not opt-in) when no row exists yet for this account
    -- same None-means-default pattern get_personal_operating_model
    already established, just with a real default value instead of
    None (a preference always has a sensible default; a computed
    profile doesn't)."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT cross_session_learning_enabled FROM privacy_settings WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return bool(row[0]) if row else True


def set_cross_session_learning_enabled(user_id: str, enabled: bool) -> None:
    """Upsert, keyed on user_id -- same pattern
    replace_personal_operating_model already established, since (unlike
    the old singleton) there's no guaranteed row to UPDATE on a
    account's first-ever write."""
    with _connect() as conn:
        conn.execute(
            "INSERT INTO privacy_settings (user_id, cross_session_learning_enabled) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET cross_session_learning_enabled = excluded.cross_session_learning_enabled",
            (user_id, 1 if enabled else 0),
        )


def _rows_for_session_ids(conn: sqlite3.Connection, table: str, session_ids: List[str]) -> List[dict]:
    """Small shared helper for export_all_data/reset_all_data below --
    both need "every row in this child table that belongs to one of
    THESE session ids" at least twice each. An empty `session_ids`
    (an account with no Journeys yet) short-circuits to `[]` rather
    than emitting `WHERE session_id IN ()`, which SQLite rejects as
    invalid syntax."""
    if not session_ids:
        return []
    placeholders = ",".join("?" * len(session_ids))
    conn.row_factory = sqlite3.Row
    return [dict(row) for row in conn.execute(
        f"SELECT * FROM {table} WHERE session_id IN ({placeholders})", session_ids
    )]


def export_all_data(user_id: str) -> dict:
    """Everything Confidant has ever stored about THIS ACCOUNT, as one
    plain JSON-serializable document.

    Scoped per account (2026-07-18, see engine/decisions.md "POM made
    per-user") -- this shipped alongside making POM per-user, since
    both were the same underlying bug: real personal content with zero
    account scoping. Before this fix, ANY signed-in visitor's "Export
    your data" downloaded EVERY account's Journeys -- correct back when
    this app served exactly one person, a real cross-account data leak
    once real accounts existed to leak between.

    Scoped to sessions this account itself owns (`sessions.user_id`),
    plus every child row that references one of those sessions
    (messages/behavioral_events/insight_sessions -- same "keyed on
    session_id" pattern delete_session already uses, just for many
    sessions at once via `_rows_for_session_ids`).

    `insights` (2026-07-19, see engine/decisions.md "Insight Engine made
    per-account") is now scoped directly by THIS account's own
    `user_id`, same as `learned_patterns` below -- previously selected
    indirectly via `insight_sessions` under the reasoning that "an
    Insight is a genuine cross-account theme that may also be evidenced
    by someone else's Journey," which was true only because `insights`
    had no owner column at all; now that it does, an Insight is exactly
    as much "this account's own data" as a session is.

    `learned_patterns` (2026-07-18, see engine/decisions.md "Learning
    made per-account") is included too, scoped to THIS account's
    own `user_id` -- previously excluded entirely because the table had
    no per-account attribution at all; now that it does, the same
    "include what's genuinely this account's own" rule POM's row
    already follows applies here too.

    `privacy_settings` (2026-07-19, see engine/decisions.md
    "privacy_settings made per-account") is now included too, for the
    same reason -- previously not included at all (the table was a
    single global row, not attributable to any one account); now it's
    genuinely this account's own stated preference. `None` (no row
    yet, defaulting to the standard `True`) is a real, correct value to
    export, not an error -- same "not yet set" treatment
    `personal_operating_model`'s own `None` case gets below.

    `*_json` TEXT columns are parsed back into real nested objects
    rather than left as escaped strings, so the exported file is
    actually readable by a person, not just re-ingestable by this
    codebase."""
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        sessions = [dict(row) for row in conn.execute(
            "SELECT * FROM sessions WHERE user_id = ?", (user_id,)
        )]
        session_ids = [s["id"] for s in sessions]
        messages = _rows_for_session_ids(conn, "messages", session_ids)
        behavioral_events = _rows_for_session_ids(conn, "behavioral_events", session_ids)
        insight_sessions = _rows_for_session_ids(conn, "insight_sessions", session_ids)
        insights = [dict(row) for row in conn.execute(
            "SELECT * FROM insights WHERE user_id = ?", (user_id,)
        )]
        learned_patterns = [dict(row) for row in conn.execute(
            "SELECT * FROM learned_patterns WHERE user_id = ?", (user_id,)
        )]
        pom_row = conn.execute(
            "SELECT * FROM personal_operating_model WHERE user_id = ?", (user_id,)
        ).fetchone()
        pom_row = dict(pom_row) if pom_row else None
        privacy_settings_row = conn.execute(
            "SELECT * FROM privacy_settings WHERE user_id = ?", (user_id,)
        ).fetchone()
        privacy_settings_row = dict(privacy_settings_row) if privacy_settings_row else None

    for session in sessions:
        session["world_state"] = json.loads(session.pop("world_state_json"))
        debug_json = session.pop("debug_json")
        session["debug"] = json.loads(debug_json) if debug_json else None
    for message in messages:
        options_json = message.pop("options_json")
        message["options"] = json.loads(options_json) if options_json else []
    if pom_row is not None:
        pom_row["personal_operating_model"] = json.loads(pom_row.pop("pom_json"))

    return {
        "exported_at": _now(),
        "sessions": sessions,
        "messages": messages,
        "behavioral_events": behavioral_events,
        "insights": insights,
        "insight_sessions": insight_sessions,
        "learned_patterns": learned_patterns,
        "personal_operating_model": pom_row,
        "privacy_settings": privacy_settings_row,
    }


def reset_all_data(user_id: str) -> None:
    """"Forget everything" for THIS ACCOUNT -- irreversible, same as
    delete_session's own lack of an undo path, just wider.

    Scoped per account (2026-07-18, see engine/decisions.md "POM made
    per-user") -- before this fix, ANY signed-in visitor's "Forget
    everything" deleted EVERY account's Journeys system-wide, the same
    underlying bug as export_all_data's own (see that function's
    docstring for the full reasoning).

    Deletes this account's own sessions, messages, behavioral events,
    this account's own insight_sessions evidence links, this account's
    own learned_patterns rows, this account's own Personal Operating
    Model row, and (2026-07-19, see engine/decisions.md "Insight Engine
    made per-account") this account's own `insights` rows -- previously
    left untouched under the reasoning that "an Insight may still be
    evidenced by someone else's Journey even after this account's own
    evidence link is removed," which was true only because `insights`
    had no owner column to delete by; now that it does, "forget
    everything" can and should actually forget it, same as
    `learned_patterns` below. `privacy_settings` stays untouched, same
    as before: a person clearing their journal data is not also asking
    to have their own stated cross-session-learning preference silently
    reset back to the default -- now genuinely THIS account's own row
    being preserved (2026-07-19, see engine/decisions.md "privacy_settings
    made per-account"), not a shared global one every account used to
    have equal, unwanted influence over.

    `learned_patterns` (2026-07-18, see engine/decisions.md "Learning
    made per-account") IS deleted here too -- previously excluded for
    the same reason `insights` used to be (no way to attribute one
    account's share of a shared aggregate), but now that both tables
    have real per-account ownership, "forget everything" actually
    forgets them."""
    with _connect() as conn:
        session_ids = [
            row[0] for row in conn.execute("SELECT id FROM sessions WHERE user_id = ?", (user_id,)).fetchall()
        ]
        if session_ids:
            placeholders = ",".join("?" * len(session_ids))
            conn.execute(f"DELETE FROM messages WHERE session_id IN ({placeholders})", session_ids)
            conn.execute(f"DELETE FROM behavioral_events WHERE session_id IN ({placeholders})", session_ids)
            conn.execute(f"DELETE FROM insight_sessions WHERE session_id IN ({placeholders})", session_ids)
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM learned_patterns WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM insights WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM personal_operating_model WHERE user_id = ?", (user_id,))
