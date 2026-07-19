"""
Tests for the four Judgment v3 design-pass fields (2026-07-19, backlog
#228, see engine/decisions.md "Judgment v3 design pass"): situation_assessment,
contradiction_significance, risk_significance, decision_readiness. All
four are plain, defaulted (`= ""`) string fields with no boolean-gate/
auto-repair -- same "no gate without evidence of a transcription-
compliance failure" discipline as secondary_issues/stagnation_notes, so
these tests are simple schema round-trips plus prompt-presence checks,
not repair-validator tests.
"""

from __future__ import annotations

from src.judgment.prompt import SYSTEM_PROMPT
from src.judgment.schema import Judgment

_REQUIRED_FIELDS = dict(
    primary_problem="",
    primary_goal="",
    current_focus="",
    has_knowledge_correction=False,
    knowledge_correction_target="",
    knowledge_correction_kind="",
    knowledge_correction_corrected_content="",
    has_risk_signal=False,
    risk_scan="No risk-worthy signal identified.",
    has_decision_resolution=False,
    decision_resolution_option="",
    decision_resolution_status="",
    confidence=0.5,
)


def test_new_v3_fields_default_to_empty_string():
    judgment = Judgment(**_REQUIRED_FIELDS)
    assert judgment.situation_assessment == ""
    assert judgment.contradiction_significance == ""
    assert judgment.risk_significance == ""
    assert judgment.decision_readiness == ""


def test_new_v3_fields_accept_populated_values():
    judgment = Judgment(
        **_REQUIRED_FIELDS,
        situation_assessment="A stalled internal career transition.",
        contradiction_significance="Career advancement appears blocked despite positive performance signals.",
        risk_significance="Financial uncertainty appears to be a significant constraint on decision making.",
        decision_readiness="Actively comparing both offers.",
    )
    assert judgment.situation_assessment == "A stalled internal career transition."
    assert judgment.contradiction_significance == (
        "Career advancement appears blocked despite positive performance signals."
    )
    assert judgment.risk_significance == (
        "Financial uncertainty appears to be a significant constraint on decision making."
    )
    assert judgment.decision_readiness == "Actively comparing both offers."


def test_prompt_defines_all_four_new_fields():
    for field in (
        "situation_assessment", "contradiction_significance", "risk_significance", "decision_readiness",
    ):
        assert f"- {field}:" in SYSTEM_PROMPT


def test_prompt_distinguishes_situation_assessment_from_adjacent_fields():
    assert "the overarching frame, not a third" in SYSTEM_PROMPT
    assert "primary_problem (the specific blocking issue)" in SYSTEM_PROMPT


def test_prompt_warns_against_restating_contradictions_in_significance():
    assert "that's just contradictions' own" in SYSTEM_PROMPT


def test_prompt_forbids_decision_readiness_from_recommending_an_option():
    assert "NEVER a recommendation of which option to choose" in SYSTEM_PROMPT


def test_prompt_places_new_fields_in_second_assessment_layer():
    assert "SECOND layer built on top of those first-layer" in SYSTEM_PROMPT
