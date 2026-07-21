"""
Calibration harness for the six LLM-inferred POM systems (see
engine/decisions.md "Personal Operating Model" and
engine/specs/personal-operating-model-specification-v1.md, backlog
#292).

Purpose: `run_inferred_pom` (Identity, Motivation, Learning Style,
Stress, Narrative, Theory of Mind) shipped as a fully, deterministically
tested MECHANISM (one call, one schema, engine-level grounding
enforcement via `_ground_batch` that downgrades any ungrounded field to
"unclear"/empty) with zero live data on whether the actual inference
prompt produces genuinely useful, well-grounded assessments on real
content, or defaults to "unclear" even when a real signal is present, or
over-confidently asserts a level with thin justification. Same
"mechanism can be right and model compliance still unknown" gap as
every other LLM-facing addition (see scripts/run_tier2_calibration.py,
scripts/run_insight_calibration.py).

Unlike the mechanical Belief/Relationship systems (pure Python, no
calibration needed), the six inferred systems need real content shaped
to surface a signal for each -- since production's own
`get_aggregated_knowledge_for_pom` output format is just plain text
lines ("Fact: ...", "Claim: ...", "Goal: ...", "Decision: ...",
"Assumption: ...", "Entity: ...", "Emotional signal: ..."), this script
constructs that same plain-text shape directly from short, hand-written
scenarios rather than needing a real account's accumulated multi-session
history to exist first -- not blocked on real production data the way
Learning's MIN_EVIDENCE calibration (backlog #213) is.

Six scenarios, each calling run_inferred_pom directly (one real
billable LLM call per scenario) on a purpose-built aggregated_content
string:

1. `narrative_redemptive_and_identity` -- content describing overcoming
   a setback and now mentoring others through the same thing. Expected:
   narrative.arc="redemptive", identity.self_concept non-empty and
   grounded.
2. `motivation_low_autonomy` -- content where every major decision is
   made by someone else (manager, partner, parent), user repeatedly
   defers. Expected: motivation.autonomy="low".
3. `stress_high_signals` -- content with several emotional-signal lines
   showing overwhelm/anxiety tied to compounding deadlines. Expected:
   stress.level="high".
4. `learning_style_reflective_processor` -- content showing the person
   processes decisions slowly, in writing, talking things through
   before acting rather than deciding quickly. Expected:
   learning_style.style non-empty and grounded (not scored against an
   exact wording -- style is free text).
5. `theory_of_mind_named_entity` -- content with one clearly-described
   entity (a specific named coworker) whose own likely perspective is
   inferable from stated actions. Expected: theory_of_mind.entries
   contains at least one entry referencing that entity, grounded.
6. `negative_control_thin_data` -- minimal, generic content with no
   real signal for any of the six systems (a single neutral fact,
   nothing emotionally or narratively rich). Expected (observation, not
   scored pass/fail): most/all fields stay "unclear"/empty rather than
   the model inventing confident-sounding answers from almost nothing --
   the over-fitting risk that's the mirror image of scenarios 1-5's
   under-firing risk.

Not part of the automated test suite: this makes 6 real, billable API
calls. Run manually, or via the "POM inferred-systems calibration"
GitHub Actions workflow (workflow_dispatch).
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.instrumentation.usage import UsageTracker, is_tracking_enabled
from src.llm.providers import ProviderCallError
from src.pom.engine import run_inferred_pom
from src.pom.schema import InferredPOMBatch


@dataclass
class Scenario:
    name: str
    aggregated_content: str
    check: str  # human-readable description of what a HIT looks like
    score: Optional[str]  # dotted-path field to check for non-"unclear"/non-empty, or None to skip scoring


SCENARIOS = [
    Scenario(
        name="narrative_redemptive_and_identity",
        aggregated_content=(
            "Fact: User was laid off from their first job out of college after "
            "the company folded.\n"
            "Fact: User spent eight months unemployed and described that period "
            "as the lowest point of their career.\n"
            "Fact: User eventually built a small consulting practice from that "
            "experience and now mentors two junior consultants who are going "
            "through their own layoffs.\n"
            "Claim: User says the layoff taught them more about resilience than "
            "any job would have.\n"
            "Emotional signal: pride (intensity=0.7, source=reflecting on mentoring others)"
        ),
        check="narrative.arc == 'redemptive' (setback -> meaning -> now helping "
              "others through the same thing); identity.self_concept non-empty "
              "and grounded in the layoff/mentoring facts.",
        score="narrative.arc",
    ),
    Scenario(
        name="motivation_low_autonomy",
        aggregated_content=(
            "Fact: User's manager decides which projects they work on every "
            "quarter without asking for input.\n"
            "Fact: User's partner picks where they go on every vacation.\n"
            "Fact: User's parents chose their college major.\n"
            "Claim: User says they've never really had to pick their own path -- "
            "someone else always ends up deciding for them.\n"
            "Assumption: User believes pushing back on any of these people would "
            "cause conflict, so they go along with it."
        ),
        check="motivation.autonomy == 'low' -- consistent pattern of major life "
              "decisions being made by other people, with a stated belief that "
              "asserting their own preference would be costly.",
        score="motivation.autonomy",
    ),
    Scenario(
        name="stress_high_signals",
        aggregated_content=(
            "Fact: User has three overlapping deadlines this month: a client "
            "deliverable, a performance review, and a family event they're "
            "organizing.\n"
            "Emotional signal: anxiety (intensity=0.85, source=overlapping deadlines)\n"
            "Emotional signal: overwhelm (intensity=0.8, source=performance review prep)\n"
            "Emotional signal: exhaustion (intensity=0.75, source=lack of sleep this week)\n"
            "Claim: User says they feel like they're barely keeping up and "
            "haven't had a full night's sleep in over a week."
        ),
        check="stress.level == 'high' -- multiple high-intensity emotional "
              "signals plus an explicit self-report of being overwhelmed and "
              "under-slept.",
        score="stress.level",
    ),
    Scenario(
        name="learning_style_reflective_processor",
        aggregated_content=(
            "Fact: User keeps a running journal and reviews it before every "
            "major decision.\n"
            "Fact: User asked to postpone a work decision by two days so they "
            "could talk it through with a friend first.\n"
            "Claim: User says they never trust a decision they made in the "
            "moment -- they need to sit with it and write it out first.\n"
            "Fact: User re-read their own notes from a similar decision three "
            "years ago before deciding this time."
        ),
        check="learning_style.style non-empty, grounded, and actually describes "
              "a reflective/writing-based processing style rather than a "
              "generic restatement.",
        score="learning_style.style",
    ),
    Scenario(
        name="theory_of_mind_named_entity",
        aggregated_content=(
            "Entity: Priya -- role is team lead; relationship is user's direct manager\n"
            "Fact: Priya has postponed User's transfer request three times "
            "without giving a reason.\n"
            "Fact: Priya told User privately that she's worried about being "
            "short-staffed if User leaves the team.\n"
            "Claim: User believes Priya isn't against the transfer personally, "
            "she's just under pressure from her own manager to keep headcount."
        ),
        check="theory_of_mind.entries contains an entry for Priya, with "
              "inferred_perspective capturing that her hesitation is about "
              "staffing pressure rather than personal opposition -- grounded in "
              "the facts given, not invented.",
        score="theory_of_mind.entries",
    ),
    Scenario(
        name="negative_control_thin_data",
        aggregated_content=(
            "Fact: User had a sandwich for lunch.\n"
            "Fact: User's meeting was rescheduled to 3pm."
        ),
        check="OBSERVATION ONLY, not scored pass/fail: most/all of the six "
              "fields should stay 'unclear'/empty given how little real signal "
              "is present -- a MISS here (confident-sounding output from "
              "almost nothing) is the over-fitting risk, the mirror image of "
              "scenarios 1-5's under-firing risk.",
        score=None,
    ),
]


def _field_is_populated(batch: InferredPOMBatch, dotted_path: str) -> bool:
    obj = batch
    for part in dotted_path.split("."):
        obj = getattr(obj, part)
    if isinstance(obj, list):
        return len(obj) > 0
    if isinstance(obj, str):
        return obj not in ("", "unclear")
    return obj != "unclear"


def run_scenario(scenario: Scenario, tracker: UsageTracker) -> Optional[bool]:
    """Returns True/False if scored, None if observation-only or failed."""
    print(f"\n{'=' * 70}\nSCENARIO: {scenario.name}\n{scenario.check}\n{'=' * 70}")
    print(f"--- aggregated_content ---\n{scenario.aggregated_content}\n")

    try:
        batch = run_inferred_pom(scenario.aggregated_content, tracker=tracker)
    except ProviderCallError as exc:
        print(f"[FAIL] {exc}")
        return None

    print("--- INFERRED POM BATCH ---")
    print(f"  identity: {batch.identity!r}")
    print(f"  motivation: {batch.motivation!r}")
    print(f"  learning_style: {batch.learning_style!r}")
    print(f"  stress: {batch.stress!r}")
    print(f"  narrative: {batch.narrative!r}")
    print(f"  theory_of_mind: {batch.theory_of_mind!r}")

    if scenario.score is None:
        return None
    return _field_is_populated(batch, scenario.score)


def main() -> int:
    tracker = UsageTracker()  # inert unless CONFIDANT_TRACK_USAGE is set
    scored_total = 0
    scored_correct = 0
    results = []
    any_failure = False

    for scenario in SCENARIOS:
        result = run_scenario(scenario, tracker)
        results.append((scenario, result))
        if result is None and scenario.score is not None:
            any_failure = True
        elif scenario.score is not None:
            scored_total += 1
            if result:
                scored_correct += 1

    print(f"\n{'=' * 70}\nCALIBRATION SUMMARY\n{'=' * 70}")
    for scenario, result in results:
        if scenario.score is None:
            print(f"  [observation] {scenario.name}: see full output above")
        elif result is None:
            print(f"  [ERROR] {scenario.name}: provider call failed")
        else:
            marker = "HIT " if result else "MISS"
            print(f"  [{marker}] {scenario.name}: expected {scenario.score} populated, actual={result}")

    print(f"\nScored compliance: {scored_correct}/{scored_total}")
    print(
        "Note: a MISS here is expected calibration data about real model "
        "behavior, not a bug -- this script's exit code reflects whether "
        "every provider call succeeded, not whether the model complied with "
        "every expectation. A MISS on scenarios 1-5 means the model stayed "
        "'unclear' despite a real signal being present (under-firing); a "
        "confident, non-'unclear' answer on the negative control would be "
        "over-firing -- read that scenario's full printed output above, since "
        "it isn't scored pass/fail."
    )

    if is_tracking_enabled():
        summary = tracker.summary()
        print(f"\nTotal calls: {summary['calls']}, total tokens: {summary['total_tokens']:,}")
        cost = summary["estimated_cost_usd"]
        print(f"Estimated cost: ${cost:.4f}" if cost is not None else "Estimated cost: unknown")

    return 1 if any_failure else 0


if __name__ == "__main__":
    sys.exit(main())
