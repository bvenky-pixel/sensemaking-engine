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
import sqlite3
import tempfile
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient

from src.api import db, rate_limit, server
from src.insight.schema import Insight
from src.learning.engine import Pattern
from src.pom.schema import IdentitySystem, PersonalOperatingModel

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


def _login(client, email="person@example.com"):
    """Test-only login helper (basic auth, see engine/decisions.md "Auth,
    the low-friction way") -- requests a real magic link through the
    actual endpoint, then reads the pending token straight out of
    SQLite rather than a real inbox (see src/api/email.py's own "no
    paid/external calls in tests" docstring), and verifies it through
    the actual endpoint too. `client` is a `TestClient`, which persists
    cookies across calls on the same instance, so every later request
    made with this same `client` is authenticated as this user."""
    client.post("/auth/request-link", json={"email": email})
    conn = sqlite3.connect(db.DB_PATH)
    try:
        row = conn.execute(
            "SELECT token FROM magic_links WHERE email = ? ORDER BY created_at DESC LIMIT 1",
            (email,),
        ).fetchone()
    finally:
        conn.close()
    res = client.post("/auth/verify", json={"token": row[0]})
    assert res.status_code == 200
    return email


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    # Rate limiting (2026-07-19, backlog #229, see engine/decisions.md
    # "Rate limiting added to auth and message endpoints") -- the
    # limiter is a module-level in-memory store, so without this reset
    # one test's hits would silently count against the next test's own
    # limit checks.
    rate_limit.reset_all()
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


def test_create_session_without_mode_persists_none(client):
    """Counseling modes (see engine/decisions.md, src/orchestrator/modes.py):
    every existing caller (and the frontend's own mode-select skip path)
    sends no body at all -- must still succeed, matching how this
    endpoint worked before this feature existed."""
    session_id = client.post("/sessions").json()["id"]
    assert db.get_session_mode(session_id) is None


def test_create_session_persists_a_chosen_mode(client):
    session_id = client.post("/sessions", json={"mode": "vent"}).json()["id"]
    assert db.get_session_mode(session_id) == "vent"


def test_create_session_rejects_an_unrecognized_mode(client):
    res = client.post("/sessions", json={"mode": "not-a-real-mode"})
    assert res.status_code == 422


def test_list_sessions_includes_chosen_mode(client):
    """Home: time period + mode filtering (2026-07-18, see
    frontend/decisions.md) -- GET /sessions never surfaced `mode`
    before, so Home's new per-period mode filter had no way to group
    without a separate request per session."""
    session_id = client.post("/sessions", json={"mode": "vent"}).json()["id"]
    db.append_message(session_id, "user", "Just needed to get this out.")

    summaries = client.get("/sessions").json()
    matching = [s for s in summaries if s["id"] == session_id][0]
    assert matching["mode"] == "vent"


def test_list_sessions_mode_is_null_when_none_was_chosen(client):
    session_id = client.post("/sessions").json()["id"]
    db.append_message(session_id, "user", "I want to move teams.")

    summaries = client.get("/sessions").json()
    matching = [s for s in summaries if s["id"] == session_id][0]
    assert matching["mode"] is None


def test_list_modes_returns_all_six_with_label_and_description(client):
    res = client.get("/modes")
    assert res.status_code == 200
    modes = res.json()
    assert {m["id"] for m in modes} == {
        "vent", "strategize", "commit", "explore", "realign", "adaptive",
    }
    for m in modes:
        assert m["label"]
        assert m["description"]


def _spy_call_provider(payload, seen, key):
    """Same shape as _always_returns above, but also records the
    system_prompt/messages it was actually called with under `seen[key]`
    -- used to verify a mode's focus note actually reaches Planner's/
    Response's own prompt, not just that run_turn accepted the parameter."""

    def _call(provider_name, system_prompt, messages, schema, temperature, component="unknown", tracker=None):
        seen[key] = (system_prompt, messages)
        return json.dumps(payload)
    return _call


def test_send_message_threads_mode_focus_note_into_planner_and_response_prompts(client, monkeypatch):
    seen = {}
    monkeypatch.setattr(
        "src.interpretation.engine.call_provider",
        _always_returns(_minimal_interp("User wants to move to the Product team.")),
    )
    monkeypatch.setattr(
        "src.planner.engine.call_provider", _spy_call_provider(_MINIMAL_PLANNER, seen, "planner")
    )
    monkeypatch.setattr(
        "src.response.engine.call_provider", _spy_call_provider(_MINIMAL_RESPONSE, seen, "response")
    )
    session_id = client.post("/sessions", json={"mode": "vent"}).json()["id"]

    client.post(f"/sessions/{session_id}/messages", json={"content": "I want to move teams."})

    _, planner_messages = seen["planner"]
    _, response_messages = seen["response"]
    assert "This Journey was started in Vent mode:" in planner_messages[0]["content"]
    assert "This Journey was started in Vent mode:" in response_messages[0]["content"]


def test_send_message_omits_mode_focus_note_when_no_mode_was_chosen(client, monkeypatch):
    seen = {}
    monkeypatch.setattr(
        "src.interpretation.engine.call_provider",
        _always_returns(_minimal_interp("User wants to move to the Product team.")),
    )
    monkeypatch.setattr(
        "src.planner.engine.call_provider", _spy_call_provider(_MINIMAL_PLANNER, seen, "planner")
    )
    session_id = client.post("/sessions").json()["id"]

    client.post(f"/sessions/{session_id}/messages", json={"content": "I want to move teams."})

    _, planner_messages = seen["planner"]
    assert "This Journey was started in" not in planner_messages[0]["content"]


