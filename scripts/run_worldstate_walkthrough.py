"""
End-to-end WorldState walkthrough: runs a fixed, realistic 8-10 turn
conversation through the REAL pipeline (run_interpretation -> run_judgment
-> update_state), rendering WorldState after every turn.

Purpose: unlike tests/test_world_state_evolution.py (hand-built
Interpretation objects, no LLM calls, isolates the State Builder), this
exercises the whole chain together against a live model, so a human can read
through the per-turn output and judge whether WorldState reads as an
increasingly faithful model of the user's world by the final turn -- a
qualitative call this script doesn't attempt to auto-grade.

Not part of the automated test suite: this makes one real, billable API call
per turn. Run manually, or via the "WorldState walkthrough" GitHub Actions
workflow (workflow_dispatch).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.state_inspector import render
from src.interpretation.debug import analyze_interpretation
from src.interpretation.engine import InterpretationError, run_interpretation
from src.judgment.engine import run_judgment
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

    for i, message in enumerate(TRANSCRIPT, start=1):
        print(f"\n{'=' * 70}\nTURN {i}: {message}\n{'=' * 70}")

        try:
            interp = run_interpretation(message)
        except InterpretationError as exc:
            failures += 1
            print(f"[FAIL] turn {i}: {exc}")
            continue

        analyze_interpretation(interp)
        judgment = run_judgment(interp, state)
        print("\n--- JUDGMENT ---")
        print(judgment)

        state = update_state(state, interp)
        if judgment["recommended_next_phase"]:
            state.phase = judgment["recommended_next_phase"]

        print("\n--- WORLDSTATE AFTER TURN", i, "---")
        render(state)

    print(f"\n{'=' * 70}\nDone: {len(TRANSCRIPT) - failures}/{len(TRANSCRIPT)} turns succeeded.")
    print("Read through the WORLDSTATE output above turn by turn: does it read as an")
    print("increasingly faithful, coherent model of the user's world by turn 10?")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
