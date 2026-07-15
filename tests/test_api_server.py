"""
Tests for the MVP API layer (src/api/). Deterministic: call_provider is
mocked at each engine module's own import path (same pattern as
tests/test_reliability_instrumentation.py, tests/test_evaluation_harness.py),
no real HTTP or LLM calls.

The one genuinely new thing this codebase has never exercised before
this file: WorldState surviving a round trip through SQLite
(model_dump_json -> stored -> model_validate_json on the next request).
Every other existing test only ever holds WorldState in-process for the
life of one function call. test_second_message_reflects_accumulated_state
below is built specifically to fail if that round trip is broken (each
turn's Interpretation mock introduces a DIFFERENT fact; if persistence
were silently starting fresh every request, only the second fact would
ever appear).
"""

from __future__ import annotations

import json
import socket
import tempfile
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient

from src.api import db, server

_MINIMAL_JUDGMENT = {
    "primary_problem": "",
    "primary_goal": "",
    "current_focus": "",
    "key_blockers": [],
    "secondary_issues": [],
    "open_unknowns": [],
    "active_decisions": [],
    "contradictions": [],
    "has_knowledge_correction": False,
    "knowledge_correction_target": "",
    "knowledge_correction_kind": "",
    "knowledge_correction_corrected_content": "",
    "has_risk_signal": False,
    "risk_scan": "No risk-worthy signal identified.",
    "risks": [],
    "opportunities": [],
    "has_decision_resolution": False,
    "decision_resolution_option": "",
    "decision_resolution_status": "",
    "stagnation_notes": [],
    "confidence": 0.5,
    "supporting_evidence": [],
}

_MINIMAL_PLANNER = {
    "primary_objective": "build understanding",
    "rationale": "Early turn, still gathering context.",
    "conversational_strategy": "ask exploratory questions",
    "resolution_blocker": "",
    "priority_topics": [],
    "questions_to_explore": [],
    "assumptions_to_test": [],
    "planning_constraints": [],
    "desired_outcome": "user shares more context",
    "temporal_horizon": "immediate",
    "confidence": 0.5,
}

_MINIMAL_RESPONSE = {
    "response_text": "Thanks for sharing that.",
    "confidence": 0.5,
}


def _minimal_interp(fact: str, goals=None, goal_updates=None) -> dict:
    return {
        "urgency": "low",
        "impact_domains": [],
        "emotional_signals": [],
        "surface_complaint": fact,
        "core_question": "",
        "core_question_confidence": 0.0,
        "observed_facts": [fact],
        "claims": [],
        "goals": goals or [],
        "goal_updates": goal_updates or [],
        "decision_options": [],
        "has_assumption": False,
        "assumption_check": "No framing-embedded assumption detected.",
        "assumptions": [],
        "inferences": [],
        "unknowns": [],
        "biases": [],
        "entities": [],
        "clarity_score": 0.5,
        "requires_clarification": False,
        "has_decision_event": False,
        "decision_event_option": "",
        "decision_event_type": "",
    }


def _always_returns(payload_or_list):
    """
    If given a list, returns each element in order across successive
    calls (used to make Interpretation's mock introduce a different
    fact per turn); otherwise always returns the same payload.
    """
    if isinstance(payload_or_list, list):
        state = {"calls": iter(payload_or_list)}

        def _call(provider_name, system_prompt, messages, schema, temperature, component="unknown", tracker=None):
            return json.dumps(next(state["calls"]))
        return _call

    def _call(provider_name, system_prompt, messages, schema, temperature, component="unknown", tracker=None):
        return json.dumps(payload_or_list)
    return _call


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(
        "src.judgment.engine.call_provider", _always_returns(_MINIMAL_JUDGMENT)
    )
    monkeypatch.setattr(
        "src.planner.engine.call_provider", _always_returns(_MINIMAL_PLANNER)
    )
    monkeypatch.setattr(
        "src.response.engine.call_provider", _always_returns(_MINIMAL_RESPONSE)
    )
    with TestClient(server.app) as c:
        yield c


def test_create_session_returns_id(client):
    res = client.post("/sessions")
    assert res.status_code == 200
    assert "id" in res.json()