def test_send_message_in_adaptive_mode_threads_planners_chosen_lens_into_response_prompt(client, monkeypatch):
    """Synthesis end-to-end (see engine/decisions.md "Synthesis"): a real
    Adaptive-mode turn, where Planner's own (mocked) output picks
    "commit" as this turn's active_lens, must reach Response as the
    CONCRETE "commit" focus note -- not the literal, focus-note-less
    string "adaptive"."""
    seen = {}
    monkeypatch.setattr(
        "src.interpretation.engine.call_provider",
        _always_returns(_minimal_interp("User said they'd apply for the internal transfer weeks ago.")),
    )
    monkeypatch.setattr(
        "src.planner.engine.call_provider",
        _spy_call_provider({**_MINIMAL_PLANNER, "active_lens": "commit"}, seen, "planner"),
    )
    monkeypatch.setattr(
        "src.response.engine.call_provider", _spy_call_provider(_MINIMAL_RESPONSE, seen, "response")
    )
    session_id = client.post("/sessions", json={"mode": "adaptive"}).json()["id"]

    client.post(f"/sessions/{session_id}/messages", json={"content": "I still haven't applied."})

    _, planner_messages = seen["planner"]
    _, response_messages = seen["response"]
    assert "This Journey was started in Adaptive mode:" in planner_messages[0]["content"]
    assert "This Journey was started in Commit mode:" in response_messages[0]["content"]


def test_send_message_threads_retrieved_context_into_judgment_prompt(client, monkeypatch):
    """Retrieval v1 (see engine/decisions.md "Retrieval",
    src/retrieval/engine.py): patterns/insights already stored in the DB
    by Learning/Insight Engine must actually reach Judgment's own prompt
    on the next live turn -- not just be readable via GET /learned-patterns
    and GET /insights.

    Learning made per-account (2026-07-18) and Insight Engine made
    per-account (2026-07-19, see engine/decisions.md for both) -- this
    now requires a signed-in caller for both halves, since neither
    patterns nor insights are readable by an anonymous caller anymore."""
    seen = {}
    monkeypatch.setattr(
        "src.interpretation.engine.call_provider",
        _always_returns(_minimal_interp("User wants to move to the Product team.")),
    )
    monkeypatch.setattr(
        "src.judgment.engine.call_provider", _spy_call_provider(_MINIMAL_JUDGMENT, seen, "judgment")
    )
    monkeypatch.setattr(
        "src.planner.engine.call_provider", _always_returns(_MINIMAL_PLANNER)
    )
    monkeypatch.setattr(
        "src.response.engine.call_provider", _always_returns(_MINIMAL_RESPONSE)
    )
    email = _login(client)
    user_id = db.get_or_create_user(email)
    db.replace_learned_patterns(user_id, [
        Pattern(pattern_type="decision_reversal", detail="Often reopens closed decisions", evidence_count=3)
    ])
    db.replace_insights(user_id, [
        Insight(theme="Career anxiety", detail="Recurring worry about job security", evidence_session_ids=[])
    ])
    session_id = client.post("/sessions").json()["id"]

    client.post(f"/sessions/{session_id}/messages", json={"content": "I want to move teams."})

    _, judgment_messages = seen["judgment"]
    content = judgment_messages[0]["content"]
    assert "Often reopens closed decisions" in content
    assert "Career anxiety" in content


def test_send_message_omits_retrieved_context_when_nothing_learned_yet(client, monkeypatch):
    seen = {}
    monkeypatch.setattr(
        "src.interpretation.engine.call_provider",
        _always_returns(_minimal_interp("User wants to move to the Product team.")),
    )
    monkeypatch.setattr(
        "src.judgment.engine.call_provider", _spy_call_provider(_MINIMAL_JUDGMENT, seen, "judgment")
    )
    monkeypatch.setattr(
        "src.planner.engine.call_provider", _always_returns(_MINIMAL_PLANNER)
    )
    monkeypatch.setattr(
        "src.response.engine.call_provider", _always_returns(_MINIMAL_RESPONSE)
    )
    session_id = client.post("/sessions").json()["id"]

    client.post(f"/sessions/{session_id}/messages", json={"content": "I want to move teams."})

    _, judgment_messages = seen["judgment"]
    assert "Retrieved Context" not in judgment_messages[0]["content"]


def test_send_message_rate_limited_per_identity(client, monkeypatch):
    """Rate limiting (2026-07-19, backlog #229, see engine/decisions.md
    "Rate limiting added to auth and message endpoints") -- direct
    regression test for the pace limit, distinct from
    ANONYMOUS_MESSAGE_LIMIT's own lifetime cap. Logged in specifically
    so the anonymous response-limit gate (10 messages) can't fire first
    and mask whether the rate limiter (20) is actually being reached."""
    monkeypatch.setattr(
        "src.interpretation.engine.call_provider",
        _always_returns(_minimal_interp("User wants to move to the Product team.")),
    )
    _login(client)
    session_id = client.post("/sessions").json()["id"]

    for _ in range(server._SEND_MESSAGE_PER_IDENTITY_LIMIT):
        res = client.post(f"/sessions/{session_id}/messages", json={"content": "Still thinking about it."})
        assert res.status_code == 200

    res = client.post(f"/sessions/{session_id}/messages", json={"content": "One more."})
    assert res.status_code == 429
    assert res.json()["detail"] == "rate_limited"


def test_send_message_threads_inferred_need_state_into_judgment_prompt(client, monkeypatch):
    """Need State Inference (see engine/decisions.md "Need State
    Inference", src/need_state/engine.py): once a real open Decision
    exists in a session's accumulated WorldState, the NEXT turn's
    infer_need_state(state) call must actually reach Judgment's prompt
    via Retrieved Context's new label -- not just be computable in
    isolation (already covered by tests/test_need_state.py)."""
    seen = {}
    monkeypatch.setattr(
        "src.interpretation.engine.call_provider",
        _always_returns({**_minimal_interp("User is weighing the job offer."), "decision_options": ["Take the job offer."]}),
    )
    monkeypatch.setattr(
        "src.planner.engine.call_provider", _always_returns(_MINIMAL_PLANNER)
    )
    monkeypatch.setattr(
        "src.response.engine.call_provider", _always_returns(_MINIMAL_RESPONSE)
    )
    session_id = client.post("/sessions").json()["id"]

    # Turn 1: establishes the open Decision in WorldState (judgment mock
    # is unspied here -- only the SECOND turn's prompt is under test,
    # since infer_need_state runs on the PRE-turn state loaded before
    # turn 2 begins). decision_options must be lexically grounded in the
    # user's own message text -- src/interpretation/engine.py's own
    # grounding filter (_is_option_grounded) strips any option that
    # isn't, same anti-hallucination guard as everywhere else in this
    # codebase.
    monkeypatch.setattr(
        "src.judgment.engine.call_provider", _always_returns(_MINIMAL_JUDGMENT)
    )
    client.post(f"/sessions/{session_id}/messages", json={"content": "I have a job offer to weigh."})

    monkeypatch.setattr(
        "src.judgment.engine.call_provider", _spy_call_provider(_MINIMAL_JUDGMENT, seen, "judgment")
    )
    client.post(f"/sessions/{session_id}/messages", json={"content": "Still thinking about it."})

    _, judgment_messages = seen["judgment"]
    content = judgment_messages[0]["content"]
    assert "This turn's inferred need: decision" in content


