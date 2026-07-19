"""
Production observability report (2026-07-19, backlog #230, see
engine/decisions.md "Production observability beyond opt-in
UsageTracker"). Offline, read-only -- reads whatever
src/api/server.py::send_message has persisted into
llm_usage_records/llm_attempt_records (only when CONFIDANT_TRACK_USAGE
is set, see fly.toml's own comment) and prints an aggregate summary:
per-component call counts, success rate (from attempt outcomes),
P50/P95 latency and total estimated cost (from usage records).

This is the "beyond" in the backlog title -- UsageTracker itself is a
fresh, in-memory, per-request instance; without this report there was
no way to see the pipeline's aggregate health/cost across every turn
without either enabling and re-deriving from raw per-session debug_json
blobs one at a time, or SSHing in and querying the DB by hand.

Run manually, or via a GitHub Actions workflow_dispatch (see
.github/workflows/usage-report.yml). Never called from
src/api/server.py or any other live request path.

Usage: python scripts/usage_report.py [--db-path PATH] [--since ISO_TIMESTAMP]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api import db


def _percentile(sorted_values: list, pct: float) -> float:
    """Nearest-rank percentile -- no interpolation, no external
    dependency (numpy) for what's otherwise a stdlib-only script."""
    if not sorted_values:
        return 0.0
    index = max(0, min(len(sorted_values) - 1, int(round(pct * (len(sorted_values) - 1)))))
    return sorted_values[index]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db-path", type=str, default=None,
        help="Override CONFIDANT_DB_PATH for this run (defaults to db.py's own resolution).",
    )
    parser.add_argument(
        "--since", type=str, default=None,
        help="Only include records at/after this ISO timestamp (default: all-time).",
    )
    args = parser.parse_args()

    db.init_db(Path(args.db_path) if args.db_path else None)

    usage_records = db.get_llm_usage_records(args.since)
    attempt_records = db.get_llm_attempt_records(args.since)

    if not usage_records and not attempt_records:
        print(
            "No usage/attempt records found"
            + (f" since {args.since}" if args.since else "")
            + " -- either CONFIDANT_TRACK_USAGE has never been enabled, or no live turns have run yet."
        )
        return

    components = sorted({r.component for r in usage_records} | {r.component for r in attempt_records})
    print(f"Usage report{' since ' + args.since if args.since else ' (all-time)'}")
    print(f"{len(usage_records)} usage record(s), {len(attempt_records)} attempt record(s) across {len(components)} component(s).\n")

    total_cost = 0.0
    for component in components:
        component_usage = [r for r in usage_records if r.component == component]
        component_attempts = [r for r in attempt_records if r.component == component]

        print(f"=== {component} ===")

        if component_attempts:
            successes = sum(1 for a in component_attempts if a.outcome == "success")
            print(f"Attempts: {len(component_attempts)}, success rate: {successes / len(component_attempts):.1%}")
            failures_by_outcome: dict = {}
            for a in component_attempts:
                if a.outcome != "success":
                    failures_by_outcome[a.outcome] = failures_by_outcome.get(a.outcome, 0) + 1
            for outcome, count in sorted(failures_by_outcome.items()):
                print(f"  {outcome}: {count}")
        else:
            print("Attempts: none recorded.")

        if component_usage:
            latencies = sorted(r.latency_ms for r in component_usage)
            costs = [r.estimated_cost_usd for r in component_usage if r.estimated_cost_usd is not None]
            component_cost = sum(costs)
            total_cost += component_cost
            print(f"Calls: {len(component_usage)}")
            print(f"Latency ms -- avg: {mean(latencies):.0f}, P50: {_percentile(latencies, 0.5):.0f}, P95: {_percentile(latencies, 0.95):.0f}")
            if costs:
                print(f"Estimated cost: ${component_cost:.4f} ({len(costs)}/{len(component_usage)} call(s) had a known model price)")
            else:
                print("Estimated cost: unknown (no call had a recognized model price)")
        else:
            print("Calls: none recorded.")
        print()

    print(f"Total estimated cost across all components: ${total_cost:.4f}")


if __name__ == "__main__":
    main()
