"""
n=N live benchmark harness for the Interpretation Engine (see
engine/decisions.md v1.0 exit criteria).

Runs each fixed benchmark conversation (tests/fixtures/benchmark_conversations.py)
N times against whatever OPENROUTER_MODEL is configured in the
environment (OpenRouter is the only registered provider -- see
src/llm/providers.py), dumping every resulting Interpretation to
test-runs/ (gitignored) as JSON, plus a failure log if any run errors out.

This script only produces the raw data. Scoring it against the six v1.0
exit criteria (stability, zero role violations, no fabrication, etc.) is
a human judgment pass over the dumped JSON -- see engine/decisions.md for
what to look for, and log the result there once scored, the same way
every prior v1.0 iteration was recorded.

Not part of the automated test suite: this makes N * len(BENCHMARKS)
real, billable API calls. Run manually, or via the "Interpretation
benchmark" GitHub Actions workflow (workflow_dispatch).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.interpretation.engine import InterpretationError, run_interpretation
from tests.fixtures.benchmark_conversations import BENCHMARKS


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=10, help="Runs per benchmark case (default: 10)")
    parser.add_argument(
        "--out-dir",
        default="test-runs",
        help="Directory to dump per-run JSON output (default: test-runs/)",
    )
    args = parser.parse_args()

    provider = os.environ.get("LLM_PROVIDER", "openrouter")
    model = os.environ.get("OPENROUTER_MODEL")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    batch_dir = os.path.join(args.out_dir, f"{stamp}-{provider}-{model or 'default'}")
    os.makedirs(batch_dir, exist_ok=True)

    print(f"Provider: {provider} | model: {model or '(provider default)'}")
    print(f"Output directory: {batch_dir}")

    total = 0
    failures = 0

    for case_name, text in BENCHMARKS.items():
        for i in range(1, args.runs + 1):
            total += 1
            label = f"{case_name} run {i}/{args.runs}"
            try:
                interp = run_interpretation(text)
            except InterpretationError as exc:
                failures += 1
                print(f"[FAIL] {label}: {exc}")
                fail_path = os.path.join(batch_dir, f"{case_name}-{i:02d}-FAILED.txt")
                with open(fail_path, "w") as f:
                    f.write(str(exc))
                    if exc.raw_output:
                        f.write("\n\n--- raw output ---\n")
                        f.write(exc.raw_output)
                continue

            out_path = os.path.join(batch_dir, f"{case_name}-{i:02d}.json")
            with open(out_path, "w") as f:
                json.dump(interp.model_dump(), f, indent=2)
            print(f"[OK]   {label} -> {out_path}")

    print(f"\nDone: {total - failures}/{total} succeeded, {failures} failed.")
    print(f"Review the dumped JSON in {batch_dir} against the six v1.0 exit criteria in engine/decisions.md.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
