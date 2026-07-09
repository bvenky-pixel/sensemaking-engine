"""
Judgment v2 evaluation SMOKE TEST -- the scaled-down first run of
engine/specs/judgment-v2-evaluation-design.md, not the full pilot.

Scope, per explicit user decision (see engine/decisions.md):
- "Smoke test first": one conversation (the existing 10-turn Sarah/
  Product-team scenario from scripts/run_worldstate_walkthrough.py,
  reused so there's already a qualitative read on Confidant's behavior
  against it), one run per condition -- not the design doc's 20-30
  conversation pilot.
- "Quantitative only for now": only src/evaluation/metrics.py's
  automatically-derivable signals (token/cost/latency, structural counts,
  a word-overlap groundedness heuristic, a keyword constraint-violation
  heuristic) -- no blind human ranking, no LLM-judge, no pre-registered
  ground truth. This validates the HARNESS (does it run all three
  conditions end to end, produce comparable output, stay inside the
  free-tier call budget) more than it validates the ARCHITECTURE -- a
  real conclusion needs the full pilot with human/LLM-judge scoring.

Conditions run (design doc Sec. 2's "core three"):
- Baseline A: single call over the raw transcript.
- Baseline B2: incremental summary, then a call over the final summary.
- Confidant: the real pipeline, one call over the final WorldState.

Budget: ~23 LLM calls total (10 Interpretation + 1 Judgment for
Confidant, 1 for Baseline A, 10 summary-updates + 1 Judgment for
Baseline B2) -- sized to stay well inside the free-tier's daily request
cap. Each condition uses its OWN UsageTracker so cost/latency are never
mixed across conditions.

Not part of the automated test suite: this makes real, billable API
calls. Run manually, or via the "Judgment evaluation smoke test" GitHub
Actions workflow (workflow_dispatch).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.run_worldstate_walkthrough import TRANSCRIPT

from src.evaluation.baselines import run_baseline_a, run_baseline_b2
from src.evaluation.confidant_runner import run_confidant
from src.evaluation.metrics import compute_all
from src.instrumentation.usage import UsageTracker, is_tracking_enabled
from src.interpretation.engine import InterpretationError
from src.judgment.engine import JudgmentError

CONDITIONS = {
    "Baseline A (raw transcript)": run_baseline_a,
    "Baseline B2 (incremental summary)": run_baseline_b2,
    "Confidant (Interpretation -> WorldState -> Judgment)": run_confidant,
}


def _print_usage(tracker: UsageTracker) -> None:
    if not is_tracking_enabled():
        return
    summary = tracker.summary()
    cost = summary["estimated_cost_usd"]
    cost_str = f"${cost:.4f}" if cost is not None else "unknown"
    if not summary["cost_fully_known"]:
        cost_str += " (partial)"
    print(
        f"  calls={summary['calls']} tokens={summary['total_tokens']:,} "
        f"latency={summary['latency_ms'] / 1000:.1f}s cost={cost_str}"
    )
    for component, stats in summary["by_component"].items():
        comp_cost = stats["estimated_cost_usd"]
        comp_cost_str = f"${comp_cost:.4f}" if comp_cost is not None else "unknown"
        print(f"    - {component}: {stats['calls']} calls, {stats['total_tokens']:,} tokens, {comp_cost_str}")


def main() -> int:
    results = {}
    failures = 0

    for name, runner in CONDITIONS.items():
        print(f"\n{'=' * 70}\n{name}\n{'=' * 70}")
        tracker = UsageTracker()
        try:
            judgment, source_text = runner(TRANSCRIPT, tracker=tracker)
        except (JudgmentError, InterpretationError) as exc:
            failures += 1
            print(f"[FAIL] {exc}")
            continue

        results[name] = (judgment, source_text)

        print("\n--- JUDGMENT ---")
        print(judgment.model_dump())

        print("\n--- USAGE ---")
        _print_usage(tracker)

        print("\n--- METRICS (heuristic/quantitative only -- see src/evaluation/metrics.py) ---")
        metrics = compute_all(judgment, source_text)
        print(metrics)

    print(f"\n{'=' * 70}\nDone: {len(results)}/{len(CONDITIONS)} conditions succeeded.")
    print("Read the JUDGMENT blocks above side by side: do primary_problem/primary_goal/")
    print("risks/opportunities differ meaningfully across conditions? The metrics blocks")
    print("are heuristic signals only, not a substitute for the full pilot's human/")
    print("LLM-judge scoring (see engine/specs/judgment-v2-evaluation-design.md).")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
