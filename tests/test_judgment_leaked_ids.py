"""
Tests for src/judgment/engine.py::strip_leaked_ids -- the mechanical
backstop against Judgment echoing raw WorldState item ids back into its
own free-text/list fields. Added 2026-07-22 (direct founder bug report
from manual production testing): a live Clarity Brief showed ids leaking
in a shape neither this codebase's existing anti-id-leak law nor
Planner's own strip_leaked_ids (src/planner/engine.py) covered --
labeled by WorldState item TYPE NAME ("fact:", "claims:"), not just
"id:", and with multiple comma-separated ids under one label. Same
"prompt alone isn't enough, back it with a mechanical backstop"
discipline as every other instance of this pattern in this codebase.
"""

from __future__ import annotations

import json

from src.judgment.engine import _strip_leaked_id, run_judgment, strip_leaked_ids
from src.judgment.schema import Judgment
from src.state.world_state import WorldState

_BASE_JUDGMENT = {
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
    "confidence": 0.4,
}


def _judgment(**overrides) -> Judgment:
    return Judgment(**{**_BASE_JUDGMENT, **overrides})


def test_strip_leaked_id_removes_a_real_observed_single_id_labeled_fact():
    """Regression test for a real, live-observed leak (2026-07-22): the
    label is the WorldState item's own TYPE NAME ("fact"), not "id"."""
    text = (
        "The new boss's lack of communication (fact: "
        "4be1114f-3e51-47c7-b5c0-51b7600ed0d1) could lead to you losing relevance"
    )
    assert _strip_leaked_id(text) == (
        "The new boss's lack of communication could lead to you losing relevance"
    )


def test_strip_leaked_id_removes_multiple_comma_separated_ids():
    """Regression test for a real, live-observed leak (2026-07-22): a
    single parenthetical can carry more than one comma-separated id
    under a pluralized label ("claims:")."""
    text = (
        "could lead to you losing relevance and their job (claims: "
        "b523627e-c0d6-4f3d-832c-d62f1640ad1e, "
        "2766f7c7-f0a4-46ad-b37c-56064afaff04) due to a failure to align"
    )
    cleaned = _strip_leaked_id(text)
    assert "b523627e" not in cleaned
    assert "2766f7c7" not in cleaned
    assert "claims:" not in cleaned


def test_strip_leaked_id_still_handles_the_original_id_label_shape():
    text = "Has the user asked for a clear reason directly? (id: 2037e579-7562-42b6-a0f1-9ce6c8e384a4)"
    assert _strip_leaked_id(text) == "Has the user asked for a clear reason directly?"


def test_strip_leaked_ids_covers_open_unknowns():
    """Regression test for the real, live-observed leak location: the
    "Still uncertain" Clarity Brief section (Judgment.open_unknowns)."""
    judgment = _judgment(open_unknowns=[
        "What is the nature of the vision and goals? (id: 520eb13f-3890-4f5d-bcf7-077438d231b3)",
    ])

    cleaned = strip_leaked_ids(judgment)

    assert cleaned.open_unknowns == ["What is the nature of the vision and goals?"]


def test_strip_leaked_ids_covers_key_insights_source_fields():
    """Regression test for the real, live-observed leak location: the
    "What matters here" Clarity Brief section (Judgment.primary_problem +
    risks + opportunities)."""
    judgment = _judgment(
        primary_problem="The new boss's lack of communication (fact: 4be1114f-3e51-47c7-b5c0-51b7600ed0d1) is the core issue.",
        has_risk_signal=True,
        risks=[
            "could lead to you losing relevance and their job (claims: "
            "b523627e-c0d6-4f3d-832c-d62f1640ad1e, 2766f7c7-f0a4-46ad-b37c-56064afaff04)"
        ],
        opportunities=["A new manager could sponsor it (fact: 882c7638-9b2f-405d-908c-2241f20c31e0)"],
    )

    cleaned = strip_leaked_ids(judgment)

    assert "4be1114f" not in cleaned.primary_problem
    assert "b523627e" not in cleaned.risks[0]
    assert "882c7638" not in cleaned.opportunities[0]


def test_strip_leaked_ids_does_not_touch_exact_quote_fields():
    """knowledge_correction_target and decision_resolution_option must
    stay byte-identical to real WorldState text by their own contract --
    even in the (extremely unlikely) case one contained an id-shaped
    substring, stripping it would break the "exact quote" guarantee
    src/state/builder.py depends on to find the matching WorldState item."""
    judgment = _judgment(
        has_knowledge_correction=True,
        knowledge_correction_target="User's note (id: 11111111-1111-1111-1111-111111111111) about the freeze.",
        knowledge_correction_kind="retracted",
        has_decision_resolution=True,
        decision_resolution_option="Wait until Q3 (id: 22222222-2222-2222-2222-222222222222)",
        decision_resolution_status="resolved",
    )

    cleaned = strip_leaked_ids(judgment)

    assert cleaned.knowledge_correction_target == judgment.knowledge_correction_target
    assert cleaned.decision_resolution_option == judgment.decision_resolution_option


def test_strip_leaked_ids_does_not_touch_supporting_evidence():
    """supporting_evidence is the one field ids are SUPPOSED to live in."""
    judgment = _judgment(supporting_evidence=["fact:abc123"])
    cleaned = strip_leaked_ids(judgment)
    assert cleaned.supporting_evidence == judgment.supporting_evidence


def _always_returns(payload):
    def _call(provider_name, system_prompt, messages, schema, temperature, component="unknown", tracker=None):
        return json.dumps(payload)
    return _call


def test_run_judgment_strips_a_leaked_id_end_to_end(monkeypatch):
    monkeypatch.setattr(
        "src.judgment.engine.call_provider",
        _always_returns({
            **_BASE_JUDGMENT,
            "open_unknowns": [
                "What specific communication issues are occurring? (id: def180ec-6098-4328-bc56-c1b69532e0fd)",
            ],
        }),
    )

    judgment = run_judgment(WorldState())

    assert judgment.open_unknowns == ["What specific communication issues are occurring?"]
