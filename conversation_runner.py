"""
conversation_runner.py -- manual developer CLI for Understanding Layer
"""

from __future__ import annotations

import argparse
import sys

from typing import List

from engine.state import ConversationState
from engine.state_inspector import render

from src.interpretation.debug import analyze_interpretation
from src.interpretation.engine import run_interpretation
from src.state.builder import update_state
from src.judgment.engine import run_judgment


DIVIDER = "=" * 50
EXIT_COMMANDS = {"exit", "quit"}


def run(model: str) -> None:
    print("Conversation Runner -- Understanding Layer inspector")
    print("Type a message and press Enter. Type 'exit' to quit.")
    print("-" * 50)

    state = ConversationState()
    transcript: List[str] = []  # optional, currently unused

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

        try:
            # 1. Interpretation (LLM)
            interp = run_interpretation(message)

            analyze_interpretation(interp)

            judgment = run_judgment(interp, state)

            print("\n--- JUDGMENT ---")
            print(judgment)

            state = update_state(state, interp)

            if judgment["recommended_next_phase"]:
                state.phase = judgment["recommended_next_phase"]

            # 3. Debug view
            print("\n--- INTERPRETATION ---")
            print(interp.model_dump())

            print("\n--- STATE ---")
            render(state)

            print(DIVIDER)

        except Exception as exc:
            print(f"\n[Error] {exc}")
            print("State unchanged.")
            print(DIVIDER)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect ConversationState after every message."
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