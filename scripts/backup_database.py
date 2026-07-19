"""
Database backup -- offline utility (2026-07-19, backlog #231, see
engine/decisions.md "Backup strategy for the production SQLite
volume"). Dumps CONFIDANT_DB_PATH to stdout as a portable SQL text
script (schema + every row), using Python's own stdlib
`sqlite3.Connection.iterdump()` -- deliberately NOT the `sqlite3` CLI
binary (`sqlite3 db.db .dump`), which the production image does not
have: `Dockerfile`'s base is `python:3.11-slim`, which ships Python's
own sqlite3 module (linked against libsqlite3) but not the separate
command-line tool. Pure stdlib means this needs nothing added to the
image to work.

Consistency: opened read-only (`mode=ro` URI) so this can never
accidentally create or write anything, and wrapped in one explicit
`BEGIN DEFERRED` transaction before iterdump() runs and rolled back
(never committed -- there's nothing to commit) after -- SQLite gives a
transaction a consistent snapshot for its own duration, so every
table's rows in the resulting dump reflect the exact same instant, not
whatever was committed by the time iterdump() got around to querying
each table in turn (a real, if small-scale, risk on a live database
serving concurrent requests while this runs).

The resulting .sql text restores into a fresh, empty database with:
    sqlite3.connect("restored.db").executescript(open("dump.sql").read())
(or the `sqlite3` CLI's own `sqlite3 restored.db < dump.sql`, wherever
that binary IS available -- a developer's own machine, not the
container). See engine/decisions.md for the full restore runbook --
deliberately a documented manual procedure, not an automated
workflow_dispatch: restoring overwrites a live database, which is
exactly the kind of destructive action this codebase's own standing
discipline keeps hand-operated rather than one click away.

Run manually, or via a GitHub Actions workflow_dispatch (see
.github/workflows/backup-database.yml, manual-only for now -- whether
to also run this on a recurring schedule is a separate, deliberate
decision, not a default).

Usage: python scripts/backup_database.py [--db-path PATH] > backup.sql
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api import db


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="Override CONFIDANT_DB_PATH for this run (defaults to db.py's own resolution).",
    )
    args = parser.parse_args()

    db_path = Path(args.db_path) if args.db_path else db.DB_PATH
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        conn.execute("BEGIN DEFERRED")
        for line in conn.iterdump():
            sys.stdout.write(f"{line}\n")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