def test_send_message_returns_response_text(client, monkeypatch):
    monkeypatch.setattr(
        "src.interpretation.engine.call_provider",
        _always_returns(_minimal_interp("User wants to move to the Product team.")),
    )
    session_id = client.post("/sessions").json()["id"]

    res = client.post(f"/sessions/{session_id}/messages", json={"content": "I want to move teams."})

    assert res.status_code == 200
    body = res.json()
    assert body["response_text"] == "Thanks for sharing that."
    assert body["failed_stage"] is None


def test_second_message_reflects_accumulated_state(client, monkeypatch):
    """
    Turn 1's Interpretation mock introduces Fact A; turn 2's introduces
    Fact B. If the session's WorldState didn't actually survive the
    SQLite round trip between requests, turn 2 would start from a blank
    WorldState and only Fact B would ever have existed -- this fails
    loudly in that case rather than silently passing.
    """
    monkeypatch.setattr(
        "src.interpretation.engine.call_provider",
        _always_returns([
            _minimal_interp("User wants to move to the Product team."),
            _minimal_interp("Sarah keeps deferring the transfer."),
        ]),
    )
    session_id = client.post("/sessions").json()["id"]

    client.post(f"/sessions/{session_id}/messages", json={"content": "I want to move teams."})
    client.post(f"/sessions/{session_id}/messages", json={"content": "Sarah keeps deferring."})

    debug = client.get(f"/sessions/{session_id}/debug").json()
    fact_contents = [f["content"] for f in debug["state"]["facts"]]

    assert "User wants to move to the Product team." in fact_contents
    assert "Sarah keeps deferring the transfer." in fact_contents


def test_list_messages_returns_transcript_in_order(client, monkeypatch):
    monkeypatch.setattr(
        "src.interpretation.engine.call_provider",
        _always_returns(_minimal_interp("User wants to move to the Product team.")),
    )
    session_id = client.post("/sessions").json()["id"]
    client.post(f"/sessions/{session_id}/messages", json={"content": "I want to move teams."})

    messages = client.get(f"/sessions/{session_id}/messages").json()

    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "I want to move teams."
    assert messages[1]["content"] == "Thanks for sharing that."


def test_unknown_session_returns_404(client):
    res = client.get("/sessions/does-not-exist/messages")
    assert res.status_code == 404


def test_list_sessions_returns_summaries_ordered_by_recency(client, monkeypatch):
    """Backs the real frontend's Home screen (a list of a person's
    Journeys) -- see frontend/decisions.md "Build the real Confidant
    frontend". Session B is created after A but never touched again, so
    sending a message to A (which bumps its updated_at) must move A back
    to the front of the list."""
    monkeypatch.setattr(
        "src.interpretation.engine.call_provider",
        _always_returns(_minimal_interp("User wants to move to the Product team.")),
    )
    session_a = client.post("/sessions").json()["id"]
    session_b = client.post("/sessions").json()["id"]

    client.post(f"/sessions/{session_a}/messages", json={"content": "I want to move teams."})

    summaries = client.get("/sessions").json()
    ids_in_order = [s["id"] for s in summaries]

    assert ids_in_order[0] == session_a
    assert session_b in ids_in_order
    matching = [s for s in summaries if s["id"] == session_a][0]
    # preview_text is the session's first RAW user message (see
    # engine/decisions.md "Frontend UX pass") -- not the mocked
    # surface_complaint ("User wants to move to the Product team."),
    # which is a separate, Interpretation-derived paraphrase.
    assert matching["preview_text"] == "I want to move teams."


def test_preview_text_stays_stable_across_later_turns(client, monkeypatch):
    """Regression test for a real, live-observed issue (see
    engine/decisions.md "Frontend UX pass"): previously this field was
    literally the live WorldState.surface_complaint, overwritten every
    turn -- a session's Home-screen label would change on every message
    instead of staying a stable "what this Journey is about." Fixed by
    sourcing it from the FIRST user message instead."""
    monkeypatch.setattr(
        "src.interpretation.engine.call_provider",
        _always_returns([
            _minimal_interp("User wants to move to the Product team."),
            _minimal_interp("User is now unsure about the move."),
        ]),
    )
    session_id = client.post("/sessions").json()["id"]
    client.post(f"/sessions/{session_id}/messages", json={"content": "I want to move teams."})
    client.post(f"/sessions/{session_id}/messages", json={"content": "Actually, I'm not so sure anymore."})

    summaries = client.get("/sessions").json()
    matching = [s for s in summaries if s["id"] == session_id][0]
    assert matching["preview_text"] == "I want to move teams."


