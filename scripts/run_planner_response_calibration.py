"""
Dedicated calibration/evaluation round for Planner and Response, with
tracked case IDs (backlog #222, #223 -- see engine/decisions.md).

Neither stage has ever had a structured, case-ID-tracked evaluation the
way Judgment v2 did (engine/specs/judgment-v2-evaluation-design.md) --
every prior Planner/Response fix (v2 Priority 1, v3 compact structure,
depth-parity passes) was driven by direct user complaints or ad hoc log
greps against `experiments/confidant-validation/log.md`, never a
repeatable round with named cases. This script is that first round for
both stages at once: Planner and Response are adjacent, tightly coupled
stages of the same `run_turn` call (Response consumes Planner's own
output directly), so one live dispatch naturally produces trackable
evidence for both -- no reason to force two separate dispatches of the
same conversations.

Each case is scripted to stress-test a SPECIFIC, already-documented
principle from `engine/specs/planner-specification-v1.md` or
`engine/specs/response-generator-specification-v2.md`, not a vague
"is this good" vibe check:

- **PR01 (user_stated_response_style_constraint)** — tests the 2026-07-10
  rule (planner-specification-v1.md, `planning_constraints`): an
  explicit user instruction about HOW to be responded to ("don't ask me
  questions") must be translated into its own literal constraint.
  Scored: does `planning_constraints` contain a constraint referencing
  "question"?
- **PR02 (respect_already_made_decision)** — tests Planner's "User
  Agency is Absolute" principle (#2): if the user has clearly chosen a
  path, Planner supports it rather than re-litigating it, and
  `resolution_blocker` shouldn't still be framed as the already-resolved
  choice itself. Scored: `resolution_blocker` and `response_text` don't
  read as re-opening the decision (checked via absence of
  reconsideration-flavored phrasing) -- an imperfect proxy, printed in
  full for human read-through too.
- **PR03 (overwhelm_pacing)** — tests Response v2 Priority 1's pacing
  rule (at most one, or at most two closely related, questions per turn
  when the situation is emotionally loaded). Scored: `response_text`
  contains at most 2 question marks.
- **PR04 (emotional_acknowledgment_before_pivot)** — tests Response v2
  Priority 1's second fix: a brief acknowledgment before pivoting to
  fact-finding, when the latest turn carries real emotional content.
  Observation only (a "brief acknowledgment" isn't mechanically
  checkable) -- printed for human read-through.
- **PR05 (negative_control_mundane)** — a flat, logistics-only exchange
  with no emotional or agency-conflict content. Observation only: tests
  that Planner/Response don't manufacture urgency, stakes, or
  unsolicited acknowledgment where none is warranted -- the mirror-image
  over-fitting risk to PR01-PR04's under-firing risk.

Not part of the automated test suite: this makes real, billable API
calls through the full pipeline (Interpretation, Judgment, Planner,
Response per turn -- up to 3 turns per case). Run manually, or via the
"Planner/Response calibration" GitHub Actions workflow
(workflow_dispatch).
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.instrumentation.usage import UsageTracker, is_tracking_enabled
from src.orchestrator.engine import run_turn
from src.state.world_state import WorldState

_RECONSIDERATION_PHRASES = (
    "are you sure", "have you considered not", "before you commit",
    "reconsider", "is this really the right", "double check this decision",
)


@dataclass
class Case:
    case_id: str
    name: str
    turns: List[str]
    check: str
    score_fn: Optional[str]  # name of a scoring function below, or None for observation-only


CASES = [
    Case(
        case_id="PR01",
        name="user_stated_response_style_constraint",
        turns=[
            "I'm trying to decide whether to move to another city for a job offer.",
            "Honestly, please don't ask me a bunch of questions about it -- "
            "just help me think through what actually matters here.",
        ],
        check="planning_constraints must contain a literal constraint derived "
              "from the user's explicit 'don't ask me questions' instruction "
              "(the 2026-07-10 rule in planner-specification-v1.md).",
        score_fn="score_pr01",
    ),
    Case(
        case_id="PR02",
        name="respect_already_made_decision",
        turns=[
            "I've been going back and forth on whether to take a job with a pay cut "
            "but way better hours.",
            "I've decided -- I'm taking it, the pay cut is worth it for my time back. "
            "I just want to think through the logistics of resigning now.",
        ],
        check="Planner must not re-litigate the already-resolved choice (User "
              "Agency principle #2); resolution_blocker/response_text should be "
              "about logistics, not whether to take the job.",
        score_fn="score_pr02",
    ),
    Case(
        case_id="PR03",
        name="overwhelm_pacing",
        turns=[
            "This week has been a lot: my landlord is raising rent 20%, my car "
            "needs a repair I can't really afford right now, and my manager just "
            "told me my role might be eliminated next quarter.",
            "I don't even know where to start with any of this.",
        ],
        check="response_text should contain at most 2 question marks under "
              "Response v2 Priority 1's overwhelm-pacing rule.",
        score_fn="score_pr03",
    ),
    Case(
        case_id="PR04",
        name="emotional_acknowledgment_before_pivot",
        turns=[
            "My dad passed away last month and I'm still trying to sort out his "
            "estate on top of everything else.",
        ],
        check="Response should include a brief acknowledgment before pivoting to "
              "fact-finding (Response v2 Priority 1's second fix). Observation "
              "only -- read the printed response_text.",
        score_fn=None,
    ),
    Case(
        case_id="PR05",
        name="negative_control_mundane",
        turns=[
            "My dentist appointment got moved from Tuesday to Thursday.",
            "Also I need to renew my car registration sometime this month.",
        ],
        check="Negative control: Planner/Response should not manufacture urgency, "
              "stakes, or unsolicited emotional acknowledgment for a flat, "
              "logistics-only exchange. Observation only.",
        score_fn=None,
    ),
]


def score_pr01(planner, response) -> bool:
    return any("question" in c.lower() for c in planner.planning_constraints)


def score_pr02(planner, response) -> bool:
    text = (planner.resolution_blocker + " " + response.response_text).lower()
    return not any(phrase in text for phrase in _RECONSIDERATION_PHRASES)


def score_pr03(planner, response) -> bool:
    return response.response_text.count("?") <= 2


_SCORERS = {"score_pr01": score_pr01, "score_pr02": score_pr02, "score_pr03": score_pr03}


def run_case(case: Case, tracker: UsageTracker) -> Optional[bool]:
    print(f"\n{'=' * 70}\nCASE {case.case_id}: {case.name}\n{case.check}\n{'=' * 70}")
    state = WorldState()
    planner = None
    response = None

    for i, message in enumerate(case.turns, start=1):
        print(f"\n--- turn {i}: {message}")
        result = run_turn(message, state, tracker=tracker)
        state = result.state
        if not result.planner or not result.response:
            print(f"[FAIL] turn {i}: {result.failed_stage} -- {result.error}")
            return None
        planner, response = result.planner, result.response

    print("\n--- PLANNER ---")
    print(f"  primary_objective: {planner.primary_objective!r}")
    print(f"  rationale: {planner.rationale!r}")
    print(f"  conversational_strategy: {planner.conversational_strategy!r}")
    print(f"  resolution_blocker: {planner.resolution_blocker!r}")
    print(f"  planning_constraints: {planner.planning_constraints!r}")
    print(f"  questions_to_explore: {planner.questions_to_explore!r}")

    print("\n--- RESPONSE ---")
    print(f"  response_text: {response.response_text!r}")
    print(f"  options: {response.options!r}")

    if case.score_fn is None:
        return None
    return _SCORERS[case.score_fn](planner, response)


def main() -> int:
    tracker = UsageTracker()  # inert unless CONFIDANT_TRACK_USAGE is set
    scored_total = 0
    scored_correct = 0
    results = []
    any_pipeline_failure = False

    for case in CASES:
        result = run_case(case, tracker)
        if result is None and case.score_fn is not None:
            any_pipeline_failure = True
        results.append((case, result))
        if case.score_fn is not None and result is not None:
            scored_total += 1
            if result:
                scored_correct += 1

    print(f"\n{'=' * 70}\nCALIBRATION SUMMARY\n{'=' * 70}")
    for case, result in results:
        if case.score_fn is None:
            print(f"  [observation] {case.case_id} {case.name}: see full output above")
        elif result is None:
            print(f"  [ERROR] {case.case_id} {case.name}: pipeline failed")
        else:
            marker = "HIT " if result else "MISS"
            print(f"  [{marker}] {case.case_id} {case.name}")

    print(f"\nScored compliance: {scored_correct}/{scored_total}")
    print(
        "Note: a MISS here is expected calibration data about real model "
        "behavior, not a bug -- this script's exit code reflects whether the "
        "pipeline ran successfully, not whether the model complied with every "
        "expectation. Observation-only cases (PR04, PR05) have no mechanical "
        "score -- read their printed output directly against this file's own "
        "docstring criteria."
    )

    if is_tracking_enabled():
        summary = tracker.summary()
        print(f"\nTotal calls: {summary['calls']}, total tokens: {summary['total_tokens']:,}")
        cost = summary["estimated_cost_usd"]
        print(f"Estimated cost: ${cost:.4f}" if cost is not None else "Estimated cost: unknown")

    return 1 if any_pipeline_failure else 0


if __name__ == "__main__":
    sys.exit(main())
