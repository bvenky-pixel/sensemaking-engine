"""
Learning v1 -- offline pattern computation (see
engine/specs/architecture-roadmap-v1.md Phase 1, src/learning/engine.py).

Reads the entire Memory Store (src/api/db.py's `behavioral_events`
table, across every session -- single-user scope, no user_id column),
computes evidence-counted patterns via compute_behavioral_patterns, and
replaces `learned_patterns` wholesale (truncate-and-replace, not
append -- see db.py module docstring).

Run manually, or via a GitHub Actions workflow_dispatch (see
.github/workflows/learning-walkthrough.yml). Never called from
src/api/server.py or any other live request path -- this is what makes
"Learning operates asynchronously, never inside a live conversation
turn" (engine/specs/system-architecture-v2-specification.md) literally
true rather than just documented.

Usage: python scripts/run_learning.py [--db-path PATH]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api import db
from src.learning.engine import MIN_EVIDENCE, compute_behavioral_patterns


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="Override CONFIDANT_DB_PATH for this run (defaults to db.py's own resolution).",
    )
    args = parser.parse_args()

    db.init_db(Path(args.db_path) if args.db_path else None)

    events = db.get_all_events()
    print(f"Read {len(events)} behavioral event(s) from the Memory Store.")

    patterns = compute_behavioral_patterns(events)
    db.replace_learned_patterns(patterns)

    if not patterns:
        print(
            f"No patterns met the evidence floor (min_evidence={MIN_EVIDENCE}). "
            "learned_patterns is now empty -- correct behavior when evidence is thin, not an error."
        )
        return

    print(f"\nComputed {len(patterns)} pattern(s):")
    for p in patterns:
        print(f"- [{p.pattern_type}] {p.detail} (evidence_count={p.evidence_count})")


if __name__ == "__main__":
    main()