def test_preview_text_falls_back_to_surface_complaint_before_any_message(client):
    """A session with zero messages yet (just created) has nothing in
    the messages table to source a preview from -- falls back to
    WorldState.surface_complaint, which is also empty for a fresh
    session, matching what the frontend already renders as "A new
    Journey" for an empty preview_text."""
    session_id = client.post("/sessions").json()["id"]
    summaries = client.get("/sessions").json()
    matching = [s for s in summaries if s["id"] == session_id][0]
    assert matching["preview_text"] == ""


def test_sessions_default_unbookmarked(client):
    session_id = client.post("/sessions").json()["id"]
    summaries = client.get("/sessions").json()
    matching = [s for s in summaries if s["id"] == session_id][0]
    assert matching["bookmarked"] is False


def test_bookmark_toggle_persists_and_filters(client):
    """Added for the Home redesign (see frontend/decisions.md) -- bookmarking
    a session must both persist across a fresh GET /sessions call and
    correctly filter when bookmarked_only=true, without pulling in an
    unbookmarked session."""
    session_a = client.post("/sessions").json()["id"]
    session_b = client.post("/sessions").json()["id"]

    res = client.post(f"/sessions/{session_a}/bookmark", json={"bookmarked": True})
    assert res.status_code == 200
    assert res.json()["bookmarked"] is True

    all_summaries = client.get("/sessions").json()
    matching_a = [s for s in all_summaries if s["id"] == session_a][0]
    matching_b = [s for s in all_summaries if s["id"] == session_b][0]
    assert matching_a["bookmarked"] is True
    assert matching_b["bookmarked"] is False

    filtered = client.get("/sessions?bookmarked_only=true").json()
    filtered_ids = [s["id"] for s in filtered]
    assert session_a in filtered_ids
    assert session_b not in filtered_ids

    # Un-bookmarking removes it from the filtered view again.
    client.post(f"/sessions/{session_a}/bookmark", json={"bookmarked": False})
    filtered_again = client.get("/sessions?bookmarked_only=true").json()
    assert session_a not in [s["id"] for s in filtered_again]


def test_bookmark_unknown_session_returns_404(client):
    res = client.post("/sessions/does-not-exist/bookmark", json={"bookmarked": True})
    assert res.status_code == 404


def test_has_stagnation_signal_false_for_fresh_session(client):
    """A brand-new session (turn_count=0, no goals/decisions) has nothing
    for compute_stagnation_signals to flag."""
    session_id = client.post("/sessions").json()["id"]
    summaries = client.get("/sessions").json()
    matching = [s for s in summaries if s["id"] == session_id][0]
    assert matching["has_stagnation_signal"] is False


def test_has_stagnation_signal_true_when_a_decision_is_stale(client, monkeypatch):
    """Directly exercises db.list_sessions' use of compute_stagnation_signals
    against a real stored WorldState -- construct one with a stale open
    Decision (gap >= STAGNATION_TURN_THRESHOLD) and confirm the flag
    reflects it, mirroring tests/test_judgment_stagnation.py's own
    Provenance-construction pattern."""
    from src.api import db as db_module
    from src.state.world_state import Decision, Provenance, WorldState

    session_id = client.post("/sessions").json()["id"]
    stale_state = WorldState(
        turn_count=10,
        decisions=[
            Decision(
                content="Whether to accept the offer",
                status="open",
                provenance=Provenance(source="interpretation", first_seen=1, last_updated=1),
            )
        ],
    )
    with db_module._connect() as conn:
        conn.execute(
            "UPDATE sessions SET world_state_json = ? WHERE id = ?",
            (stale_state.model_dump_json(), session_id),
        )

    summaries = client.get("/sessions").json()
    matching = [s for s in summaries if s["id"] == session_id][0]
    assert matching["has_stagnation_signal"] is True


def _goal_update_turns():
    return [
        _minimal_interp("User wants to move to the Product team.", goals=["Move to the Product team."]),
        _minimal_interp(
            "User's goal is now complete.",
            goal_updates=[{"goal": "Move to the Product team.", "status": "completed"}],
        ),
    ]


