"""
Tests for src/api/db.py::get_aggregated_knowledge_for_pom -- the one
piece of Personal Operating Model wiring that reads real WorldState
objects field-by-field to build POM's aggregated input (see
engine/decisions.md "Personal Operating Model"). Regression coverage for
a real bug the live gpt-4o walkthrough dispatch caught: `EmotionalSignalItem`
has no `.content` field (`emotion`/`intensity`/`source`/`status`
instead), and nothing in the mocked test suite had ever actually
exercised this function against a WorldState containing one -- every
other POM test operates on already-aggregated inputs, not on this
aggregation step itself.
"""

from __future__ import annotations

from src.api import db
from src.pom.schema import MAX_SESSIONS_FOR_POM
from src.state.world_state import (
    Claim,
    Decision,
    EmotionalSignalItem,
    Entity,
    EntityAttribute,
    Fact,
    Goal,
    WorldState,
)


def test_get_aggregated_knowledge_for_pom_handles_a_real_emotional_signal_item(tmp_path, monkeypatch):
    """Regression test for the bug the live walkthrough caught: this
    must not raise AttributeError on a WorldState containing a real
    EmotionalSignalItem."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db(tmp_path / "test.db")
    session_id = db.create_session(user_id="user-1")
    state = WorldState(
        facts=[Fact(content="User is weighing a job offer.")],
        claims=[Claim(content="User believes the market is competitive.")],
        goals=[Goal(content="Move to the Product team.")],
        decisions=[Decision(content="Take the offer.")],
        entities=[Entity(
            name="Sarah", attributes=[EntityAttribute(attribute="role", value="manager")],
            relationships=["has final say on transfers"],
        )],
        emotional_signal_items=[EmotionalSignalItem(emotion="stress", intensity=0.7, source="explicit")],
    )
    db.save_world_state_for_backfill(session_id, state)

    claims, assumptions, entities, aggregated_content = db.get_aggregated_knowledge_for_pom("user-1")

    assert claims == ["User believes the market is competitive."]
    assert len(entities) == 1
    assert "Fact: User is weighing a job offer." in aggregated_content
    assert "Goal: Move to the Product team." in aggregated_content
    assert "Decision: Take the offer." in aggregated_content
    assert "Entity: Sarah" in aggregated_content
    assert "Emotional signal: stress (intensity=0.7, source=explicit)" in aggregated_content


def test_get_aggregated_knowledge_for_pom_aggregates_across_multiple_sessions(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db(tmp_path / "test.db")
    session_a = db.create_session(user_id="user-1")
    session_b = db.create_session(user_id="user-1")
    db.save_world_state_for_backfill(session_a, WorldState(claims=[Claim(content="Belief from session A.")]))
    db.save_world_state_for_backfill(session_b, WorldState(claims=[Claim(content="Belief from session B.")]))

    claims, _, _, _ = db.get_aggregated_knowledge_for_pom("user-1")

    assert "Belief from session A." in claims
    assert "Belief from session B." in claims


def test_get_aggregated_knowledge_for_pom_empty_when_no_sessions_exist(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db(tmp_path / "test.db")

    claims, assumptions, entities, aggregated_content = db.get_aggregated_knowledge_for_pom("user-1")

    assert claims == []
    assert assumptions == []
    assert entities == []
    assert aggregated_content == ""


def test_get_aggregated_knowledge_for_pom_includes_journey_reflections(tmp_path, monkeypatch):
    """Journey-close reflection question (2026-07-19, backlog #207) --
    a submitted reflection is folded into aggregated_content as its own
    labeled line, same "surface everything already known" treatment as
    every other content type here."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db(tmp_path / "test.db")
    session_a = db.create_session(user_id="user-1")
    db.save_world_state_for_backfill(session_a, WorldState(claims=[Claim(content="Belief from session A.")]))
    db.save_journey_reflection(session_a, "user-1", "This conversation made me realize I've been avoiding this.")

    _, _, _, aggregated_content = db.get_aggregated_knowledge_for_pom("user-1")

    assert "Reflection: This conversation made me realize I've been avoiding this." in aggregated_content


def test_get_aggregated_knowledge_for_pom_includes_pom_field_feedback(tmp_path, monkeypatch):
    """Light affirm/correct affordance (2026-07-19, backlog #209) -- both
    an affirmation and a correction get folded into aggregated_content
    as their own plain-language evidence lines."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db(tmp_path / "test.db")
    db.save_pom_feedback("user-1", "identity", "Values independence at work.", "affirm")
    db.save_pom_feedback("user-1", "stress", "You seem stretched thin.", "correct", "Things have calmed down.")

    _, _, _, aggregated_content = db.get_aggregated_knowledge_for_pom("user-1")

    assert "User confirmed this is accurate about themselves (identity): Values independence at work." in aggregated_content
    assert "User said this was inaccurate about themselves (stress) and clarified: Things have calmed down." in aggregated_content


def test_get_aggregated_knowledge_for_pom_excludes_other_accounts_sessions(tmp_path, monkeypatch):
    """POM made per-user (2026-07-18, see engine/decisions.md "POM made
    per-user"): the direct regression test for the bug this round
    fixed -- a brand-new account must never inherit another account's
    aggregated knowledge just because sessions exist in the same DB."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db(tmp_path / "test.db")
    session_a = db.create_session(user_id="user-1")
    session_b = db.create_session(user_id="user-2")
    db.save_world_state_for_backfill(session_a, WorldState(claims=[Claim(content="Belief from user-1.")]))
    db.save_world_state_for_backfill(session_b, WorldState(claims=[Claim(content="Belief from user-2.")]))

    claims_1, _, _, _ = db.get_aggregated_knowledge_for_pom("user-1")
    claims_2, _, _, _ = db.get_aggregated_knowledge_for_pom("user-2")

    assert claims_1 == ["Belief from user-1."]
    assert claims_2 == ["Belief from user-2."]


def test_get_aggregated_knowledge_for_pom_caps_at_most_recently_updated_sessions(tmp_path, monkeypatch):
    """Recency cap (2026-07-19, backlog #272, see engine/decisions.md
    "POM: recency cap added to aggregation") -- the founder's own
    explicit choice, overriding this codebase's original "POM is an
    all-history model, uncapped" reasoning. One session beyond
    MAX_SESSIONS_FOR_POM, given the OLDEST updated_at of the bunch, must
    be excluded -- direct regression test for the cap actually limiting
    which sessions get aggregated, same "cap actually bites" coverage
    get_session_texts_for_insights' own MAX_SESSIONS_FOR_INSIGHT cap
    established."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db(tmp_path / "test.db")

    # One extra session, given the earliest updated_at of the group so
    # it's the one the cap should exclude.
    for i in range(MAX_SESSIONS_FOR_POM + 1):
        session_id = db.create_session(user_id="user-1")
        claim_text = "Oldest session, should be capped out." if i == 0 else f"Claim from session {i}."
        state = WorldState(claims=[Claim(content=claim_text)])
        with db._connect() as conn:
            conn.execute(
                "UPDATE sessions SET world_state_json = ?, updated_at = ? WHERE id = ?",
                (state.model_dump_json(), f"2020-01-{i + 1:02d}T00:00:00", session_id),
            )

    claims, _, _, _ = db.get_aggregated_knowledge_for_pom("user-1")

    assert len(claims) == MAX_SESSIONS_FOR_POM
    assert "Oldest session, should be capped out." not in claims
