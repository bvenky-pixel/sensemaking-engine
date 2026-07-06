"""
conversation_runner.py -- manual developer CLI for Understanding Layer
"""

from __future__ import annotations

import argparse

from typing import List

from engine.state_inspector import render

from src.instrumentation.usage import UsageTracker, is_tracking_enabled, print_turn_summary
from src.interpretation.debug import analyze_interpretation
from src.interpretation.engine import run_interpretation
from src.planner.engine import run_planner
from src.response.engine import run_response_generator
from src.state.builder import update_state
from src.state.world_state import WorldState
from src.judgment.engine import recommend_phase_transition, run_judgment


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
            # 1. Interpretation (LLM)
            interp = run_interpretation(message, tracker=tracker)
            analyze_interpretation(interp)

            # 2. State Builder -- WorldState must be updated with this
            # turn's Interpretation BEFORE Judgment runs, since Judgment
            # only ever sees WorldState (never the raw Interpretation).
            state = update_state(state, interp)

            next_phase = recommend_phase_transition(state)
            if next_phase:
                state.phase = next_phase

            # 3. Judgment (LLM, over the now-updated WorldState)
            judgment = run_judgment(state, tracker=tracker)

            # 4. Planner (LLM, over WorldState + Judgment -- never the raw
            # conversation or Interpretation, per the Planner spec's Inputs
            # section)
            plan = run_planner(state, judgment, tracker=tracker)

            # 5. Response Generator (LLM, over WorldState + Judgment +
            # Planner -- never the raw conversation or Interpretation).
            # This is the only artifact actually meant for the user;
            # everything above is internal, shown here for inspection.
            response = run_response_generator(state, judgment, plan, tracker=tracker)

            print("\n--- INTERPRETATION (internal) ---")
            print(interp.model_dump())

            print("\n--- STATE (internal) ---")
            render(state)

            print("\n--- JUDGMENT (internal) ---")
            print(judgment.model_dump())

            print("\n--- PLANNER (internal) ---")
            print(plan.model_dump())

            print("\n--- RESPONSE (user-facing) ---")
            print(response.response_text)
            print(f"[confidence={response.confidence}]")

            if is_tracking_enabled():
                print_turn_summary(tracker.since(turn_start), tracker.outcomes_since(outcome_start))

            print(DIVIDER)

        except Exception as exc:
            print(f"\n[Error] {exc}")
            print("State unchanged.")
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