"""
Personal Operating Model -- offline computation (see src/pom/engine.py,
engine/decisions.md "Personal Operating Model").

Reads every session's WorldState (src/api/db.py::get_aggregated_knowledge_for_pom,
uncapped -- POM is a single-person, all-history profile, not a
recency-capped sample), computes the two mechanical systems plus one LLM
call for the other six, and replaces the stored
`personal_operating_model` row wholesale (truncate-and-replace, single
row -- see db.py's own table CHECK constraint).

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

    # Privacy, made real (2026-07-18, see frontend/decisions.md) --
    # defense in depth alongside src/api/server.py's own read-path gate;
    # see run_learning.py's identical guard for the full reasoning. POM
    # is arguably the MOST personal of the three cross-session artifacts
    # (an inferred profile of beliefs/motivation/identity), so honoring
    # the opt-out here is not optional.
    if not db.get_cross_session_learning_enabled():
        print("Cross-session learning is disabled in Privacy settings -- skipping (no-op).")
        return

    claims, assumptions, entities, aggregated_content = db.get_aggregated_knowledge_for_pom()
    print(
        f"Aggregated {len(claims)} claim(s), {len(assumptions)} assumption(s), "
        f"{len(entities)} entit(y/ies) across every session."
    )

    pom = compute_personal_operating_model(claims, assumptions, entities, aggregated_content)
    db.replace_personal_operating_model(pom)

    print("\nBelief:")
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