def test_behavioral_events_not_recorded_when_flag_is_off(client, monkeypatch):
    """CONFIDANT_RECORD_EVENTS is off by default (see
    src/instrumentation/events.py::is_events_enabled) -- real behavioral
    data must not silently accumulate without this explicitly set, per
    trust-and-privacy-ux-v1.md's Principle 6 (amended for this feature)."""
    monkeypatch.delenv("CONFIDANT_RECORD_EVENTS", raising=False)
    monkeypatch.setattr(
        "src.interpretation.engine.call_provider", _always_returns(_goal_update_turns())
    )
    session_id = client.post("/sessions").json()["id"]

    client.post(f"/sessions/{session_id}/messages", json={"content": "I want to move teams."})
    client.post(f"/sessions/{session_id}/messages", json={"content": "It happened!"})

    assert db.get_all_events() == []


def test_real_goal_status_change_is_recorded_to_memory_store_when_enabled(client, monkeypatch):
    """End-to-end, with CONFIDANT_RECORD_EVENTS explicitly on: a Goal
    created in turn 1, transitioned in turn 2 via a real goal_updates
    signal, must produce exactly one behavioral_events row -- exercises
    the full send_message -> run_turn -> diff_behavioral_events ->
    db.save_events chain (see engine/specs/architecture-roadmap-v1.md
    Phase 1), not just the pure diff_behavioral_events unit tests."""
    monkeypatch.setenv("CONFIDANT_RECORD_EVENTS", "1")
    monkeypatch.setattr(
        "src.interpretation.engine.call_provider", _always_returns(_goal_update_turns())
    )
    session_id = client.post("/sessions").json()["id"]

    client.post(f"/sessions/{session_id}/messages", json={"content": "I want to move teams."})
    client.post(f"/sessions/{session_id}/messages", json={"content": "It happened!"})

    events = db.get_all_events()
    assert len(events) == 1
    assert events[0].event_type == "goal_status_changed"
    assert events[0].old_status == "active"
    assert events[0].new_status == "completed"
    assert events[0].session_id == session_id


def test_patterns_endpoint_empty_before_learning_has_run(client):
    assert client.get("/patterns").json() == []


def test_patterns_endpoint_reflects_last_computed_batch(client):
    """GET /patterns serves whatever scripts/run_learning.py last wrote --
    exercised here at the db layer directly, since the endpoint itself
    must stay read-only (see engine/specs/architecture-roadmap-v1.md:
    Learning runs offline, never inside a live request)."""
    from src.learning.engine import Pattern

    db.replace_learned_patterns(
        [Pattern(pattern_type="decision_status_changed", detail="3 of your decisions...", evidence_count=3)]
    )

    body = client.get("/patterns").json()
    assert len(body) == 1
    assert body[0]["evidence_count"] == 3

    # Truncate-and-replace, not append -- a second run must not accumulate.
    db.replace_learned_patterns([])
    assert client.get("/patterns").json() == []


def test_clarity_brief_returns_404_before_any_completed_turn(client):
    session_id = client.post("/sessions").json()["id"]
    res = client.get(f"/sessions/{session_id}/clarity-brief")
    assert res.status_code == 404


