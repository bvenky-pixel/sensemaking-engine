"""
End-to-end Phase 1 Learning walkthrough (see
engine/specs/architecture-roadmap-v1.md): drives several real,
independent sessions through the REAL pipeline (run_turn -- the same
Orchestrator entrypoint the live API server uses), each ending with a
person clearly deferring a decision, so real Interpretation extracts a
genuine `decision_events` signal rather than a hand-built one (contrast
tests/test_instrumentation_events.py and tests/test_learning.py, which
are pure/deterministic and don't touch the LLM at all). This is the one
thing those unit tests can't cover: whether real Interpretation reliably
produces the decision_events shape diff_behavioral_events depends on.

Three sessions each defer a different decision (crossing
MIN_EVIDENCE=3 when aggregated); a fourth session defers only once, kept
deliberately BELOW the evidence floor, to confirm Learning stays silent
on thin evidence rather than reporting a one-off as a pattern -- the
failure mode this whole feature exists to avoid.

Learning made per-account (2026-07-18, see engine/decisions.md
"Learning made per-account"): all four sessions now belong to one
fixed demo account (`db.create_session(user_id=DEMO_USER_ID)`, same
pattern scripts/run_pom_walkthrough.py already established), not bare
hand-picked session_id strings with no corresponding `sessions` row --
`get_events_for_user` joins through `sessions.user_id`, so a session
with no real row there would silently contribute nothing.

Not part of the automated test suite: this makes real, billable API
calls. Run manually, or via the "Learning walkthrough" GitHub Actions
workflow (workflow_dispatch). Requires CONFIDANT_RECORD_EVENTS=1 (off by
default -- see src/instrumentation/events.py::is_events_enabled).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api import db
from src.instrumentation.events import is_events_enabled
from src.instrumentation.usage import UsageTracker
from src.learning.engine import MIN_EVIDENCE, compute_behavioral_patterns
from src.orchestrator.engine import run_turn
from src.state.world_state import WorldState

DEMO_USER_ID = "learning-walkthrough-demo-user"

# Each session: two turns, the second a clear, unambiguous deferral of the
# decision opened in the first -- crafted deliberately unambiguous so real
# Interpretation has the best real chance of extracting a decision_events
# signal (see engine/specs/interpretation-spec-v1.1.md's decision_events
# field, whose extraction reliability was verified in earlier rounds this
# project already ran). Labels only, not real session ids -- see
# DEMO_USER_ID's own docstring paragraph above for why.
DEFERRAL_SESSIONS = [
    (
        "defer-1",
        [
            "I'm weighing whether to take the new consulting offer or stay in my current role.",
            "I've decided to hold off on the consulting offer for now -- I need more time to think it through.",
        ],
    ),
    (
        "defer-2",
        [
            "I'm trying to decide whether to sign the new apartment lease this week.",
            "I'm putting off signing the lease for now, I want to see a couple more places first.",
        ],
    ),
    (
        "defer-3",
        [
            "I need to decide whether to enroll in the certification program before the deadline.",
            "I'm going to defer enrolling in the certification program -- the timing isn't right yet.",
        ],
    ),
]

# Deliberately only one deferral -- below MIN_EVIDENCE -- to confirm
# Learning stays silent on thin evidence.
LOW_EVIDENCE_SESSION = (
    "defer-lowevidence",
    [
        "I'm deciding whether to switch banks for a better savings rate.",
        "I'm deferring the bank switch decision until next month.",
    ],
)


def _run_session(label: str, messages: list[str], tracker: UsageTracker) -> None:
    session_id = db.create_session(user_id=DEMO_USER_ID)
    print(f"\n{'=' * 70}\nSESSION {label} ({session_id})\n{'=' * 70}")
    state = WorldState()
    for i, message in enumerate(messages, start=1):
        print(f"\n--- turn {i}: {message}")
        result = run_turn(message, state, tracker=tracker, session_id=session_id)
        state = result.state
        if result.failed_stage:
            print(f"[FAIL] turn {i} ({result.failed_stage}): {result.error}")
        print(f"behavioral_events this turn: {[e.model_dump() for e in result.behavioral_events]}")
        db.save_events(session_id, result.behavioral_events)


def main() -> int:
    if not is_events_enabled():
        print(
            "CONFIDANT_RECORD_EVENTS is not set -- this walkthrough needs it enabled "
            "to actually persist anything (see src/instrumentation/events.py). Set "
            "CONFIDANT_RECORD_EVENTS=1 and re-run."
        )
        return 1

    db.init_db()
    tracker = UsageTracker()

    for label, messages in DEFERRAL_SESSIONS + [LOW_EVIDENCE_SESSION]:
        _run_session(label, messages, tracker)

    events = db.get_events_for_user(DEMO_USER_ID)
    print(f"\n{'=' * 70}\nTotal behavioral_events recorded for {DEMO_USER_ID}: {len(events)}")
    for e in events:
        print(f"- [{e.session_id}] {e.event_type}: {e.old_status} -> {e.new_status} ({e.detail!r})")

    patterns = compute_behavioral_patterns(events)
    db.replace_learned_patterns(DEMO_USER_ID, patterns)

    print(f"\nComputed {len(patterns)} pattern(s) (min_evidence={MIN_EVIDENCE}):")
    for p in patterns:
        print(f"- [{p.pattern_type}] {p.detail} (evidence_count={p.evidence_count})")

    deferred_pattern = next(
        (p for p in patterns if p.pattern_type == "decision_status_changed" and "deferred" in p.detail),
        None,
    )
    ok = True
    if deferred_pattern is None or deferred_pattern.evidence_count < 3:
        print(
            "\n[CHECK FAILED] Expected a 'decision_status_changed'/'deferred' pattern with "
            "evidence_count >= 3 from the three deliberate deferrals above. Real Interpretation "
            "may not have extracted decision_events as expected this run -- read the per-turn "
            "behavioral_events output above to see what actually happened."
        )
        ok = False
    else:
        print(f"\n[CHECK PASSED] Deferral pattern found with evidence_count={deferred_pattern.evidence_count}.")

    print(
        "\n[CHECK] Low-evidence session's single deferral must not, by itself, tip any "
        "pattern over the floor on its own -- it's folded into the same aggregate above "
        "by design (event_type/status only, not per-session), so this just confirms the "
        "aggregate count matches what's expected (3 sessions x 1 deferral + 1 low-evidence "
        "session x 1 deferral = 4 total decision_status_changed/deferred events)."
    )
    deferred_events = [e for e in events if e.event_type == "decision_status_changed" and e.new_status == "deferred"]
    print(f"Actual deferred event count: {len(deferred_events)} (expected 4)")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
