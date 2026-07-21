"""
Calibration harness for Insight Engine (see engine/decisions.md
"Insight Engine" and engine/specs/insight-engine-specification-v1.md).

Purpose: `run_insight_detection` shipped as a fully, deterministically
tested MECHANISM (grounding enforcement, MIN_EVIDENCE_SESSIONS floor,
MAX_SESSIONS_FOR_INSIGHT cap) with zero live data on whether the actual
cross-session theme-detection prompt correctly recognizes that two
differently-worded sessions describe the same underlying pattern, or
over-clusters genuinely unrelated sessions into an invented theme. Same
"the mechanism can be right and the model compliance still unknown" gap
every other LLM-facing addition in this codebase has needed a
calibration round for (see scripts/run_tier2_calibration.py,
scripts/run_knowledge_correction_calibration.py).

Unlike those two, Insight Engine's unit is `run_insight_detection`
directly on a list of (session_id, surface_complaint, primary_problem)
tuples -- exactly the shape `get_session_texts_for_insights` already
produces from real persisted sessions in production, but constructible
here from short, hand-written scenarios instead of needing real
accumulated multi-session account history to exist first. This is
deliberately NOT blocked on real production data the way Learning's
MIN_EVIDENCE calibration (backlog #213) is: Insight Engine's quality
question is "does the model correctly cluster BY MEANING", which a
scripted pair of differently-worded session summaries can test directly
without waiting for real users to accumulate multi-session history.

Five scenarios, each a self-contained list of session tuples (no
WorldState, no orchestrator turns -- this calls run_insight_detection
directly, one real billable LLM call per scenario with >= MIN_EVIDENCE_SESSIONS
sessions; the below-floor scenario makes zero calls, per the engine's
own short-circuit, already covered by tests/test_insight_engine.py):

1. `reworded_recurring_theme` -- two sessions describing the same
   underlying pattern in different words (waiting on someone else's
   decision). Expected: a real Insight recognizing them as the same
   theme, with both session ids in evidence.
2. `three_sessions_shared_theme` -- three sessions, all reflecting a
   pattern of deferring to others rather than deciding for themselves.
   Expected: an Insight covering at least 2 of the 3 (MIN_EVIDENCE_SESSIONS),
   a slightly richer positive case than scenario 1.
3. `negative_control_unrelated` -- two genuinely unrelated sessions
   (career transfer freeze vs. a house-vs-MBA affordability decision).
   Expected: no Insight, or an Insight so weak it fails engine-level
   grounding -- tests the over-clustering risk, the mirror-image
   failure mode of scenario 1's under-clustering risk.
4. `two_sessions_same_topic_different_take` -- two sessions about the
   same surface topic (a difficult manager) but describing genuinely
   different underlying situations (one about being blocked from a
   transfer, one about a performance review) -- tests whether the model
   over-generalizes "same topic mentioned" into "same recurring pattern"
   when the actual underlying dynamic differs. Not scored pass/fail
   (observation only): a correct call could reasonably go either way
   depending on how much surface-topic overlap should count.
5. `below_evidence_floor` -- a single session. Expected: empty list,
   zero LLM calls (the engine's own short-circuit) -- included here as a
   live sanity check that the floor still holds in the exact calling
   shape production uses, even though it's already covered by unit
   tests.

Not part of the automated test suite: this makes real, billable API
calls (up to 4: scenarios 1-4, scenario 5 makes none). Run manually, or
via the "Insight Engine calibration" GitHub Actions workflow
(workflow_dispatch).
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.insight.engine import InsightEngineError, run_insight_detection
from src.instrumentation.usage import UsageTracker, is_tracking_enabled


@dataclass
class Scenario:
    name: str
    sessions: List[Tuple[str, str, str]]  # (session_id, surface_complaint, primary_problem)
    expected_theme_detected: Optional[bool]  # None = observation-only, not scored
    note: str


SCENARIOS = [
    Scenario(
        name="reworded_recurring_theme",
        sessions=[
            (
                "s1",
                "Feeling stuck waiting for my manager to approve my transfer request.",
                "User's internal move to another team is blocked by their manager's "
                "approval, which has been delayed for months with no clear reason given.",
            ),
            (
                "s2",
                "My co-founder still hasn't decided whether we're pivoting the product.",
                "User's ability to move forward on the product roadmap is blocked "
                "because a key decision rests entirely with their co-founder, who "
                "keeps deferring it.",
            ),
        ],
        expected_theme_detected=True,
        note="Two differently-worded sessions describing the same underlying "
             "pattern (progress blocked on someone else's unmade decision) -- "
             "the core semantic-clustering case Insight Engine exists for.",
    ),
    Scenario(
        name="three_sessions_shared_theme",
        sessions=[
            (
                "s1",
                "I keep asking my partner what they want for dinner instead of picking.",
                "User consistently defers small decisions to their partner rather "
                "than deciding for themselves.",
            ),
            (
                "s2",
                "I let my team pick the project approach even though I had a clear preference.",
                "User deferred a work decision to their team despite having their "
                "own clear preference.",
            ),
            (
                "s3",
                "I asked my sister to choose my apartment for me.",
                "User deferred a significant personal decision (choosing where to "
                "live) to a family member instead of deciding themselves.",
            ),
        ],
        expected_theme_detected=True,
        note="Three sessions, all reflecting a pattern of deferring decisions to "
             "others rather than deciding independently -- a richer positive case "
             "than scenario 1, testing whether the model correctly clusters more "
             "than a minimal pair.",
    ),
    Scenario(
        name="negative_control_unrelated",
        sessions=[
            (
                "s1",
                "My move to the Product team is stuck because of a transfer freeze until Q3.",
                "User's internal team transfer is blocked by an organizational "
                "freeze on new transfers until Q3.",
            ),
            (
                "s2",
                "Trying to decide between buying a house or going for an MBA.",
                "User is weighing a major financial decision between a house "
                "purchase and graduate education, constrained by a shared budget.",
            ),
        ],
        expected_theme_detected=False,
        note="Two genuinely unrelated sessions (an organizational blocker vs. a "
             "personal financial trade-off) -- tests over-clustering risk: does "
             "the model invent a shared theme where none exists, the mirror-image "
             "failure mode of scenario 1's under-clustering risk.",
    ),
    Scenario(
        name="two_sessions_same_topic_different_take",
        sessions=[
            (
                "s1",
                "My manager won't let me transfer to another team.",
                "User's internal team transfer is blocked by their manager, who "
                "has not given a clear reason for the delay.",
            ),
            (
                "s2",
                "My manager gave me a harsh performance review out of nowhere.",
                "User received an unexpectedly negative performance review from "
                "their manager, with no prior warning signs.",
            ),
        ],
        expected_theme_detected=None,
        note="Same surface topic (a difficult manager) but describing genuinely "
             "different underlying situations (a blocked transfer vs. an "
             "unexpected review) -- observation-only: a defensible model could "
             "reasonably call this either way depending on how much weight "
             "'same person, same relationship' should carry versus the "
             "dynamics actually being distinct.",
    ),
    Scenario(
        name="below_evidence_floor",
        sessions=[
            (
                "s1",
                "Just journaling about how my week went.",
                "User reflected generally on their week with no single blocking "
                "issue identified.",
            ),
        ],
        expected_theme_detected=False,
        note="A single session -- below MIN_EVIDENCE_SESSIONS. Expected: empty "
             "list, ZERO LLM calls (the engine's own short-circuit) -- a live "
             "sanity check that the floor holds in production's exact calling "
             "shape, even though tests/test_insight_engine.py already covers "
             "this at the unit level.",
    ),
]


def run_scenario(scenario: Scenario, tracker: UsageTracker) -> Tuple[bool, bool]:
    """Returns (theme_detected, pipeline_failed)."""
    print(f"\n{'=' * 70}\nSCENARIO: {scenario.name}\n{scenario.note}\n{'=' * 70}")
    for sid, complaint, problem in scenario.sessions:
        print(f"  [{sid}] surface_complaint={complaint!r}")
        print(f"        primary_problem={problem!r}")

    try:
        insights = run_insight_detection(scenario.sessions, tracker=tracker)
    except InsightEngineError as exc:
        print(f"[FAIL] {exc}")
        return False, True

    print(f"\n  detected {len(insights)} insight(s):")
    for insight in insights:
        print(f"    - theme={insight.theme!r}")
        print(f"      detail={insight.detail!r}")
        print(f"      evidence_session_ids={insight.evidence_session_ids}")

    return bool(insights), False


def main() -> int:
    tracker = UsageTracker()  # inert unless CONFIDANT_TRACK_USAGE is set
    scored_total = 0
    scored_correct = 0
    results = []
    any_pipeline_failure = False

    for scenario in SCENARIOS:
        detected, pipeline_failed = run_scenario(scenario, tracker)
        any_pipeline_failure = any_pipeline_failure or pipeline_failed
        results.append((scenario, detected))
        if scenario.expected_theme_detected is not None:
            scored_total += 1
            if detected == scenario.expected_theme_detected:
                scored_correct += 1

    print(f"\n{'=' * 70}\nCALIBRATION SUMMARY\n{'=' * 70}")
    for scenario, detected in results:
        if scenario.expected_theme_detected is None:
            print(f"  [observation] {scenario.name}: theme_detected={detected}")
        else:
            hit = detected == scenario.expected_theme_detected
            marker = "HIT " if hit else "MISS"
            print(
                f"  [{marker}] {scenario.name}: expected_detected="
                f"{scenario.expected_theme_detected}, actual={detected}"
            )

    print(f"\nScored compliance: {scored_correct}/{scored_total}")
    print(
        "Note: a MISS here is expected calibration data about real model "
        "behavior, not a bug -- this script's exit code reflects whether the "
        "PIPELINE ran successfully, not whether the model complied with every "
        "expectation. A MISS on a *_recurring_theme/*_shared_theme scenario "
        "means the model under-clustered (missed a real pattern); a MISS on "
        "negative_control_unrelated means it over-clustered (invented a "
        "connection) -- different, differently-actionable findings."
    )

    if is_tracking_enabled():
        summary = tracker.summary()
        print(f"\nTotal calls: {summary['calls']}, total tokens: {summary['total_tokens']:,}")
        cost = summary["estimated_cost_usd"]
        print(f"Estimated cost: ${cost:.4f}" if cost is not None else "Estimated cost: unknown")

    return 1 if any_pipeline_failure else 0


if __name__ == "__main__":
    sys.exit(main())
