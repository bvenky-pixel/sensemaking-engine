"""
End-to-end WorldState walkthrough: runs a fixed, realistic 8-10 turn
conversation through the REAL pipeline (run_interpretation -> update_state
-> run_judgment -> run_planner -> run_response_generator), rendering
WorldState, the Judgment assessment, the Planner plan, and the final
user-facing Response after every turn.

Purpose: unlike tests/test_world_state_evolution.py (hand-built
Interpretation objects, no LLM calls, isolates the State Builder), this
exercises the whole chain together against a live model, so a human can read
through the per-turn output and judge whether WorldState reads as an
increasingly faithful model of the user's world by the final turn -- a
qualitative call this script doesn't attempt to auto-grade. Now also
exercises Judgment v2 (src/judgment/engine.py), Planner v1
(src/planner/engine.py), and Response Generator v1 (src/response/engine.py),
each its own LLM call layered on the one before -- read Judgment's output
for whether the assessment tracks the actual WorldState content, Planner's
output for whether the chosen primary_objective/rationale actually follows
from that Judgment, and the Response for whether it faithfully executes
Planner's plan (same objective/strategy/constraints) without introducing
new facts, reasoning, or objectives of its own.

Not part of the automated test suite: this makes one real, billable API call
per turn. Run manually, or via the "WorldState walkthrough" GitHub Actions
workflow (workflow_dispatch).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.state_inspector import render
from src.instrumentation.usage import UsageTracker, is_tracking_enabled, print_turn_summary
from src.interpretation.debug import analyze_interpretation
from src.interpretation.engine import InterpretationError, run_interpretation
from src.judgment.engine import JudgmentError, recommend_phase_transition, run_judgment
from src.planner.engine import PlannerError, run_planner
from src.response.engine import ResponseGeneratorError, run_response_generator
from src.state.builder import update_state
from src.state.world_state import WorldState

# Career-decision scenario, deliberately built to exercise: an accumulating
# goal, an unknown a later turn plausibly resolves, an entity who gets a
# later role update, and a final decision.
TRANSCRIPT = [
    "I've been trying to move from my current team to the Product team for a few months now.",
    "My manager, Sarah, keeps saying it's not the right time, but she never gives a clear reason.",
    "I don't know if she's actually against it or just too busy to deal with the paperwork.",
    "Yesterday she told me the team is frozen for new transfers until Q3.",
    "That actually explains a lot -- I was starting to think she just didn't want me on the team.",
    "My main goal right now is to make sure I'm the first one considered once the freeze lifts.",
    "I'm also considering just applying externally if this drags on much longer.",
    "Sarah mentioned she's actually being promoted to Head of Product in Q3.",
    "If she's leading Product, I think my chances go up a lot once the freeze ends.",
    "I've decided to wait until Q3 and see what happens once she's in the new role.",
]


def main() -> int:
    state = WorldState()
    failures = 0
    tracker = UsageTracker()  # inert unless CONFIDANT_TRACK_USAGE is set

    for i, message in enumerate(TRANSCRIPT, start=1):
        print(f"\n{'=' * 70}\nTURN {i}: {message}\n{'=' * 70}")
        turn_start = tracker.count()

        try:
            interp = run_interpretation(message, tracker=tracker)
        except InterpretationError as exc:
            failures += 1
            print(f"[FAIL] turn {i} (interpretation): {exc}")
            continue

        analyze_interpretation(interp)

        # WorldState must be updated with this turn's Interpretation
        # BEFORE Judgment runs -- Judgment only ever sees WorldState.
        state = update_state(state, interp)

        next_phase = recommend_phase_transition(state)
        if next_phase:
            state.phase = next_phase

        print("\n--- WORLDSTATE AFTER TURN", i, "---")
        render(state)

        try:
            judgment = run_judgment(state, tracker=tracker)
        except JudgmentError as exc:
            failures += 1
            print(f"[FAIL] turn {i} (judgment): {exc}")
            continue

        print("\n--- JUDGMENT ---")
        print(judgment.model_dump())

        try:
            plan = run_planner(state, judgment, tracker=tracker)
        except PlannerError as exc:
            failures += 1
            print(f"[FAIL] turn {i} (planner): {exc}")
            continue

        print("\n--- PLANNER ---")
        print(plan.model_dump())

        try:
            response = run_response_generator(state, judgment, plan, tracker=tracker)
        except ResponseGeneratorError as exc:
            failures += 1
            print(f"[FAIL] turn {i} (response generator): {exc}")
            continue

        print("\n--- RESPONSE (user-facing) ---")
        print(response.response_text)
        print(f"[confidence={response.confidence}]")

        if is_tracking_enabled():
            print_turn_summary(tracker.since(turn_start))

    print(f"\n{'=' * 70}\nDone: {len(TRANSCRIPT) - failures}/{len(TRANSCRIPT)} turns succeeded.")
    print("Read through the WORLDSTATE output above turn by turn: does it read as an")
    print("increasingly faithful, coherent model of the user's world by turn 10?")

    if is_tracking_enabled():
        summary = tracker.summary()
        print(f"\n{'=' * 70}\nCONVERSATION USAGE SUMMARY (all {len(TRANSCRIPT)} turns)")
        print(f"- Calls: {summary['calls']}")
        print(f"- Prompt tokens: {summary['prompt_tokens']:,}")
        print(f"- Completion tokens: {summary['completion_tokens']:,}")
        reasoning = summary["reasoning_tokens"]
        print(f"- Reasoning tokens: {reasoning:,}" if reasoning is not None else "- Reasoning tokens: N/A")
        cached = summary["cached_tokens"]
        print(f"- Cached tokens: {cached:,}" if cached is not None else "- Cached tokens: N/A")
        print(f"- Total tokens: {summary['total_tokens']:,}")
        print(f"- Total latency: {summary['latency_ms'] / 1000:.1f} s")
        cost = summary["estimated_cost_usd"]
        cost_str = f"${cost:.4f}" if cost is not None else "unknown"
        if not summary["cost_fully_known"]:
            cost_str += " (partial -- some calls had no pricing entry)"
        print(f"- Total cost: {cost_str}")
        frontier = summary["frontier_cost_comparison_usd"]
        if frontier:
            frontier_str = ", ".join(f"{model_id}=${cost:.4f}" for model_id, cost in frontier.items())
            print(f"- Frontier cost comparison: {frontier_str}")
        for component, stats in summary["by_component"].items():
            comp_cost = stats["estimated_cost_usd"]
            comp_cost_str = f"${comp_cost:.4f}" if comp_cost is not None else "unknown"
            print(
                f"  - {component}: {stats['calls']} calls, {stats['total_tokens']:,} tokens, "
                f"{comp_cost_str}"
            )
        for provider, stats in summary["by_provider"].items():
            prov_cost = stats["estimated_cost_usd"]
            prov_cost_str = f"${prov_cost:.4f}" if prov_cost is not None else "unknown"
            print(
                f"  - [{provider}] {stats['calls']} calls, {stats['total_tokens']:,} tokens, "
                f"{prov_cost_str}"
            )

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
