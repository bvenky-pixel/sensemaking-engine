"""
Tests for Judgment.competing_priorities (2026-07-22, see
engine/decisions.md and engine/specs/clarity-brief-specification-v1.md
section 5). List[str], defaulted, no boolean-gate -- same "no gate
without evidence of a transcription-compliance failure" discipline as
secondary_issues/stagnation_notes, so these are simple schema round-trips
plus prompt-presence/distinction checks, matching
test_judgment_v3_fields.py's own style for the same class of field.
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


def test_competing_priorities_defaults_to_empty_list():
    judgment = Judgment(**_REQUIRED_FIELDS)
    assert judgment.competing_priorities == []


def test_competing_priorities_accepts_populated_list():
    judgment = Judgment(
        **_REQUIRED_FIELDS,
        competing_priorities=[
            "Pushing harder for the Product team move risks straining "
            "the relationship with Sarah that the user also wants to "
            "protect."
        ],
    )
    assert judgment.competing_priorities == [
        "Pushing harder for the Product team move risks straining "
        "the relationship with Sarah that the user also wants to "
        "protect."
    ]


def test_prompt_defines_competing_priorities():
    assert "- competing_priorities:" in SYSTEM_PROMPT


def test_prompt_distinguishes_competing_priorities_from_contradictions_and_secondary_issues():
    assert "not a contradiction (both sides here CAN be true at" in SYSTEM_PROMPT
    assert "not a lone secondary issue" in SYSTEM_PROMPT
