"""
Insight Engine -- offline cross-session theme detection (see
src/insight/engine.py, engine/decisions.md "Major update").

Reads every session with a completed Judgment (src/api/db.py's
`get_session_texts_for_insights`, capped at MAX_SESSIONS_FOR_INSIGHT
most-recently-updated), calls run_insight_detection for real semantic
clustering, and replaces `insights`/`insight_sessions` wholesale
(truncate-and-replace, not append -- see db.py module docstring).

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

    session_texts = db.get_session_texts_for_insights()
    print(f"Read {len(session_texts)} session(s) with a completed Judgment.")

    insights = run_insight_detection(session_texts)
    db.replace_insights(insights)

    if not insights:
        print(
            f"No themes met the evidence floor (min_evidence_sessions={MIN_EVIDENCE_SESSIONS}). "
            "insights is now empty -- correct behavior when evidence is thin, not an error."
        )
        return

    print(f"\nDetected {len(insights)} theme(s):")
    for i in insights:
        print(f"- [{i.theme}] {i.detail} (evidence_session_ids={i.evidence_session_ids})")


if __name__ == "__main__":
    main()
