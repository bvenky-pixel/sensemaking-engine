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
from src.orchestrator.engine import run_turn
from src.state.world_state import WorldState
from src.understanding.tier2_engine import select_tier2_candidates

# Career-decision scenario, deliberately built to exercise: an accumulating
# goal, an unknown a later turn plausibly resolves, an entity who gets a
# later role update, and a final decision. Turn 11 (added 2026-07-12, see
# engine/decisions.md "Fact/Claim correction and near-duplicate
# consolidation") directly reverses turn 8's fact, to exercise
# Judgment.has_knowledge_correction against a real, live model on a real
# correction moment -- unlike every other boolean-gate field in this
# codebase (assumptions, decision_events, decision_resolutions), this one
# had no prior live-run track record when it shipped.
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
    "Actually, I just found out Sarah's promotion fell through -- she's not moving to Head of Product after all, she's staying on as my manager.",
]


def main() -> int:
    state = WorldState()
    failures = 0
    tracker = UsageTracker()  # inert unless CONFIDANT_TRACK_USAGE is set

    # Counseling modes (see engine/decisions.md): optional, env-set so a
    # dispatch of this script (or the GH Actions workflow wrapping it)
    # can exercise the same fixed transcript under a specific mode's
    # focus notes against a real model -- unset (the default) behaves
    # exactly as before this feature existed.
    mode = os.environ.get("WALKTHROUGH_MODE") or None
    if mode:
        print(f"Counseling mode: {mode}")

    for i, message in enumerate(TRANSCRIPT, start=1):
        print(f"\n{'=' * 70}\nTURN {i}: {message}\n{'=' * 70}")
        turn_start = tracker.count()
        outcome_start = tracker.outcome_count()
        tier2_computed_before = state.understanding.tier2_computed_at_turn

        # Orchestrator coordinates the fixed pipeline and reports exactly
        # how far this turn got -- see src/orchestrator/engine.py.
        # `result.state` always reflects what actually happened, so it's
        # safe to reassign unconditionally even on a mid-pipeline failure.
        result = run_turn(message, state, tracker=tracker, mode=mode)
        state = result.state

        if not result.interpretation:
            failures += 1
            print(f"[FAIL] turn {i} (interpretation): {result.error}")
            continue

        analyze_interpretation(result.interpretation)

        print("\n--- WORLDSTATE AFTER TURN", i, "---")
        render(state)

        # Understanding layer, Tier 1 (2026-07-12, see engine/decisions.md
        # "Understanding layer -- Journey-scoped identity") -- deterministic,
        # already computed by run_turn itself (src/orchestrator/engine.py),
        # printed here so a live multi-turn run visibly demonstrates
        # statement-id stability across turns, not just constructed test
        # fixtures.
        print("\n--- UNDERSTANDING (Tier 1) ---")
        if state.understanding.tier1:
            for stmt in state.understanding.tier1:
                print(f"    [{stmt.kind}] {stmt.text!r} (id={stmt.id})")
        else:
            print("    (none yet)")

        # Understanding layer, Tier 2 (2026-07-19, backlog #289) --
        # printed here, unlike Tier 1 above, because Tier 2 is
        # CONDITIONAL: most turns skip the LLM call entirely (see
        # src/understanding/tier2_engine.py::should_recompute_tier2), so
        # a live multi-turn run is the only way to see real candidate-pool
        # growth and real recompute cadence, not just Tier 1's per-turn
        # rendering. `candidate_pool_size` is computed here directly
        # (select_tier2_candidates), independent of whether a recompute
        # actually happened this turn, so the pool's own growth is
        # visible even on turns that skip the LLM call.
        candidates = select_tier2_candidates(state)
        tier2_recomputed = state.understanding.tier2_computed_at_turn != tier2_computed_before
        print("\n--- UNDERSTANDING (Tier 2) ---")
        print(f"    candidate_pool_size={len(candidates)}")
        print(f"    tier2_recomputed_this_turn={tier2_recomputed}")
        print(f"    tier2_computed_at_turn={state.understanding.tier2_computed_at_turn}")
        if state.understanding.tier2:
            for stmt in state.understanding.tier2:
                print(f"    [synthesis] {stmt.text!r} grounded_in={stmt.grounding_item_ids}")
        else:
            print("    (none yet)")

        if not result.judgment:
            failures += 1
            print(f"[FAIL] turn {i} (judgment): {result.error}")
            continue

        print("\n--- JUDGMENT ---")
        print(result.judgment.model_dump())

        if not result.planner:
            failures += 1
            print(f"[FAIL] turn {i} (planner): {result.error}")
            continue

        print("\n--- PLANNER ---")
        print(result.planner.model_dump())

        if not result.response:
            failures += 1
            print(f"[FAIL] turn {i} (response generator): {result.error}")
            continue

        print("\n--- RESPONSE (user-facing) ---")
        print(result.response.response_text)
        print(f"[confidence={result.response.confidence}]")
        if result.response.options:
            print("[options]")
            for option in result.response.options:
                print(f"  - {option.label}: {option.description}")
        else:
            print("[options] (none)")

        if is_tracking_enabled():
            print_turn_summary(tracker.since(turn_start), tracker.outcomes_since(outcome_start))

    print(f"\n{'=' * 70}\nDone: {len(TRANSCRIPT) - failures}/{len(TRANSCRIPT)} turns succeeded.")
    print("Read through the WORLDSTATE output above turn by turn: does it read as an")
    print("increasingly faithful, coherent model of the user's world by turn 10?")

    # WorldState provenance (2026-07-10, see engine/decisions.md
    # "WorldState provenance -- trajectory prerequisite") -- prints
    # first_seen/last_updated for every Goal/Decision so a live run
    # visibly demonstrates turn_count and the first_seen/last_updated
    # split on a real, multi-turn transcript, not just constructed test
    # fixtures.
    print(f"\n{'=' * 70}\nPROVENANCE CHECK (final turn_count={state.turn_count})")
    for label, items in (("Goals", state.goals), ("Decisions", state.decisions)):
        print(f"- {label}:")
        for item in items:
            p = item.provenance
            stamp = f"first_seen={p.first_seen}, last_updated={p.last_updated}" if p else "no provenance"
            print(f"    [{item.status}] {item.content!r} ({stamp})")

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

        reliability = summary["reliability"]
        rate = reliability["success_rate"]
        rate_str = f"{rate:.0%}" if rate is not None else "N/A"
        print(
            f"- Reliability: {reliability['successes']}/{reliability['attempts']} "
            f"attempts succeeded ({rate_str})"
        )
        if reliability["failures_by_type"]:
            for failure_type, count in reliability["failures_by_type"].items():
                print(f"  - {failure_type}: {count}")
        for component, stats in reliability["by_component"].items():
            comp_rate = stats["success_rate"]
            comp_rate_str = f"{comp_rate:.0%}" if comp_rate is not None else "N/A"
            print(
                f"  - {component}: {stats['successes']}/{stats['attempts']} succeeded "
                f"({comp_rate_str})"
            )

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
