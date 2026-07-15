"""
Calibration harness for Tier 2 synthesis (see engine/decisions.md
"Tier 2 design" and "Tier 2 implementation").

Purpose: the Tier 2 implementation round shipped a fully, deterministically
tested MECHANISM -- candidate selection, cache invalidation, staleness
backstop, grounding enforcement, non-blocking failure -- but zero live
data on whether the actual synthesis prompt produces genuinely useful
statements on a real model, or over-synthesizes tenuous connections that
aren't really there. Same "the mechanism can be right and the model
compliance still unknown" gap every other LLM-facing addition in this
codebase has needed a calibration round for (has_knowledge_correction
being the most recent, see its own calibration script/entries above).

Unlike scripts/run_worldstate_walkthrough.py's single long transcript,
this runs several independent SHORT (1-2 turn) scenarios, each starting
from a fresh WorldState() -- cheaper per scenario, and isolates which
specific situation does or doesn't trigger real synthesis, which one
long conversation can't cleanly attribute. Scenarios are deliberately
shaped to reach Tier 2's candidate-pool floor (MIN_GROUNDING_ITEMS = 2)
within 1-2 turns: thread kinds (Goal/Decision/Unknown) qualify
regardless of recency, so two Decision options from a single "deciding
between X or Y" turn already clears the floor cheaply.

After each scenario, also calls update_tier2 a SECOND time on the final
state with no new turn, to confirm the caching/staleness gate actually
skips a redundant recompute against real data, not just the synthetic
unit tests in tests/test_tier2.py.

Not part of the automated test suite: this makes real, billable API
calls per scenario turn (up to 5/turn now: Interpretation, Judgment,
Planner, Response, and Tier 2 when a recompute is due). Run manually, or
via the "Tier 2 calibration" GitHub Actions workflow (workflow_dispatch).
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.state_inspector import render
from src.instrumentation.usage import UsageTracker, is_tracking_enabled
from src.orchestrator.engine import run_turn
from src.state.world_state import WorldState
from src.understanding.tier2_engine import update_tier2


@dataclass
class Scenario:
    name: str
    turns: List[str]
    expected_tier2_nonempty: Optional[bool]  # None = observation-only, not scored
    note: str


SCENARIOS = [
    Scenario(
        name="synthesis_decision_and_assumption",
        turns=[
            "I'm trying to decide between buying a house or going for an MBA.",
            "Honestly I don't think I can afford to do both at once.",
        ],
        expected_tier2_nonempty=True,
        note="Two Decision options (thread candidates, no recency window "
             "needed) plus a stated affordability constraint -- a clean "
             "synthesis opportunity: the decision may be less about "
             "preference than a shared resource constraint.",
    ),
    Scenario(
        name="synthesis_goal_and_blocking_fact",
        turns=[
            "My goal is to move into the Product team.",
            "But my manager just got promoted and I'm not sure who I'd even report to now.",
        ],
        expected_tier2_nonempty=True,
        note="An open Goal (thread) plus a new, unrelated-sounding "
             "organizational fact that plausibly complicates it -- tests "
             "whether synthesis connects a goal to a fact that isn't "
             "explicitly about the goal.",
    ),
    Scenario(
        name="negative_control_unrelated",
        turns=[
            "I've been trying to save up for a house.",
            "Also I've started going to pottery classes on Tuesdays, it's fun.",
        ],
        expected_tier2_nonempty=False,
        note="Two genuinely unrelated candidates (the negative control) -- "
             "tests over-synthesis risk: does the model invent a tenuous "
             "connection where none exists, the mirror-image failure mode "
             "of has_knowledge_correction's under-firing.",
    ),
    Scenario(
        name="same_decision_two_options",
        turns=[
            "I'm deciding whether to ask my manager for a raise or not.",
        ],
        expected_tier2_nonempty=None,
        note="Originally designed as a below-the-floor check (expecting "
             "one Decision-shaped candidate); the first live run (see "
             "engine/decisions.md 'Tier 2 first live calibration run') "
             "confirmed Interpretation reliably extracts BOTH sides of an "
             "'X or not X' framing as two separate Decision options, "
             "clearing MIN_GROUNDING_ITEMS every time -- the floor itself "
             "is already fully covered deterministically in "
             "tests/test_tier2.py, so this doesn't need to re-test it "
             "live. Repurposed as an observation: two candidates that ARE "
             "genuinely the same underlying choice (not unrelated, not a "
             "real cross-topic connection either) -- does the model "
             "produce a real restatement-as-synthesis here, a different "
             "compliance question than the unrelated-candidates control "
             "above.",
    ),
]


def run_scenario(scenario: Scenario, tracker: UsageTracker) -> tuple[bool, bool]:
    """Runs one scenario's turns through the real pipeline; returns
    (tier2 non-empty after the last turn, whether any stage actually
    failed)."""
    print(f"\n{'=' * 70}\nSCENARIO: {scenario.name}\n{scenario.note}\n{'=' * 70}")
    state = WorldState()
    pipeline_failed = False

    for i, message in enumerate(scenario.turns, start=1):
        print(f"\n--- turn {i}: {message}")
        computed_before = state.understanding.tier2_computed_at_turn
        result = run_turn(message, state, tracker=tracker)
        state = result.state

        if not result.judgment:
            print(f"[FAIL] turn {i}: {result.failed_stage} -- {result.error}")
            pipeline_failed = True
            continue

        recomputed = state.understanding.tier2_computed_at_turn != computed_before
        print(f"    tier2_recomputed_this_turn={recomputed}")
        print(f"    tier2_grounding_signature={state.understanding.tier2_grounding_signature!r}")
        print(f"    tier2 statements ({len(state.understanding.tier2)}):")
        for stmt in state.understanding.tier2:
            print(f"      - {stmt.text!r} grounded_in={stmt.grounding_item_ids}")

    print("\n--- caching check: calling update_tier2 again, no new turn ---")
    signature_before = state.understanding.tier2_grounding_signature
    computed_before = state.understanding.tier2_computed_at_turn
    state_again = update_tier2(state, tracker=tracker)
    same_signature = state_again.understanding.tier2_grounding_signature == signature_before
    same_computed_turn = state_again.understanding.tier2_computed_at_turn == computed_before
    print(f"    signature unchanged={same_signature}, computed_at_turn unchanged={same_computed_turn}")
    if not (same_signature and same_computed_turn):
        print("    [NOTE] recompute happened on the repeat call -- expected if "
              "tier2_computed_at_turn was still None (Tier 2 never successfully "
              "ran during the scenario's own turns, e.g. every turn failed "
              "upstream) or the staleness backstop is already due at this turn "
              "count; otherwise investigate as an unexpected cache miss.")

    print("\n--- final WORLDSTATE ---")
    render(state)

    return bool(state.understanding.tier2), pipeline_failed


def main() -> int:
    tracker = UsageTracker()  # inert unless CONFIDANT_TRACK_USAGE is set
    scored_total = 0
    scored_correct = 0
    results = []
    any_pipeline_failure = False

    for scenario in SCENARIOS:
        tier2_nonempty, pipeline_failed = run_scenario(scenario, tracker)
        any_pipeline_failure = any_pipeline_failure or pipeline_failed
        results.append((scenario, tier2_nonempty))
        if scenario.expected_tier2_nonempty is not None:
            scored_total += 1
            if tier2_nonempty == scenario.expected_tier2_nonempty:
                scored_correct += 1

    print(f"\n{'=' * 70}\nCALIBRATION SUMMARY\n{'=' * 70}")
    for scenario, tier2_nonempty in results:
        if scenario.expected_tier2_nonempty is None:
            print(f"  [observation] {scenario.name}: tier2_nonempty={tier2_nonempty}")
        else:
            hit = tier2_nonempty == scenario.expected_tier2_nonempty
            marker = "HIT " if hit else "MISS"
            print(
                f"  [{marker}] {scenario.name}: expected_nonempty="
                f"{scenario.expected_tier2_nonempty}, actual={tier2_nonempty}"
            )

    print(f"\nScored compliance: {scored_correct}/{scored_total}")
    print(
        "Note: a MISS here is expected calibration data about real model "
        "behavior, not a bug -- this script's exit code reflects whether "
        "the PIPELINE ran successfully, not whether the model complied "
        "with every expectation. A MISS on a synthesis_* scenario means "
        "the model under-synthesized (stayed too quiet); a MISS on "
        "negative_control_unrelated means it over-synthesized (invented a "
        "connection) -- these are different, differently-actionable "
        "findings, not the same failure."
    )

    if is_tracking_enabled():
        summary = tracker.summary()
        print(f"\nTotal calls: {summary['calls']}, total tokens: {summary['total_tokens']:,}")
        cost = summary["estimated_cost_usd"]
        print(f"Estimated cost: ${cost:.4f}" if cost is not None else "Estimated cost: unknown")

    return 1 if any_pipeline_failure else 0


if __name__ == "__main__":
    sys.exit(main())