def test_clarity_brief_reflects_completed_turn(client, monkeypatch):
    """Exercises the Executor's fixed template (src/executor/engine.py)
    through the live endpoint -- situation/current_direction/decisions
    come from WorldState/Planner directly, key_insights/remaining_unknowns
    are Judgment's curated subset, not a raw WorldState dump."""
    monkeypatch.setattr(
        "src.interpretation.engine.call_provider",
        _always_returns(_minimal_interp("User wants to move to the Product team.")),
    )
    populated_judgment = dict(_MINIMAL_JUDGMENT)
    populated_judgment.update(
        {
            "primary_problem": "Founder resists the move.",
            "risks": ["Founder may block the transfer."],
            "opportunities": ["A new manager could sponsor it."],
            "open_unknowns": ["What does the user want next?"],
            "secondary_issues": ["Strained relationship with their current manager."],
            "stagnation_notes": ["No movement on this goal in 4 turns."],
        }
    )
    monkeypatch.setattr("src.judgment.engine.call_provider", _always_returns(populated_judgment))
    populated_planner = dict(_MINIMAL_PLANNER)
    populated_planner["desired_outcome"] = "user gains clarity on next steps"
    monkeypatch.setattr("src.planner.engine.call_provider", _always_returns(populated_planner))

    session_id = client.post("/sessions").json()["id"]
    # Deliberately worded NOT to overlap with the mocked surface_complaint
    # below ("User wants to move to the Product team.") -- see
    # test_clarity_brief_suppresses_situation_when_it_echoes_the_last_message
    # for the dedicated test of that separate behavior; this test's own
    # purpose is the field MAPPING, which the echo-suppression would
    # otherwise interfere with.
    client.post(f"/sessions/{session_id}/messages", json={"content": "Ugh, today was a rough day."})

    res = client.get(f"/sessions/{session_id}/clarity-brief")

    assert res.status_code == 200
    body = res.json()
    # Major update (see engine/decisions.md): every brief field -- plus
    # secondary_issues/stagnation_notes, which bypass build_clarity_brief's
    # mapping but are just as user-facing -- is voice-rewritten via
    # src/executor/voice.py::to_second_person before reaching the client.
    assert body["situation"] == "You want to move to the Product team."
    assert body["key_insights"] == [
        "Founder resists the move.",
        "Founder may block the transfer.",
        "A new manager could sponsor it.",
    ]
    assert body["current_direction"] == "you gain clarity on next steps"
    assert body["remaining_unknowns"] == ["What do you want next?"]
    assert body["decisions"] == []
    assert "# Clarity Brief" in body["rendered_markdown"]
    # Passed through directly from Judgment (not part of Executor's own
    # fixed template) -- see src/api/schema.py's ClarityBriefResponse docstring.
    # "their" here possessively refers back to the user ("their [own]
    # manager"), but the string doesn't contain "user" text for
    # to_second_person to anchor a rewrite on, and "manager" being present
    # makes the conservative pronoun-rewrite guard skip it entirely (see
    # src/executor/voice.py's own documented trade-off) -- left unchanged
    # is the correct, expected behavior here, not a bug.
    assert body["secondary_issues"] == ["Strained relationship with their current manager."]
    assert body["stagnation_notes"] == ["No movement on this goal in 4 turns."]


def test_clarity_brief_suppresses_situation_when_it_echoes_the_last_message(client, monkeypatch):
    """Regression test for a real, live-observed issue (see
    engine/decisions.md "Frontend UX pass"): `situation` is, by
    construction, always a light paraphrase of the most recent message
    -- surfacing it as its own card directly below the actual chat
    transcript just repeats the person's own words back to them."""
    monkeypatch.setattr(
        "src.interpretation.engine.call_provider",
        _always_returns(_minimal_interp("User wants to move to the Product team.")),
    )
    monkeypatch.setattr("src.judgment.engine.call_provider", _always_returns(_MINIMAL_JUDGMENT))
    monkeypatch.setattr("src.planner.engine.call_provider", _always_returns(_MINIMAL_PLANNER))

    session_id = client.post("/sessions").json()["id"]
    client.post(f"/sessions/{session_id}/messages", json={"content": "I want to move teams."})

    res = client.get(f"/sessions/{session_id}/clarity-brief")
    assert res.status_code == 200
    assert res.json()["situation"] == ""


def test_understanding_empty_before_any_turn(client):
    """Unlike /clarity-brief, this never 404s -- an empty tier1/tier2
    list before any turn has completed is a valid, correct response."""
    session_id = client.post("/sessions").json()["id"]
    res = client.get(f"/sessions/{session_id}/understanding")
    assert res.status_code == 200
    assert res.json() == {"tier1": [], "tier2": []}


