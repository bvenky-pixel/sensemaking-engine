"""
Tests for src/judgment/engine.py::run_judgment's grounding enforcement on
`supporting_evidence` (backlog #242, see engine/decisions.md "Judgment:
supporting_evidence migrated to KnowledgeItem id references"). call_provider
is mocked at src.judgment.engine's own import path, same pattern as
tests/test_insight.py/tests/test_tier2.py -- no real LLM calls.

compute_stagnation_signals/recommend_phase_transition (the other pure
helpers in this module) have their own dedicated test files
(tests/test_judgment_stagnation.py, tests/test_judgment_phase_transition.py)
and are not repeated here.
"""

from __future__ import annotations

import json

from src.judgment.engine import run_judgment
from src.state.world_state import Fact, Provenance, WorldState

_BASE_JUDGMENT = {
    "primary_problem": "Transfer to Product team is stalled without explanation.",
    "primary_goal": "Move to the Product team.",
    "current_focus": "Understanding why Sarah keeps deferring.",
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


def _always_returns(payload):
    def _call(provider_name, system_prompt, messages, schema, temperature, component="unknown", tracker=None):
        return json.dumps(payload)
    return _call


def test_supporting_evidence_keeps_real_knowledge_item_ids(monkeypatch):
    state = WorldState()
    state.facts.append(Fact(
        content="User has a manager named Sarah.",
        provenance=Provenance(source="interpretation", first_seen=1, last_updated=1),
    ))
    real_id = state.facts[0].id

    monkeypatch.setattr(
        "src.judgment.engine.call_provider",
        _always_returns({**_BASE_JUDGMENT, "supporting_evidence": [real_id]}),
    )

    judgment = run_judgment(state)

    assert judgment.supporting_evidence == [real_id]


def test_supporting_evidence_drops_a_hallucinated_id(monkeypatch):
    """The direct regression test for grounding enforcement: an id the
    model invented (never actually part of this WorldState) must never
    survive into the returned Judgment -- same "never trust the model's
    own ids uncritically" discipline as src/insight/engine.py's/
    src/understanding/tier2_engine.py's own grounding filters."""
    state = WorldState()
    state.facts.append(Fact(
        content="User has a manager named Sarah.",
        provenance=Provenance(source="interpretation", first_seen=1, last_updated=1),
    ))
    real_id = state.facts[0].id

    monkeypatch.setattr(
        "src.judgment.engine.call_provider",
        _always_returns({
            **_BASE_JUDGMENT,
            "supporting_evidence": [real_id, "hallucinated-id-not-in-worldstate"],
        }),
    )

    judgment = run_judgment(state)

    assert judgment.supporting_evidence == [real_id]
