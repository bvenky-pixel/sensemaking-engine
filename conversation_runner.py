"""
conversation_runner.py -- manual developer CLI for Understanding Layer
"""

from __future__ import annotations

import argparse

from typing import List

from engine.state_inspector import render

from src.instrumentation.usage import UsageTracker, is_tracking_enabled, print_turn_summary
from src.interpretation.debug import analyze_interpretation
from src.orchestrator.engine import run_turn
from src.state.world_state import WorldState


DIVIDER = "=" * 50
EXIT_COMMANDS = {"exit", "quit"}


def run(model: str) -> None:
    print("Conversation Runner -- Understanding Layer inspector")
    print("Type a message and press Enter. Type 'exit' to quit.")
    print("-" * 50)

    state = WorldState()
    transcript: List[str] = []  # optional, currently unused
    tracker = UsageTracker()  # inert unless CONFIDANT_TRACK_USAGE is set

    while True:
        try:
            message = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSession ended.")
            break

        if not message:
            continue

        if message.lower() in EXIT_COMMANDS:
            print("Session ended.")
            break

        # Keep transcript for future multi-turn reasoning (optional)
        transcript.append(f"User: {message}")

        turn_start = tracker.count()
        outcome_start = tracker.outcome_count()

        try:
            # Orchestrator coordinates the fixed Interpretation -> WorldState
            # -> Judgment -> Planner -> Response Generator sequence and
            # reports exactly how far the turn got, even on a mid-pipeline
            # failure -- see src/orchestrator/engine.py. `result.state`
            # always reflects what's actually true (genuinely unchanged
            # only if Interpretation itself failed), so state is never lost
            # or misreported the way it was before Orchestrator existed.
            result = run_turn(message, state, tracker=tracker)
            state = result.state

            if result.interpretation:
                analyze_interpretation(result.interpretation)
                print("\n--- INTERPRETATION (internal) ---")
                print(result.interpretation.model_dump())

                print("\n--- STATE (internal) ---")
                render(state)

            if result.judgment:
                print("\n--- JUDGMENT (internal) ---")
                print(result.judgment.model_dump())

            if result.planner:
                print("\n--- PLANNER (internal) ---")
                print(result.planner.model_dump())

            if result.response:
                print("\n--- RESPONSE (user-facing) ---")
                print(result.response.response_text)
                print(f"[confidence={result.response.confidence}]")

            if result.error:
                print(f"\n[Error at {result.failed_stage}] {result.error}")

            if is_tracking_enabled():
                print_turn_summary(tracker.since(turn_start), tracker.outcomes_since(outcome_start))

        except Exception as exc:
            # Backstop only -- every EXPECTED failure mode (a stage's LLM
            # call failing) is already handled above via TurnResult, never
            # raised. This catches a genuinely unexpected bug (e.g. in
            # render() or analyze_interpretation()) so the REPL loop
            # survives instead of crashing outright.
            print(f"\n[Unexpected error] {exc}")

        print(DIVIDER)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect WorldState after every message."
    )

    parser.add_argument(
        "--model",
        default="claude-sonnet-5",
        help="Unused for now unless wired into interpretation engine."
    )

    args = parser.parse_args()
    run(model=args.model)


if __name__ == "__main__":
    main()