def test_understanding_reflects_tier1_after_a_completed_turn(client, monkeypatch):
    """Exercises the live endpoint end to end -- Tier 1 is computed
    unconditionally every turn (src/orchestrator/engine.py::run_turn),
    so a single completed turn already has real content."""
    monkeypatch.setattr(
        "src.interpretation.engine.call_provider",
        _always_returns(_minimal_interp("User wants to move to the Product team.")),
    )

    session_id = client.post("/sessions").json()["id"]
    client.post(f"/sessions/{session_id}/messages", json={"content": "I want to move teams."})

    res = client.get(f"/sessions/{session_id}/understanding")
    assert res.status_code == 200
    body = res.json()
    assert len(body["tier1"]) == 1
    statement = body["tier1"][0]
    assert statement["kind"] == "fact"
    assert statement["text"] == "You want to move to the Product team."
    assert statement["tier"] == 1
    assert statement["grounding_item_ids"]
    # Tier 2 needs MIN_GROUNDING_ITEMS (2) real candidates and a real
    # provider -- neither holds in this single-fact, no-API-key test
    # environment, so it stays empty (the common, expected case, not a
    # gap -- see src/understanding/tier2_engine.py's own module docstring).
    assert body["tier2"] == []


def test_understanding_unknown_session_returns_404(client):
    res = client.get("/sessions/does-not-exist/understanding")
    assert res.status_code == 404


def test_stream_endpoint_delivers_one_event_per_stage_during_a_live_turn(monkeypatch, tmp_path):
    """GET /sessions/{id}/stream, opened before the POST, must receive one
    SSE event per pipeline stage as run_turn's on_stage_complete callback
    fires (see src/orchestrator/engine.py, engine/decisions.md "Major
    update" Part 5) -- and the module's in-process queue must be cleaned
    up once the stream closes. Every OTHER test in this file never opens
    a stream, so their passing already confirms on_stage_complete=None
    (the default for every caller that doesn't stream) changes nothing
    about a normal POST /messages -- this test is the one exercising the
    callback actually firing.

    Deliberately NOT built on the `client` fixture's in-process TestClient:
    TestClient's single blocking portal serializes requests dispatched
    from separate Python threads (confirmed directly -- a concurrent GET
    only actually connects once a second request wakes the same portal),
    so a genuinely concurrent GET+POST needs a real live server. Runs
    uvicorn in a background thread against a real loopback socket instead
    -- this is what actually exercises asyncio.Queue's cross-thread
    call_soon_threadsafe handoff (see server.py's send_message) the way
    the deployed app really will."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "stream_test.db")
    monkeypatch.setattr("src.judgment.engine.call_provider", _always_returns(_MINIMAL_JUDGMENT))
    monkeypatch.setattr("src.planner.engine.call_provider", _always_returns(_MINIMAL_PLANNER))
    monkeypatch.setattr("src.response.engine.call_provider", _always_returns(_MINIMAL_RESPONSE))
    monkeypatch.setattr(
        "src.interpretation.engine.call_provider",
        _always_returns(_minimal_interp("User wants to move to the Product team.")),
    )

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    config = uvicorn.Config(server.app, host="127.0.0.1", port=port, log_level="warning")
    live_server = uvicorn.Server(config)
    server_thread = threading.Thread(target=live_server.run, daemon=True)
    server_thread.start()
    deadline = time.monotonic() + 5
    while not live_server.started and time.monotonic() < deadline:
        time.sleep(0.02)
    assert live_server.started, "uvicorn never started"

    try:
        base = f"http://127.0.0.1:{port}"
        session_id = httpx.post(f"{base}/sessions").json()["id"]

        received: list[str] = []
        connected = threading.Event()

        def _listen():
            with httpx.stream("GET", f"{base}/sessions/{session_id}/stream", timeout=10) as response:
                connected.set()
                for line in response.iter_lines():
                    if line.startswith("data: "):
                        received.append(json.loads(line[len("data: "):])["stage"])
                    if len(received) >= 4:
                        break

        listener = threading.Thread(target=_listen, daemon=True)
        listener.start()
        assert connected.wait(timeout=2), "stream never connected"

        res = httpx.post(
            f"{base}/sessions/{session_id}/messages", json={"content": "I want to move teams."}, timeout=10
        )
        assert res.status_code == 200

        listener.join(timeout=5)
        assert not listener.is_alive()
        assert received == ["interpretation", "judgment", "planner", "response"]
        # Same process, same imported server module -- uvicorn.Server was
        # constructed directly from server.app, not an import-string
        # subprocess, so server._stage_queues here really is the dict the
        # stream generator's finally block cleaned up.
        assert session_id not in server._stage_queues
    finally:
        live_server.should_exit = True
        server_thread.join(timeout=5)
