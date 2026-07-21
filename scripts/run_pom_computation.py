"""
Personal Operating Model -- offline computation (see src/pom/engine.py,
engine/decisions.md "Personal Operating Model").

POM made per-user (2026-07-18, see engine/decisions.md "POM made
per-user"): reads each account's own sessions' WorldState
(src/api/db.py::get_aggregated_knowledge_for_pom(user_id), capped at
MAX_SESSIONS_FOR_POM most-recently-updated sessions since 2026-07-19,
backlog #272, see engine/decisions.md "POM: recency cap added to
aggregation" -- previously uncapped), one account at a time, computes
the two mechanical systems
plus one LLM call for the other six per account, and replaces that
account's own `personal_operating_model` row (upsert, keyed on
user_id -- see db.py's own schema). Every user-facing surface in this
app is scoped to one account's own data; this offline job mirrors that
same discipline rather than computing a single cross-account profile.

Run manually, or via a GitHub Actions workflow_dispatch. Never called
from src/api/server.py or any other live request path -- same
"operates asynchronously, never inside a live conversation turn"
boundary Learning and Insight Engine already established.

Usage: python scripts/run_pom_computation.py [--db-path PATH]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api import db
from src.pom.engine import compute_personal_operating_model


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
    print(f"Computing POM for {len(user_ids)} account(s).")

    for user_id in user_ids:
        # Privacy, made real (2026-07-18, see frontend/decisions.md) --
        # defense in depth alongside src/api/server.py's own read-path
        # gate; see run_learning.py's identical guard for the full
        # reasoning. POM is arguably the MOST personal of the three
        # cross-session artifacts (an inferred profile of beliefs/
        # motivation/identity), so honoring the opt-out here is not
        # optional. privacy_settings made per-account (2026-07-19, see
        # engine/decisions.md "privacy_settings made per-account") --
        # checked per account inside the loop now, so one account's
        # opt-out only skips THEIR OWN computation, not every account's.
        if not db.get_cross_session_learning_enabled(user_id):
            print(f"\n=== {user_id} ===\nCross-session learning is disabled in Privacy settings -- skipping (no-op).")
            continue

        claims, assumptions, entities, aggregated_content = db.get_aggregated_knowledge_for_pom(user_id)
        events = db.get_events_for_user(user_id)
        print(
            f"\n=== {user_id} ==="
            f"\nAggregated {len(claims)} claim(s), {len(assumptions)} assumption(s), "
            f"{len(entities)} entit(y/ies), {len(events)} behavioral event(s) across this account's sessions."
        )

        pom = compute_personal_operating_model(claims, assumptions, entities, aggregated_content, events)
        db.replace_personal_operating_model(user_id, pom)

        print("Belief:")
        print(f"  {len(pom.belief.beliefs)} belief(s)")
        print("Relationship:")
        print(f"  {len(pom.relationship.relationships)} relationship(s)")
        print(f"Identity: {pom.identity.self_concept or '(unclear)'}")
        print(
            "Motivation (Self-Determination Theory): "
            f"autonomy={pom.motivation.autonomy}, competence={pom.motivation.competence}, "
            f"relatedness={pom.motivation.relatedness}"
        )
        print(f"Learning style: {pom.learning_style.style or '(unclear)'}")
        print(f"Stress: {pom.stress.level}")
        print(f"Narrative arc: {pom.narrative.arc} -- {pom.narrative.summary or '(no summary)'}")
        print(f"Theory of mind: {len(pom.theory_of_mind.entries)} entr(y/ies)")
        for entry in pom.theory_of_mind.entries:
            print(f"  - {entry.entity_name}: {entry.inferred_perspective}")


if __name__ == "__main__":
    main()
