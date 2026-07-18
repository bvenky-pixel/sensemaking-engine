"""
Personal Operating Model -- live walkthrough (see src/pom/engine.py,
engine/decisions.md "Personal Operating Model").

The one thing pytest coverage (tests/test_pom_engine.py) can't verify:
whether a REAL model produces sensible, well-grounded Identity/
Motivation/Learning-Style/Stress/Narrative/Theory-of-Mind inferences
from real conversation content, and whether the engine-level grounding
enforcement (_ground_batch) actually fires correctly against real model
output rather than only the hand-built fixtures the unit tests use.

Drives two short, independent sessions through the REAL pipeline
(run_turn -- the same Orchestrator entrypoint the live API uses),
persisted via src/api/db.py (create_session/save_turn_result, same as
a real live conversation), each written to touch different POM systems:
- Session A: identity/motivation/decision content (autonomy, competence,
  a job offer being weighed).
- Session B: relationship/stress/narrative content (a named person with
  a real attribute, stress under a deadline, a hard-patch-then-
  improvement arc).

Then runs the real POM computation (src/pom/engine.py::compute_personal_operating_model)
against BOTH sessions' aggregated content and prints every system's
output in full, for a human to read and judge -- same "qualitative call
this script doesn't attempt to auto-grade" posture as
run_worldstate_walkthrough.py.

Not part of the automated test suite: this makes real, billable API
calls (up to 4 per turn x 6 turns, plus 1 for the POM inference call).
Run manually, or via the "Personal Operating Model walkthrough" GitHub
Actions workflow (workflow_dispatch).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api import db
from src.instrumentation.usage import UsageTracker
from src.orchestrator.engine import run_turn
from src.pom.engine import compute_personal_operating_model
from src.state.world_state import WorldState

SESSION_A_MESSAGES = [
    "I've always been the kind of person who needs to make my own decisions at work -- I don't like being micromanaged.",
    "I got an offer to lead a new team, but I'm weighing it against staying in my current role where I already know I can deliver.",
    "I think I'm good at the technical side, but leading people is something I haven't proven to myself yet.",
]

SESSION_B_MESSAGES = [
    "My manager Sarah has been putting a lot of pressure on me to decide by Friday, and it's stressing me out.",
    "Sarah's usually supportive, but this deadline feels like it's testing our relationship.",
    "Honestly the last few months have been hard, but I feel like I'm finally getting my footing back.",
]


def _run_session(label: str, messages: list[str], tracker: UsageTracker) -> str:
    print(f"\n{'=' * 70}\nSESSION {label}\n{'=' * 70}")
    session_id = db.create_session()
    state = WorldState()
    result = None
    for i, message in enumerate(messages, start=1):
        print(f"\n--- turn {i}: {message}")
        result = run_turn(message, state, tracker=tracker, session_id=session_id)
        state = result.state
        if result.failed_stage:
            print(f"[FAIL] turn {i} ({result.failed_stage}): {result.error}")
        db.append_message(session_id, "user", message)
    db.save_turn_result(session_id, result)
    print(f"\nFinal WorldState for {label}: {len(state.facts)} fact(s), {len(state.claims)} claim(s), "
          f"{len(state.goals)} goal(s), {len(state.decisions)} decision(s), {len(state.entities)} entit(y/ies), "
          f"{len(state.emotional_signal_items)} emotional signal(s)")
    return session_id


def main() -> None:
    db.init_db()
    tracker = UsageTracker()

    _run_session("A (identity/motivation/decision)", SESSION_A_MESSAGES, tracker)
    _run_session("B (relationship/stress/narrative)", SESSION_B_MESSAGES, tracker)

    claims, assumptions, entities, aggregated_content = db.get_aggregated_knowledge_for_pom()
    print(f"\n{'=' * 70}\nAggregated: {len(claims)} claim(s), {len(assumptions)} assumption(s), "
          f"{len(entities)} entit(y/ies) across both sessions.\n{'=' * 70}")
    print(aggregated_content)

    pom = compute_personal_operating_model(claims, assumptions, entities, aggregated_content, tracker=tracker)
    db.replace_personal_operating_model(pom)

    print(f"\n{'=' * 70}\nPERSONAL OPERATING MODEL\n{'=' * 70}")
    print(f"\nBelief ({len(pom.belief.beliefs)}):")
    for b in pom.belief.beliefs:
        print(f"  - {b}")
    print(f"\nRelationship ({len(pom.relationship.relationships)}):")
    for r in pom.relationship.relationships:
        print(f"  - {r}")
    print(f"\nIdentity: {pom.identity.self_concept or '(unclear)'}")
    print(f"  evidence: {pom.identity.evidence}")
    print(
        "\nMotivation (Self-Determination Theory): "
        f"autonomy={pom.motivation.autonomy}, competence={pom.motivation.competence}, "
        f"relatedness={pom.motivation.relatedness}"
    )
    print(f"  autonomy evidence: {pom.motivation.autonomy_evidence}")
    print(f"  competence evidence: {pom.motivation.competence_evidence}")
    print(f"  relatedness evidence: {pom.motivation.relatedness_evidence}")
    print(f"\nLearning style: {pom.learning_style.style or '(unclear)'}")
    print(f"  evidence: {pom.learning_style.evidence}")
    print(f"\nStress: {pom.stress.level}")
    print(f"  evidence: {pom.stress.evidence}")
    print(f"\nNarrative arc: {pom.narrative.arc} -- {pom.narrative.summary or '(no summary)'}")
    print(f"  evidence: {pom.narrative.evidence}")
    print(f"\nTheory of mind ({len(pom.theory_of_mind.entries)}):")
    for entry in pom.theory_of_mind.entries:
        print(f"  - {entry.entity_name}: {entry.inferred_perspective}")
        print(f"    evidence: {entry.evidence}")


if __name__ == "__main__":
    main()
