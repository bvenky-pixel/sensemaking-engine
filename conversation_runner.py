"""
conversation_runner.py -- manual developer CLI for the Understanding Layer.

PURPOSE
-------
Lets a developer type messages into the terminal, one at a time, and watch
ConversationState evolve after each one. There is no assistant reply
generated -- this tool exists purely to observe StateUpdater's behavior in
isolation, turn by turn.

FLOW PER TURN
-------------
1. Prompt for input in the terminal.
2. Append the message to the in-memory transcript.
3. Call StateUpdater with the current state + full transcript.
4. Replace the current state with the validated result.
5. Render the new state with StateInspector.
6. Print a divider.
Repeat until you type "exit" (or "quit").

REQUIREMENTS
------------
- Python 3.9+
- `anthropic` and `pydantic` installed (StateUpdater's dependencies)
- ANTHROPIC_API_KEY set in your environment

RUNNING IT
----------
    export ANTHROPIC_API_KEY=sk-ant-...
    python conversation_runner.py

    # optionally pin a different model:
    python conversation_runner.py --model claude-sonnet-5

EXAMPLE SESSION
----------------
    $ python conversation_runner.py
    Conversation Runner -- Understanding Layer inspector
    Type a message and press Enter. Type 'exit' to quit.
    --------------------------------------------------

    You: My partnerships team is upset about a landing page escalation
         and I don't know how direct to be in my response.

    ==================================================
                    CONVERSATION STATE
    ==================================================
    Emotion
    -------
    Anxious (6/10)
    ...
    ==================================================

    ==================================================

    You: exit
    Session ended.

This script does NOT generate assistant replies. It only exercises
StateUpdater + StateInspector against whatever you type.
"""

from __future__ import annotations

import argparse
import sys
from typing import List

from engine.state import ConversationState
from engine.state_inspector import render
from engine.state_updater import StateUpdater, StateUpdateError

DIVIDER = "=" * 50
EXIT_COMMANDS = {"exit", "quit"}


def build_transcript(turns: List[str]) -> str:
    """Join accumulated turns into the flat transcript text StateUpdater
    expects. Each turn is already prefixed with its speaker label."""
    return "\n".join(turns)


def run(model: str) -> None:
    print("Conversation Runner -- Understanding Layer inspector")
    print("Type a message and press Enter. Type 'exit' to quit.")
    print("-" * 50)

    try:
        updater = StateUpdater(model=model)
    except Exception as exc:
        print(f"Failed to initialize StateUpdater: {exc}")
        print("Check that ANTHROPIC_API_KEY is set and 'anthropic'/'pydantic' are installed.")
        sys.exit(1)

    state = ConversationState()
    transcript: List[str] = []

    while True:
        try:
            message = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSession ended.")
            break

        if not message:
            # Nothing typed -- don't waste a turn or an API call on it.
            continue

        if message.lower() in EXIT_COMMANDS:
            print("Session ended.")
            break

        transcript.append(f"User: {message}")

        try:
            state = updater.update(state, build_transcript(transcript))
        except StateUpdateError as exc:
            print(f"\n[StateUpdater error] {exc}")
            if exc.raw_output:
                print(f"[raw model output] {exc.raw_output}")
            print("State was left unchanged for this turn.")
            print(DIVIDER)
            continue
        except Exception as exc:
            # Catch-all so a single bad turn can't crash the session --
            # this is a debugging tool, it should keep running.
            print(f"\n[Unexpected error] {exc}")
            print("State was left unchanged for this turn.")
            print(DIVIDER)
            continue

        print()
        print(render(state))
        print(DIVIDER)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manually chat with the Understanding Layer and inspect "
        "ConversationState after every message."
    )
    parser.add_argument(
        "--model",
        default="claude-sonnet-5",
        help="Claude model to pass to StateUpdater (default: claude-sonnet-5).",
    )
    args = parser.parse_args()
    run(model=args.model)


if __name__ == "__main__":
    main()
