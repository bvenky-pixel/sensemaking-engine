"""
Insight Engine -- offline cross-session theme detection (see
src/insight/engine.py, engine/decisions.md "Major update").

Insight Engine made per-account (2026-07-19, see engine/decisions.md
"Insight Engine made per-account"): reads each account's own sessions
with a completed Judgment (src/api/db.py's
`get_session_texts_for_insights(user_id)`, capped at
MAX_SESSIONS_FOR_INSIGHT most-recently-updated per account), one
account at a time, calls run_insight_detection for real semantic
clustering over THAT account's own history, and replaces THAT
account's own share of `insights`/`insight_sessions`
(truncate-and-replace per account, not a global truncate -- see db.py's
own docstring). Same per-account discipline
scripts/run_learning.py/run_pom_computation.py already established --
every user-facing surface in this app is scoped to one account's own
data; this offline job mirrors that rather than computing one
cross-account aggregate (which is what it did before this round, and
which `send_message` then injected, unscoped, into every live
conversation regardless of who was asking).

Run manually, or via a GitHub Actions workflow_dispatch. Never called
from src/api/server.py or any other live request path -- same
"operates asynchronously, never inside a live conversation turn"
boundary Learning already established (see src/insight/__init__.py).

Usage: python scripts/run_insight_detection.py [--db-path PATH]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api import db
from src.insight.engine import MIN_EVIDENCE_SESSIONS, run_insight_detection


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

    user_ids = db.get_all_user_ids_with_sessions()
    if not user_ids:
        print("No accounts with any sessions yet -- nothing to compute.")
        return
    print(f"Detecting insights for {len(user_ids)} account(s).")

    for user_id in user_ids:
        # Privacy, made real (2026-07-18, see frontend/decisions.md) --
        # defense in depth alongside src/api/server.py's own read-path
        # gate; see run_learning.py's identical guard for the full
        # reasoning. privacy_settings made per-account (2026-07-19, see
        # engine/decisions.md "privacy_settings made per-account") --
        # checked per account inside the loop now, so one account's
        # opt-out only skips THEIR OWN computation, not every account's.
        if not db.get_cross_session_learning_enabled(user_id):
            print(f"\n=== {user_id} ===\nCross-session learning is disabled in Privacy settings -- skipping (no-op).")
            continue

        session_texts = db.get_session_texts_for_insights(user_id)
        print(f"\n=== {user_id} ===")
        print(f"Read {len(session_texts)} session(s) with a completed Judgment.")

        insights = run_insight_detection(session_texts)
        db.replace_insights(user_id, insights)

        if not insights:
            print(
                f"No themes met the evidence floor (min_evidence_sessions={MIN_EVIDENCE_SESSIONS}). "
                "This account's insights are now empty -- correct behavior when evidence is thin, not an error."
            )
            continue

        print(f"Detected {len(insights)} theme(s):")
        for i in insights:
            print(f"- [{i.theme}] {i.detail} (evidence_session_ids={i.evidence_session_ids})")


if __name__ == "__main__":
    main()
