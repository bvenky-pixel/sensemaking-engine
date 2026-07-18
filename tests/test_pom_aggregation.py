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
    session_id = db.create_session()
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

    claims, assumptions, entities, aggregated_content = db.get_aggregated_knowledge_for_pom()

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
    session_a = db.create_session()
    session_b = db.create_session()
    db.save_world_state_for_backfill(session_a, WorldState(claims=[Claim(content="Belief from session A.")]))
    db.save_world_state_for_backfill(session_b, WorldState(claims=[Claim(content="Belief from session B.")]))

    claims, _, _, _ = db.get_aggregated_knowledge_for_pom()

    assert "Belief from session A." in claims
    assert "Belief from session B." in claims


def test_get_aggregated_knowledge_for_pom_empty_when_no_sessions_exist(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db(tmp_path / "test.db")

    claims, assumptions, entities, aggregated_content = db.get_aggregated_knowledge_for_pom()

    assert claims == []
    assert assumptions == []
    assert entities == []
    assert aggregated_content == ""