def test_send_message_threads_personal_operating_model_into_judgment_prompt(client, monkeypatch):
    """Personal Operating Model (see engine/decisions.md "Personal
    Operating Model", src/pom/engine.py): whatever
    scripts/run_pom_computation.py last computed offline and stored via
    db.replace_personal_operating_model must reach Judgment's real
    prompt on the next live turn -- read-only, no live computation.

    POM made per-user (2026-07-18, see engine/decisions.md "POM made
    per-user"): this now requires a signed-in caller, since an
    anonymous caller has no account to own a stored POM."""
    seen = {}
    monkeypatch.setattr(
        "src.interpretation.engine.call_provider",
        _always_returns(_minimal_interp("User wants to move to the Product team.")),
    )
    monkeypatch.setattr(
        "src.judgment.engine.call_provider", _spy_call_provider(_MINIMAL_JUDGMENT, seen, "judgment")
    )
    monkeypatch.setattr(
        "src.planner.engine.call_provider", _always_returns(_MINIMAL_PLANNER)
    )
    monkeypatch.setattr(
        "src.response.engine.call_provider", _always_returns(_MINIMAL_RESPONSE)
    )
    email = _login(client)
    user_id = db.get_or_create_user(email)
    db.replace_personal_operating_model(
        user_id, PersonalOperatingModel(identity=IdentitySystem(self_concept="Values independence at work."))
    )
    session_id = client.post("/sessions").json()["id"]

    client.post(f"/sessions/{session_id}/messages", json={"content": "I want to move teams."})

    _, judgment_messages = seen["judgment"]
    content = judgment_messages[0]["content"]
    assert "Identity: Values independence at work." in content


def test_send_message_omits_pom_content_when_nothing_computed_yet(client, monkeypatch):
    seen = {}
    monkeypatch.setattr(
        "src.interpretation.engine.call_provider",
        _always_returns(_minimal_interp("User wants to move to the Product team.")),
    )
    monkeypatch.setattr(
        "src.judgment.engine.call_provider", _spy_call_provider(_MINIMAL_JUDGMENT, seen, "judgment")
    )
    monkeypatch.setattr(
        "src.planner.engine.call_provider", _always_returns(_MINIMAL_PLANNER)
    )
    monkeypatch.setattr(
        "src.response.engine.call_provider", _always_returns(_MINIMAL_RESPONSE)
    )
    session_id = client.post("/sessions").json()["id"]

    client.post(f"/sessions/{session_id}/messages", json={"content": "I want to move teams."})

    _, judgment_messages = seen["judgment"]
    assert "Identity" not in judgment_messages[0]["content"]


def test_get_personal_operating_model_returns_null_before_any_computation(client):
    _login(client)
    res = client.get("/personal-operating-model")
    assert res.status_code == 200
    assert res.json() is None


def test_get_personal_operating_model_returns_last_computed_pom(client):
    email = _login(client)
    user_id = db.get_or_create_user(email)
    db.replace_personal_operating_model(
        user_id, PersonalOperatingModel(identity=IdentitySystem(self_concept="Values independence at work."))
    )
    res = client.get("/personal-operating-model")
    assert res.status_code == 200
    assert res.json()["identity"]["self_concept"] == "Values independence at work."


def test_get_personal_operating_model_never_returns_another_accounts_pom(client):
    """POM made per-user (2026-07-18, see engine/decisions.md "POM made
    per-user"): the direct regression test for the bug this round
    fixed -- a brand-new signed-in account must not inherit whatever
    POM was computed from a different account's own sessions."""
    other_user_id = db.get_or_create_user("someone-else@example.com")
    db.replace_personal_operating_model(
        other_user_id, PersonalOperatingModel(identity=IdentitySystem(self_concept="Someone else's profile."))
    )
    _login(client)

    res = client.get("/personal-operating-model")

    assert res.status_code == 200
    assert res.json() is None


def test_get_personal_operating_model_requires_login(client):
    """Direct regression test for the new gate (2026-07-18, see
    engine/decisions.md "POM surfaced to users") -- an anonymous caller
    (no _login here) must be turned away, same as the Privacy
    endpoints."""
    res = client.get("/personal-operating-model")
    assert res.status_code == 401
    assert res.json()["detail"] == "login_required"


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


def test_send_message_returns_options_when_response_generator_provides_them(client, monkeypatch):
    """Response v3 -- real choice buttons (see engine/decisions.md):
    options flows straight through from Response into the API layer."""
    monkeypatch.setattr(
        "src.interpretation.engine.call_provider",
        _always_returns(_minimal_interp("User is deciding between an MBA and buying a house.")),
    )
    monkeypatch.setattr(
        "src.response.engine.call_provider",
        _always_returns({
            **_MINIMAL_RESPONSE,
            "options": [
                {"label": "The MBA", "description": "You mentioned the program's tuition."},
                {"label": "The house", "description": "You mentioned the down payment."},
            ],
        }),
    )
    session_id = client.post("/sessions").json()["id"]

    res = client.post(f"/sessions/{session_id}/messages", json={"content": "House or MBA?"})

    assert res.json()["options"] == [
        {"label": "The MBA", "description": "You mentioned the program's tuition."},
        {"label": "The house", "description": "You mentioned the down payment."},
    ]


def test_send_message_returns_empty_options_by_default(client, monkeypatch):
    monkeypatch.setattr(
        "src.interpretation.engine.call_provider",
        _always_returns(_minimal_interp("User wants to move to the Product team.")),
    )
    session_id = client.post("/sessions").json()["id"]

    res = client.post(f"/sessions/{session_id}/messages", json={"content": "I want to move teams."})

    assert res.json()["options"] == []


