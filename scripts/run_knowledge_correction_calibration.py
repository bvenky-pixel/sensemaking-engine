"""
Calibration harness for Judgment.has_knowledge_correction (see
engine/decisions.md "Fact/Claim correction and near-duplicate
consolidation" and "Tier 1 completeness + has_knowledge_correction
calibration").

Purpose: the first live run of this field (the correction round) produced
exactly one data point -- one real hit (an unscripted near-duplicate
consolidation), one real miss (an engineered contradiction the model
didn't flag) -- on openai/gpt-4o, a manual override, NOT the model
actually pinned in production (fly.toml: OPENROUTER_MODEL =
'openai/gpt-4o-mini'). Every other boolean-gate field in this codebase
(has_assumption, has_risk_signal, has_decision_resolution) needed several
live-run rounds across varied scenarios before its compliance rate was
trustworthy -- this script is that campaign for has_knowledge_correction,
run against whichever model the caller points it at (see the workflow's
openrouter_model input).

Unlike scripts/run_worldstate_walkthrough.py's single long transcript,
this runs several independent SHORT (2-3 turn) scenarios, each starting
from a fresh WorldState() -- cheaper per scenario, and isolates which
specific situation does or doesn't trigger the field, which one long
conversation can't cleanly attribute.

Not part of the automated test suite: this makes real, billable API
calls per scenario turn. Run manually, or via the "Knowledge correction
calibration" GitHub Actions workflow (workflow_dispatch).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import List, Optional

from engine.state_inspector import render
from src.instrumentation.usage import UsageTracker, is_tracking_enabled, print_turn_summary
from src.orchestrator.engine import run_turn
from src.state.world_state import WorldState


@dataclass
class Scenario:
    name: str
    turns: List[str]
    expected_has_knowledge_correction: Optional[bool]  # None = observation-only, not scored
    note: str


SCENARIOS = [
    Scenario(
        name="contradiction_explicit",
        turns=[
            "My manager Sarah told me I'm not getting a raise this year.",
            "Actually, HR just told me I am getting the raise after all -- Sarah was wrong.",
        ],
        expected_has_knowledge_correction=True,
        note="A clean, explicit reversal of a directly-stated Fact -- the "
             "same class of case as the Boss denied/approved test fixture.",
    ),
    Scenario(
        name="near_duplicate_rewording",
        turns=[
            "I've been trying to save up money to buy a house.",
            "I'm working on saving money for a house purchase.",
            "It's slow going but I'm making progress.",
        ],
        expected_has_knowledge_correction=True,
        note="Mild wording drift restating the same underlying fact -- "
             "mirrors the turn that actually fired, unscripted, in the "
             "correction round's live walkthrough.",
    ),
    Scenario(
        name="negative_control_distinct_facts",
        turns=[
            "I can afford a house right now.",
            "I can also afford to go back for an MBA.",
        ],
        expected_has_knowledge_correction=False,
        note="Two genuinely distinct, lexically-similar facts (the "
             "negative control from the correction round's own test "
             "suite) -- must NOT be flagged as a correction.",
    ),
    Scenario(
        name="negative_control_fresh_conversation",
        turns=[
            "I'm not sure what I want to do with my career at this point.",
        ],
        expected_has_knowledge_correction=False,
        note="A single opening turn with no prior WorldState content -- "
             "nothing exists yet to correct.",
    ),
    Scenario(
        name="ambiguous_belief_over_time",
        turns=[
            "I think my partner is upset with me about something.",
            "Actually I talked to them and I think they're fine, not upset.",
        ],
        expected_has_knowledge_correction=None,
        note="A real belief revision where it's genuinely unclear whether "
             "the earlier statement was ever 'wrong' or just described an "
             "earlier point in time. The prompt's own guidance says this "
             "exact shape should leave the gate false and rely on "
             "contradictions instead -- reported as an observation, not "
             "scored as a hit or miss.",
    ),
]


def run_scenario(scenario: Scenario, tracker: UsageTracker) -> tuple[Optional[bool], bool]:
    """Runs one scenario's turns through the real pipeline; returns
    (LAST turn's has_knowledge_correction value, whether any stage
    actually failed). The LAST turn is used since it's the one with the
    fullest WorldState behind it, most likely to carry a correction
    signal."""
    print(f"\n{'=' * 70}\nSCENARIO: {scenario.name}\n{scenario.note}\n{'=' * 70}")
    state = WorldState()
    last_judgment_result = None
    pipeline_failed = False

    for i, message in enumerate(scenario.turns, start=1):
        print(f"\n--- turn {i}: {message}")
        result = run_turn(message, state, tracker=tracker)
        state = result.state

        if not result.judgment:
            print(f"[FAIL] turn {i}: {result.failed_stage} -- {result.error}")
            pipeline_failed = True
            continue

        last_judgment_result = result.judgment
        j = result.judgment
        print(f"    has_knowledge_correction={j.has_knowledge_correction}")
        if j.has_knowledge_correction:
            print(f"    target={j.knowledge_correction_target!r}")
            print(f"    kind={j.knowledge_correction_kind!r}")
            print(f"    corrected_content={j.knowledge_correction_corrected_content!r}")

    print("\n--- final WORLDSTATE ---")
    render(state)

    actual = last_judgment_result.has_knowledge_correction if last_judgment_result else None
    return actual, pipeline_failed


def main() -> int:
    tracker = UsageTracker()  # inert unless CONFIDANT_TRACK_USAGE is set
    scored_total = 0
    scored_correct = 0
    results = []
    any_pipeline_failure = False

    for scenario in SCENARIOS:
        actual, pipeline_failed = run_scenario(scenario, tracker)
        any_pipeline_failure = any_pipeline_failure or pipeline_failed
        results.append((scenario, actual))
        if scenario.expected_has_knowledge_correction is not None:
            scored_total += 1
            if actual == scenario.expected_has_knowledge_correction:
                scored_correct += 1

    print(f"\n{'=' * 70}\nCALIBRATION SUMMARY\n{'=' * 70}")
    for scenario, actual in results:
        if scenario.expected_has_knowledge_correction is None:
            print(f"  [observation] {scenario.name}: has_knowledge_correction={actual}")
        else:
            hit = actual == scenario.expected_has_knowledge_correction
            marker = "HIT " if hit else "MISS"
            print(
                f"  [{marker}] {scenario.name}: expected="
                f"{scenario.expected_has_knowledge_correction}, actual={actual}"
            )

    print(f"\nScored compliance: {scored_correct}/{scored_total}")
    print(
        "Note: a MISS here is expected calibration data about real model "
        "behavior, not a bug -- this script's exit code reflects whether "
        "the PIPELINE ran successfully, not whether the model complied "
        "with every expectation."
    )

    if is_tracking_enabled():
        summary = tracker.summary()
        print(f"\nTotal calls: {summary['calls']}, total tokens: {summary['total_tokens']:,}")
        cost = summary["estimated_cost_usd"]
        print(f"Estimated cost: ${cost:.4f}" if cost is not None else "Estimated cost: unknown")

    return 1 if any_pipeline_failure else 0


if __name__ == "__main__":
    sys.exit(main())
