"""
Live smoke test for StateUpdater against whichever provider is configured
in the environment (see engine/llm_config.py / .env.example).

Not part of the automated test suite -- this makes a real, billable API
call. Run it manually, or via the "LLM smoke test" GitHub Actions workflow
(workflow_dispatch), to confirm credentials/config actually work end to end.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.state import ConversationState
from engine.state_updater import StateUpdateError, StateUpdater


def main() -> int:
    updater = StateUpdater()
    print(f"Provider chain: {[p.name for p in updater.providers]}")

    transcript = (
        "User: My manager just told me the project I've been leading for "
        "six months is being cancelled, and I'm not sure whether to push "
        "back or just accept it."
    )

    try:
        state = updater.update(ConversationState(), transcript)
    except StateUpdateError as exc:
        print(f"FAILED: {exc}")
        if exc.raw_output:
            print(f"raw output: {exc.raw_output}")
        return 1

    print("SUCCESS -- updated ConversationState:")
    for field_name, value in vars(state).items():
        print(f"  {field_name}: {value!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
