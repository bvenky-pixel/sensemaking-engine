"""
Learning v1 -- offline pattern computation (see
engine/specs/architecture-roadmap-v1.md Phase 1, src/learning/engine.py,
engine/specs/learning-specification-v1.md).

Learning made per-account (2026-07-18, see engine/decisions.md
"Learning made per-account"): reads each account's own behavioral
events (src/api/db.py::get_events_for_user(user_id), joined through
`sessions` since `behavioral_events` has no `user_id` column of its
own), one account at a time, computes evidence-counted patterns via
compute_behavioral_patterns, and replaces THAT account's own share of
`learned_patterns` (truncate-and-replace per account, not a global
truncate -- see db.py's own docstring). Same per-account discipline
scripts/run_pom_computation.py already established -- every
user-facing surface in this app is scoped to one account's own data;
this offline job mirrors that rather than computing one cross-account
aggregate.

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

    # Privacy, made real (2026-07-18, see frontend/decisions.md) --
    # defense in depth alongside src/api/server.py's own read-path gate:
    # this is the actual write path for `learned_patterns`, so honoring
    # the opt-out here too means it holds even if this script is ever
    # run on a schedule rather than only by hand. Still a global,
    # cross-account setting today (see engine/decisions.md "POM made
    # per-user"'s own note on privacy_settings remaining a separate,
    # not-yet-started per-account project) -- not something this round
    # touches.
    if not db.get_cross_session_learning_enabled():
        print("Cross-session learning is disabled in Privacy settings -- skipping (no-op).")
        return

    user_ids = db.get_all_user_ids_with_sessions()
    if not user_ids:
        print("No accounts with any sessions yet -- nothing to compute.")
        return
    print(f"Computing behavioral patterns for {len(user_ids)} account(s).")

    for user_id in user_ids:
        events = db.get_events_for_user(user_id)
        patterns = compute_behavioral_patterns(events)
        db.replace_learned_patterns(user_id, patterns)

        print(f"\n=== {user_id} ===")
        print(f"Read {len(events)} behavioral event(s).")
        if not patterns:
            print(
                f"No patterns met the evidence floor (min_evidence={MIN_EVIDENCE}) -- "
                "correct behavior when evidence is thin, not an error."
            )
            continue
        print(f"Computed {len(patterns)} pattern(s):")
        for p in patterns:
            print(f"- [{p.pattern_type}] {p.detail} (evidence_count={p.evidence_count})")


if __name__ == "__main__":
    main()
