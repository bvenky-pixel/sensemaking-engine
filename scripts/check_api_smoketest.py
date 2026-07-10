"""
Verification step for .github/workflows/api-smoketest.yml -- checks the
three JSON blobs the workflow captured from a real 2-turn conversation
against the live MVP API server (see src/api/server.py) and fails loudly
(non-zero exit) if either turn produced no response_text, or if the
persisted WorldState (fetched via GET /sessions/{id}/debug) didn't
actually accumulate any fact. Kept as a standalone script rather than an
inline shell heredoc, since heredoc-embedded Python is fragile against
YAML's own indentation (a literal leading-whitespace bug bit the first
draft of this workflow).
"""

from __future__ import annotations

import json
import os
import sys


def main() -> int:
    resp1 = json.loads(os.environ["RESP1"])
    resp2 = json.loads(os.environ["RESP2"])
    debug = json.loads(os.environ["DEBUG"])

    if not resp1.get("response_text"):
        print(f"FAIL: turn 1 got no response_text: {resp1}")
        return 1
    if not resp2.get("response_text"):
        print(f"FAIL: turn 2 got no response_text: {resp2}")
        return 1

    facts = debug.get("state", {}).get("facts", [])
    if len(facts) < 1:
        print(f"FAIL: expected at least one accumulated fact in persisted WorldState, got: {facts}")
        return 1

    print(
        f"OK: real response_text on both turns; {len(facts)} fact(s) "
        "accumulated in WorldState persisted across requests via SQLite."
    )
    print("Facts:", [f["content"] for f in facts])
    return 0


if __name__ == "__main__":
    sys.exit(main())