def test_options_persist_across_a_reload(client, monkeypatch):
    """Options must survive a page reload (GET /sessions/{id}/messages),
    not just the live sendMessage response -- see src/api/db.py's
    options_json column."""
    monkeypatch.setattr(
        "src.interpretation.engine.call_provider",
        _always_returns(_minimal_interp("User is deciding between an MBA and buying a house.")),
    )
    monkeypatch.setattr(
        "src.response.engine.call_provider",
        _always_returns({
            **_MINIMAL_RESPONSE,
            "options": [
                {"label": "The MBA", "description": "You mentioned the program's tuition."},
                {"label": "The house", "description": "You mentioned the down payment."},
            ],
        }),
    )
    session_id = client.post("/sessions").json()["id"]
    client.post(f"/sessions/{session_id}/messages", json={"content": "House or MBA?"})

    messages = client.get(f"/sessions/{session_id}/messages").json()

    assert messages[0]["options"] == []  # the user's own message
    assert messages[1]["options"] == [
        {"label": "The MBA", "description": "You mentioned the program's tuition."},
        {"label": "The house", "description": "You mentioned the down payment."},
    ]


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
    frontend". Session B gets its own first message (so it's populated
    -- see "Only populated after a real message is shared" below) but
    is never touched again, so a SECOND message to A (which bumps its
    updated_at past B's) must move A back to the front of the list."""
    monkeypatch.setattr(
        "src.interpretation.engine.call_provider",
        _always_returns(_minimal_interp("User wants to move to the Product team.")),
    )
    session_a = client.post("/sessions").json()["id"]
    session_b = client.post("/sessions").json()["id"]

    client.post(f"/sessions/{session_b}/messages", json={"content": "Deciding between two job offers."})
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


def test_list_sessions_excludes_a_session_with_no_messages(client):
    """Only populated after a real message is shared (2026-07-18, see
    frontend/decisions.md "Only populate a Journey on Home after a real
    message is sent") -- direct founder feedback: createSession fires
    the moment a mode is picked, before anything is typed, so a person
    backing out of an empty Journey shouldn't leave a permanent "A new
    Journey" ghost on Home. Direct regression test for the
    list_sessions filter itself."""
    empty_session = client.post("/sessions").json()["id"]
    assert empty_session not in [s["id"] for s in client.get("/sessions").json()]


# Basic auth (2026-07-18, see engine/decisions.md "Auth, the low-friction
# way"). Two independent `TestClient(server.app)` instances against the
# SAME db path (the `client` fixture's own monkeypatched db.DB_PATH) --
# each TestClient has its own cookie jar, so this is the direct way to
# simulate "two different browsers" hitting one running server, the
# thing this whole feature exists to make actually true.
def test_anonymous_visitors_do_not_see_each_others_journeys(client, monkeypatch):
    """The exact pre-auth bug this round fixes: GET /sessions used to
    return literally every Journey in the database to every visitor."""
    monkeypatch.setattr(
        "src.interpretation.engine.call_provider",
        _always_returns(_minimal_interp("User wants to move to the Product team.")),
    )
    session_id = client.post("/sessions").json()["id"]
    client.post(f"/sessions/{session_id}/messages", json={"content": "I want to move teams."})
    assert session_id in [s["id"] for s in client.get("/sessions").json()]

    with TestClient(server.app) as other_browser:
        assert other_browser.get("/sessions").json() == []
        # Not just invisible on the list -- genuinely not theirs.
        assert other_browser.get(f"/sessions/{session_id}/messages").status_code == 404


def test_anonymous_session_owner_cannot_be_impersonated_by_a_guessed_id(client, monkeypatch):
    """A session_id belonging to a different visitor 404s (never 403)
    for every session-scoped action -- existence and ownership are
    indistinguishable from the outside. `other_browser` logs in as a
    DIFFERENT account (bookmark/delete are login-required actions in
    their own right -- see test_bookmark_and_delete_require_login below
    -- so proving ownership isolation specifically needs a signed-in
    stranger, not just an anonymous one)."""
    monkeypatch.setattr(
        "src.interpretation.engine.call_provider",
        _always_returns(_minimal_interp("User wants to move to the Product team.")),
    )
    session_id = client.post("/sessions").json()["id"]
    client.post(f"/sessions/{session_id}/messages", json={"content": "I want to move teams."})

    with TestClient(server.app) as other_browser:
        _login(other_browser, email="stranger@example.com")
        assert other_browser.post(f"/sessions/{session_id}/bookmark", json={"bookmarked": True}).status_code == 404
        assert other_browser.delete(f"/sessions/{session_id}").status_code == 404
        assert other_browser.post(
            f"/sessions/{session_id}/messages", json={"content": "hi"}
        ).status_code == 404


def test_bookmark_and_delete_require_login(client, monkeypatch):
    """Direct founder follow-up: bookmark and delete are login-required
    actions too, not just Settings/Privacy and the response cap --
    an anonymous caller (no _login here) is turned away before
    ownership is even checked, same `login_required` gate Settings
    uses. Reading the current bookmark state is deliberately NOT
    gated this way (see get_bookmark's own docstring) -- only the
    write/delete actions are."""
    monkeypatch.setattr(
        "src.interpretation.engine.call_provider",
        _always_returns(_minimal_interp("User wants to move to the Product team.")),
    )
    session_id = client.post("/sessions").json()["id"]
    client.post(f"/sessions/{session_id}/messages", json={"content": "I want to move teams."})

    bookmark_res = client.post(f"/sessions/{session_id}/bookmark", json={"bookmarked": True})
    assert bookmark_res.status_code == 401
    assert bookmark_res.json()["detail"] == "login_required"

    delete_res = client.delete(f"/sessions/{session_id}")
    assert delete_res.status_code == 401
    assert delete_res.json()["detail"] == "login_required"

    # The read is unaffected -- still works anonymously.
    assert client.get(f"/sessions/{session_id}/bookmark").status_code == 200


def test_request_magic_link_always_reports_sent_regardless_of_email(client):
    """Never reveals whether the email matched an existing account --
    the email-enumeration defense every real auth system needs."""
    res = client.post("/auth/request-link", json={"email": "nobody-yet@example.com"})
    assert res.json() == {"sent": True}


def test_request_magic_link_rate_limited_per_email(client):
    """Rate limiting (2026-07-19, backlog #229, see engine/decisions.md
    "Rate limiting added to auth and message endpoints") -- direct
    regression test for the per-email limit. Each request uses a
    distinct IP-equivalent (TestClient has no real network, so every
    call shares one IP bucket) -- staying under the per-IP limit
    (20) while exceeding the per-email limit (5) isolates which of the
    two actually fired."""
    for _ in range(server._AUTH_REQUEST_LINK_PER_EMAIL_LIMIT):
        res = client.post("/auth/request-link", json={"email": "hammered@example.com"})
        assert res.status_code == 200

    res = client.post("/auth/request-link", json={"email": "hammered@example.com"})
    assert res.status_code == 429
    assert res.json()["detail"] == "rate_limited"

    # A different email is unaffected -- the limit is per-email, not a
    # blanket lockout of the whole endpoint.
    res = client.post("/auth/request-link", json={"email": "someone-else@example.com"})
    assert res.status_code == 200


def test_verify_magic_link_logs_in_and_claims_anonymous_journeys(client, monkeypatch):
    """The actual value proposition of claim-on-login: a Journey begun
    before signing up must still be there afterward, under the new
    account -- and gone from the anonymous view, since it's no longer
    that browser's alone."""
    monkeypatch.setattr(
        "src.interpretation.engine.call_provider",
        _always_returns(_minimal_interp("User wants to move to the Product team.")),
    )
    session_id = client.post("/sessions").json()["id"]
    client.post(f"/sessions/{session_id}/messages", json={"content": "I want to move teams."})

    _login(client, email="claims-test@example.com")

    res = client.get("/auth/me")
    assert res.json() == {
        "authenticated": True, "email": "claims-test@example.com", "return_session_id": None,
    }
    assert session_id in [s["id"] for s in client.get("/sessions").json()]


def test_verify_magic_link_returns_the_session_id_it_was_requested_with(client, monkeypatch):
    """Response-limit login UX gap fix (2026-07-18, see engine/decisions.md
    "Return to the same Journey after magic-link verify"): the whole
    point of return_session_id is that clicking the link actually
    returns a person to the Journey they were in, not just Home."""
    monkeypatch.setattr(
        "src.interpretation.engine.call_provider",
        _always_returns(_minimal_interp("Thinking out loud.")),
    )
    session_id = client.post("/sessions").json()["id"]
    client.post(f"/sessions/{session_id}/messages", json={"content": "one thing"})

    client.post(
        "/auth/request-link",
        json={"email": "return-test@example.com", "return_session_id": session_id},
    )
    conn = sqlite3.connect(db.DB_PATH)
    try:
        row = conn.execute(
            "SELECT token FROM magic_links WHERE email = ? ORDER BY created_at DESC LIMIT 1",
            ("return-test@example.com",),
        ).fetchone()
    finally:
        conn.close()
    res = client.post("/auth/verify", json={"token": row[0]})
    assert res.json()["return_session_id"] == session_id


def test_verify_magic_link_omits_return_session_id_when_not_actually_owned(client):
    """A foreign/stale return_session_id (never claimed by this browser,
    e.g. a tampered request or a Journey deleted since) degrades to no
    redirect at all -- App.svelte falls back to Home -- rather than
    handing back an id this account doesn't actually own."""
    client.post(
        "/auth/request-link",
        json={"email": "no-claim-test@example.com", "return_session_id": "not-a-real-session-id"},
    )
    conn = sqlite3.connect(db.DB_PATH)
    try:
        row = conn.execute(
            "SELECT token FROM magic_links WHERE email = ? ORDER BY created_at DESC LIMIT 1",
            ("no-claim-test@example.com",),
        ).fetchone()
    finally:
        conn.close()
    res = client.post("/auth/verify", json={"token": row[0]})
    assert res.json()["return_session_id"] is None


def test_verify_magic_link_rejects_an_unknown_token(client):
    res = client.post("/auth/verify", json={"token": "not-a-real-token"})
    assert res.status_code == 404


def test_verify_magic_link_token_is_single_use(client):
    client.post("/auth/request-link", json={"email": "reuse-test@example.com"})
    conn = sqlite3.connect(db.DB_PATH)
    try:
        token = conn.execute(
            "SELECT token FROM magic_links WHERE email = ?", ("reuse-test@example.com",)
        ).fetchone()[0]
    finally:
        conn.close()

    assert client.post("/auth/verify", json={"token": token}).status_code == 200
    # Same token again -- already consumed, must not log in a second time.
    assert client.post("/auth/verify", json={"token": token}).status_code == 404


def test_logout_clears_the_session_cookie(client):
    _login(client, email="logout-test@example.com")
    assert client.get("/auth/me").json()["authenticated"] is True

    assert client.post("/auth/logout").status_code == 204
    assert client.get("/auth/me").json() == {
        "authenticated": False, "email": None, "return_session_id": None,
    }


def test_anonymous_sender_is_blocked_after_the_response_limit(client, monkeypatch):
    """ANONYMOUS_MESSAGE_LIMIT (see src/api/server.py) -- exactly 10 user
    messages succeed for free; the 11th is turned away with a stable,
    frontend-checkable error rather than a generic failure."""
    monkeypatch.setattr(
        "src.interpretation.engine.call_provider",
        _always_returns(_minimal_interp("Thinking out loud.")),
    )
    session_id = client.post("/sessions").json()["id"]
    for _ in range(10):
        res = client.post(f"/sessions/{session_id}/messages", json={"content": "Thinking out loud."})
        assert res.status_code == 200

    res = client.post(f"/sessions/{session_id}/messages", json={"content": "one more thing"})
    assert res.status_code == 401
    assert res.json()["detail"] == "response_limit_reached"


def test_signed_in_sender_is_never_capped(client, monkeypatch):
    monkeypatch.setattr(
        "src.interpretation.engine.call_provider",
        _always_returns(_minimal_interp("Thinking out loud.")),
    )
    _login(client, email="no-cap-test@example.com")
    session_id = client.post("/sessions").json()["id"]
    for _ in range(11):
        res = client.post(f"/sessions/{session_id}/messages", json={"content": "Thinking out loud."})
        assert res.status_code == 200


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


def test_sessions_default_unbookmarked(client):
    session_id = client.post("/sessions").json()["id"]
    # Only populated after a real message is shared (see
    # test_list_sessions_excludes_a_session_with_no_messages above) --
    # db.append_message directly, not a real POST /messages turn, since
    # this test only cares that a message exists, not what the pipeline
    # does with it.
    db.append_message(session_id, "user", "I want to move teams.")

    summaries = client.get("/sessions").json()
    matching = [s for s in summaries if s["id"] == session_id][0]
    assert matching["bookmarked"] is False


def test_bookmark_toggle_persists_and_filters(client):
    """Added for the Home redesign (see frontend/decisions.md) -- bookmarking
    a session must both persist across a fresh GET /sessions call and
    correctly filter when bookmarked_only=true, without pulling in an
    unbookmarked session."""
    _login(client)
    session_a = client.post("/sessions").json()["id"]
    session_b = client.post("/sessions").json()["id"]
    # Only populated after a real message is shared -- both need one to
    # appear in GET /sessions at all (see
    # test_list_sessions_excludes_a_session_with_no_messages).
    db.append_message(session_a, "user", "I want to move teams.")
    db.append_message(session_b, "user", "Deciding between two job offers.")

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
    _login(client)
    res = client.post("/sessions/does-not-exist/bookmark", json={"bookmarked": True})
    assert res.status_code == 404


def test_get_bookmark_defaults_to_false_for_a_new_session(client):
    """Added for Journey's own overflow menu (see frontend/decisions.md
    "Tuck destructive/secondary Journey actions behind an overflow
    menu") -- Journey.svelte needs to read a session's current
    bookmark state before rendering the toggle, unlike Home which
    already has it from list_sessions."""
    session_id = client.post("/sessions").json()["id"]
    res = client.get(f"/sessions/{session_id}/bookmark")
    assert res.status_code == 200
    assert res.json() == {"bookmarked": False}


def test_get_bookmark_reflects_a_prior_set(client):
    _login(client)
    session_id = client.post("/sessions").json()["id"]
    client.post(f"/sessions/{session_id}/bookmark", json={"bookmarked": True})

    res = client.get(f"/sessions/{session_id}/bookmark")
    assert res.json() == {"bookmarked": True}


def test_get_bookmark_unknown_session_returns_404(client):
    res = client.get("/sessions/does-not-exist/bookmark")
    assert res.status_code == 404


def test_delete_session_removes_it_from_the_list(client, monkeypatch):
    """Added for Settings' Data section (see engine/decisions.md
    "Frontend UX pass")."""
    monkeypatch.setattr(
        "src.interpretation.engine.call_provider",
        _always_returns(_minimal_interp("User wants to move to the Product team.")),
    )
    _login(client)
    session_id = client.post("/sessions").json()["id"]
    client.post(f"/sessions/{session_id}/messages", json={"content": "I want to move teams."})

    res = client.delete(f"/sessions/{session_id}")
    assert res.status_code == 204

    assert session_id not in [s["id"] for s in client.get("/sessions").json()]
    assert client.get(f"/sessions/{session_id}/messages").status_code == 404


def test_delete_session_does_not_affect_other_sessions(client, monkeypatch):
    monkeypatch.setattr(
        "src.interpretation.engine.call_provider",
        _always_returns(_minimal_interp("User wants to move to the Product team.")),
    )
    _login(client)
    session_a = client.post("/sessions").json()["id"]
    session_b = client.post("/sessions").json()["id"]
    client.post(f"/sessions/{session_a}/messages", json={"content": "I want to move teams."})
    # Only populated after a real message is shared -- B needs one too
    # to remain visible in GET /sessions once A is gone.
    db.append_message(session_b, "user", "Deciding between two job offers.")

    client.delete(f"/sessions/{session_a}")

    remaining_ids = [s["id"] for s in client.get("/sessions").json()]
    assert session_a not in remaining_ids
    assert session_b in remaining_ids


def test_delete_unknown_session_returns_404(client):
    _login(client)
    res = client.delete("/sessions/does-not-exist")
    assert res.status_code == 404


def test_has_stagnation_signal_false_for_fresh_session(client):
    """A brand-new session (turn_count=0, no goals/decisions) has nothing
    for compute_stagnation_signals to flag."""
    session_id = client.post("/sessions").json()["id"]
    # Only populated after a real message is shared -- needs one to
    # appear in GET /sessions at all; still turn_count=0/no
    # goals-or-decisions, so the assertion below is unaffected.
    db.append_message(session_id, "user", "I want to move teams.")

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
    # Only populated after a real message is shared -- needed for this
    # session to appear in GET /sessions at all; inserted directly
    # (not a real turn) so it doesn't disturb the world_state_json this
    # test injects below.
    db_module.append_message(session_id, "user", "I want to move teams.")
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


def test_patterns_endpoint_requires_login(client):
    """Learning made per-account (2026-07-18, see engine/decisions.md
    "Learning made per-account"): /patterns now requires a signed-in
    caller, same as /personal-operating-model -- learned_patterns is no
    longer a global model an anonymous caller could safely see."""
    res = client.get("/patterns")
    assert res.status_code == 401
    assert res.json()["detail"] == "login_required"


def test_patterns_endpoint_empty_before_learning_has_run(client):
    _login(client)
    assert client.get("/patterns").json() == []


def test_patterns_endpoint_reflects_last_computed_batch(client):
    """GET /patterns serves whatever scripts/run_learning.py last wrote
    for THIS account -- exercised here at the db layer directly, since
    the endpoint itself must stay read-only (see engine/specs/
    architecture-roadmap-v1.md: Learning runs offline, never inside a
    live request)."""
    from src.learning.engine import Pattern

    email = _login(client)
    user_id = db.get_or_create_user(email)
    db.replace_learned_patterns(
        user_id, [Pattern(pattern_type="decision_status_changed", detail="3 of your decisions...", evidence_count=3)]
    )

    body = client.get("/patterns").json()
    assert len(body) == 1
    assert body[0]["evidence_count"] == 3

    # Truncate-and-replace per account, not append -- a second run must
    # not accumulate.
    db.replace_learned_patterns(user_id, [])
    assert client.get("/patterns").json() == []


def test_patterns_endpoint_never_returns_another_accounts_patterns(client):
    """Learning made per-account (2026-07-18, see engine/decisions.md
    "Learning made per-account"): the direct regression test for the
    bug this round fixed -- a brand-new signed-in account must not
    inherit whatever patterns were computed from a different account's
    own behavioral events."""
    from src.learning.engine import Pattern

    other_user_id = db.get_or_create_user("someone-else-patterns@example.com")
    db.replace_learned_patterns(
        other_user_id, [Pattern(pattern_type="decision_status_changed", detail="Someone else's pattern.", evidence_count=3)]
    )

    _login(client, email="fresh-account-patterns@example.com")
    assert client.get("/patterns").json() == []


def test_insights_endpoint_requires_login(client):
    """Insight Engine made per-account (2026-07-19, see engine/decisions.md
    "Insight Engine made per-account"): /insights now requires a
    signed-in caller, same as /patterns and /personal-operating-model --
    insights is no longer a global model an anonymous caller could
    safely see."""
    res = client.get("/insights")
    assert res.status_code == 401
    assert res.json()["detail"] == "login_required"


def test_insights_endpoint_never_returns_another_accounts_insights(client):
    """Insight Engine made per-account (2026-07-19, see engine/decisions.md
    "Insight Engine made per-account"): the direct regression test for
    the bug this round fixed -- a brand-new signed-in account must not
    inherit whatever themes were computed from a different account's
    own sessions."""
    other_user_id = db.get_or_create_user("someone-else-insights@example.com")
    db.replace_insights(
        other_user_id, [Insight(theme="Someone else's theme", detail="Not yours.", evidence_session_ids=[])]
    )

    _login(client, email="fresh-account-insights@example.com")
    assert client.get("/insights").json() == []


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
    the deployed app really will.

    Uses one shared `httpx.Client()` across all three calls (basic auth,
    see engine/decisions.md) rather than three one-off `httpx.post`/
    `httpx.stream` calls -- the first request mints this "browser"'s own
    anonymous-id cookie (src/api/server.py's `resolve_identity`), and
    every later call needs to carry that SAME cookie for the session it
    created to still be owned by whoever's asking; three independent,
    cookie-less requests would each look like a different anonymous
    visitor and 404 on ownership, same as three separate real browsers
    would."""
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
        with httpx.Client(base_url=base) as http_client:
            session_id = http_client.post("/sessions").json()["id"]

            received: list[str] = []
            connected = threading.Event()

            def _listen():
                with http_client.stream("GET", f"/sessions/{session_id}/stream", timeout=10) as response:
                    connected.set()
                    for line in response.iter_lines():
                        if line.startswith("data: "):
                            received.append(json.loads(line[len("data: "):])["stage"])
                        if len(received) >= 4:
                            break

            listener = threading.Thread(target=_listen, daemon=True)
            listener.start()
            assert connected.wait(timeout=2), "stream never connected"

            res = http_client.post(
                f"/sessions/{session_id}/messages", json={"content": "I want to move teams."}, timeout=10
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


# Privacy, made real (2026-07-18, see frontend/decisions.md).


def test_privacy_settings_default_to_cross_session_learning_enabled(client):
    _login(client)
    res = client.get("/privacy/settings")
    assert res.json() == {"cross_session_learning_enabled": True}


def test_privacy_settings_requires_login(client):
    """Direct regression test for the gate itself (basic auth, see
    engine/decisions.md "Auth, the low-friction way") -- an anonymous
    caller (no _login call here) must be turned away, not served the
    single global setting."""
    res = client.get("/privacy/settings")
    assert res.status_code == 401
    assert res.json()["detail"] == "login_required"


def test_privacy_settings_can_be_disabled_and_persist(client):
    _login(client)
    res = client.post("/privacy/settings", json={"cross_session_learning_enabled": False})
    assert res.json() == {"cross_session_learning_enabled": False}

    # A fresh GET, not just trusting the POST's own echoed response --
    # confirms it actually persisted to the DB rather than the endpoint
    # just reflecting back whatever the request body said.
    res = client.get("/privacy/settings")
    assert res.json() == {"cross_session_learning_enabled": False}


def test_send_message_omits_retrieved_context_when_cross_session_learning_disabled(client, monkeypatch):
    """Same fixture data as
    test_send_message_threads_retrieved_context_into_judgment_prompt
    above -- the only difference is the opt-out being set first. If this
    test passed without the opt-out actually gating anything, the
    positive-case test above would have caught it; this is the direct
    regression test for the gate itself."""
    seen = {}
    monkeypatch.setattr(
        "src.interpretation.engine.call_provider",
        _always_returns(_minimal_interp("User wants to move to the Product team.")),
    )
    monkeypatch.setattr(
        "src.judgment.engine.call_provider", _spy_call_provider(_MINIMAL_JUDGMENT, seen, "judgment")
    )
    monkeypatch.setattr(
        "src.planner.engine.call_provider", _always_returns(_MINIMAL_PLANNER)
    )
    monkeypatch.setattr(
        "src.response.engine.call_provider", _always_returns(_MINIMAL_RESPONSE)
    )
    email = _login(client)
    user_id = db.get_or_create_user(email)
    db.replace_learned_patterns(user_id, [
        Pattern(pattern_type="decision_reversal", detail="Often reopens closed decisions", evidence_count=3)
    ])
    db.replace_insights(user_id, [
        Insight(theme="Career anxiety", detail="Recurring worry about job security", evidence_session_ids=[])
    ])
    db.set_cross_session_learning_enabled(False)
    session_id = client.post("/sessions").json()["id"]

    client.post(f"/sessions/{session_id}/messages", json={"content": "I want to move teams."})

    _, judgment_messages = seen["judgment"]
    content = judgment_messages[0]["content"]
    assert "Often reopens closed decisions" not in content
    assert "Career anxiety" not in content


def test_privacy_export_includes_sessions_messages_and_readable_world_state(client, monkeypatch):
    monkeypatch.setattr(
        "src.interpretation.engine.call_provider",
        _always_returns(_minimal_interp("User wants to move to the Product team.")),
    )
    _login(client)
    session_id = client.post("/sessions").json()["id"]
    client.post(f"/sessions/{session_id}/messages", json={"content": "I want to move teams."})

    res = client.get("/privacy/export")
    assert res.headers["content-type"] == "application/json"
    assert "attachment" in res.headers["content-disposition"]
    payload = res.json()

    assert len(payload["sessions"]) == 1
    assert payload["sessions"][0]["id"] == session_id
    # world_state_json was a raw TEXT column -- confirms it's parsed
    # back into a real nested object here, not left as an escaped string.
    assert isinstance(payload["sessions"][0]["world_state"], dict)
    assert len(payload["messages"]) == 2  # the user turn + the assistant reply
    assert payload["learned_patterns"] == []  # never computed in this test
    assert payload["personal_operating_model"] is None  # never computed in this test


def test_privacy_reset_deletes_sessions_but_keeps_settings(client, monkeypatch):
    monkeypatch.setattr(
        "src.interpretation.engine.call_provider",
        _always_returns(_minimal_interp("User wants to move to the Product team.")),
    )
    email = _login(client)
    user_id = db.get_or_create_user(email)
    session_id = client.post("/sessions").json()["id"]
    client.post(f"/sessions/{session_id}/messages", json={"content": "I want to move teams."})
    db.replace_learned_patterns(user_id, [
        Pattern(pattern_type="decision_reversal", detail="Often reopens closed decisions", evidence_count=3)
    ])
    db.set_cross_session_learning_enabled(False)

    res = client.post("/privacy/reset")
    assert res.status_code == 204

    assert client.get("/sessions").json() == []
    # Learning made per-account (2026-07-18, see engine/decisions.md
    # "Learning made per-account"): learned_patterns now HAS real
    # per-account attribution, so "Forget everything" deletes this
    # account's own patterns too -- unlike before that fix, when the
    # table had no owner column at all and had to be left untouched.
    assert db.get_learned_patterns(user_id) == []
    # The person's own stated privacy preference survives a data reset --
    # resetting journal content isn't the same action as reverting a
    # setting they deliberately chose.
    assert db.get_cross_session_learning_enabled() is False


def test_privacy_export_never_includes_another_accounts_sessions(client, monkeypatch):
    """Direct regression test for the export/reset global-scope bug
    fixed this round (2026-07-18, see engine/decisions.md "POM made
    per-user") -- before this fix, ANY signed-in visitor's "Export your
    data" downloaded EVERY account's Journeys."""
    monkeypatch.setattr(
        "src.interpretation.engine.call_provider",
        _always_returns(_minimal_interp("User wants to move to the Product team.")),
    )
    _login(client, email="other-account@example.com")
    other_session_id = client.post("/sessions").json()["id"]
    client.post(f"/sessions/{other_session_id}/messages", json={"content": "Someone else's private message."})
    client.post("/auth/logout")

    _login(client, email="person@example.com")
    own_session_id = client.post("/sessions").json()["id"]
    client.post(f"/sessions/{own_session_id}/messages", json={"content": "My own message."})

    payload = client.get("/privacy/export").json()

    session_ids = {s["id"] for s in payload["sessions"]}
    assert session_ids == {own_session_id}
    assert other_session_id not in session_ids


def test_privacy_export_and_reset_scope_learned_patterns_to_one_account(client):
    """Learning made per-account (2026-07-18, see engine/decisions.md
    "Learning made per-account") -- direct regression test that export
    includes only this account's own learned_patterns, and reset
    deletes only this account's own rows, leaving another account's
    patterns untouched by either."""
    from src.learning.engine import Pattern

    other_user_id = db.get_or_create_user("other-patterns-account@example.com")
    db.replace_learned_patterns(
        other_user_id, [Pattern(pattern_type="decision_status_changed", detail="Someone else's pattern.", evidence_count=3)]
    )

    email = _login(client, email="own-patterns-account@example.com")
    user_id = db.get_or_create_user(email)
    db.replace_learned_patterns(
        user_id, [Pattern(pattern_type="decision_status_changed", detail="My own pattern.", evidence_count=3)]
    )

    payload = client.get("/privacy/export").json()
    assert [p["detail"] for p in payload["learned_patterns"]] == ["My own pattern."]

    assert client.post("/privacy/reset").status_code == 204
    assert db.get_learned_patterns(user_id) == []
    assert [p.detail for p in db.get_learned_patterns(other_user_id)] == ["Someone else's pattern."]


def test_privacy_export_and_reset_scope_insights_to_one_account(client):
    """Insight Engine made per-account (2026-07-19, see engine/decisions.md
    "Insight Engine made per-account") -- direct regression test that
    export includes only this account's own insights, and reset deletes
    only this account's own rows, leaving another account's insights
    untouched by either. Mirrors
    test_privacy_export_and_reset_scope_learned_patterns_to_one_account."""
    other_user_id = db.get_or_create_user("other-insights-account@example.com")
    db.replace_insights(
        other_user_id, [Insight(theme="Someone else's theme", detail="Someone else's insight.", evidence_session_ids=[])]
    )

    email = _login(client, email="own-insights-account@example.com")
    user_id = db.get_or_create_user(email)
    db.replace_insights(
        user_id, [Insight(theme="My own theme", detail="My own insight.", evidence_session_ids=[])]
    )

    payload = client.get("/privacy/export").json()
    assert [i["detail"] for i in payload["insights"]] == ["My own insight."]

    assert client.post("/privacy/reset").status_code == 204
    assert db.get_insights(user_id) == []
    assert [i.detail for i in db.get_insights(other_user_id)] == ["Someone else's insight."]


def test_privacy_reset_never_deletes_another_accounts_sessions(client, monkeypatch):
    """Direct regression test for the export/reset global-scope bug
    fixed this round (2026-07-18, see engine/decisions.md "POM made
    per-user") -- before this fix, ANY signed-in visitor's "Forget
    everything" deleted EVERY account's Journeys system-wide."""
    monkeypatch.setattr(
        "src.interpretation.engine.call_provider",
        _always_returns(_minimal_interp("User wants to move to the Product team.")),
    )
    _login(client, email="other-account@example.com")
    other_session_id = client.post("/sessions").json()["id"]
    client.post(f"/sessions/{other_session_id}/messages", json={"content": "Someone else's private message."})
    client.post("/auth/logout")

    _login(client, email="person@example.com")
    client.post("/sessions").json()["id"]

    res = client.post("/privacy/reset")
    assert res.status_code == 204

    assert client.get("/sessions").json() == []
    client.post("/auth/logout")
    _login(client, email="other-account@example.com")
    remaining = client.get("/sessions").json()
    assert {s["id"] for s in remaining} == {other_session_id}
