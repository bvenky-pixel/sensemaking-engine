"""
Tests for the Judgment v2 evaluation smoke-test harness
(src/evaluation/*) -- deterministic, no real LLM calls. Mocks
`call_provider` at each call site (src.interpretation.engine,
src.judgment.engine, src.evaluation.baselines) to return canned JSON,
so these tests verify the harness's own plumbing (prompt construction,
condition wiring, per-condition source_text, metrics computation) rather
than model output quality -- that's what the real smoke-test run (real
API calls, see scripts/run_judgment_evaluation_smoketest.py) is for.
"""

from __future__ import annotations

import json

import pytest

from src.evaluation.baselines import _adapt_judgment_prompt, run_baseline_a, run_baseline_b2
from src.evaluation.confidant_runner import run_confidant
from src.evaluation.metrics import (
    compute_all,
    constraint_violation_heuristic,
    groundedness_heuristic,
    structural_summary,
)
from src.instrumentation.usage import UsageTracker
from src.judgment.schema import Judgment

TRANSCRIPT = [
    "I've been trying to move to the Product team for months.",
    "My manager Sarah keeps deferring without a clear reason.",
]

_MINIMAL_INTERPRETATION = {
    "urgency": "low",
    "impact_domains": ["professional"],
    "emotional_signals": [],
    "surface_complaint": "Wants a team transfer that keeps getting deferred.",
    "core_question": "Why is the transfer being delayed?",
    "core_question_confidence": 0.4,
    "observed_facts": ["User wants to move to the Product team."],
    "claims": [],
    "goals": ["Move to the Product team."],
    "decision_options": [],
    "has_assumption": False,
    "assumption_check": "No framing-embedded assumption detected.",
    "assumptions": [],
    "inferences": [],
    "unknowns": ["Why Sarah keeps deferring the transfer."],
    "biases": [],
    "entities": ["Sarah"],
    "clarity_score": 0.5,
    "requires_clarification": False,
}

_MINIMAL_JUDGMENT = {
    "primary_problem": "Transfer to Product team is stalled without explanation.",
    "primary_goal": "Move to the Product team.",
    "current_focus": "Understanding why Sarah keeps deferring.",
    "key_blockers": ["Sarah has not given a clear reason."],
    "open_unknowns": ["Why Sarah keeps deferring the transfer."],
    "active_decisions": [],
    "contradictions": [],
    "has_risk_signal": True,
    "risk_scan": "The lack of a stated reason for the delay is itself risk-worthy.",
    "risks": ["The transfer may never happen without a clear reason."],
    "opportunities": [],
    "confidence": 0.4,
    "supporting_evidence": ["User wants to move to the Product team.", "Sarah keeps deferring without a clear reason."],
}


def _canned_provider(return_value):
    def _call(provider_name, system_prompt, messages, schema, temperature, component="unknown", tracker=None):
        return json.dumps(return_value)

    return _call


def test_adapt_judgment_prompt_has_no_worldstate_leaks_or_doubled_words():
    prompt = _adapt_judgment_prompt(
        "You are given the full raw conversation transcript.",
        "given this transcript, what conclusions are justified?",
        "transcript",
    )
    assert "WorldState" not in prompt
    assert "the the" not in prompt
    assert "in in" not in prompt
    assert "JUDGMENT MUST NOT" in prompt  # governance section preserved verbatim


def test_run_baseline_a_returns_judgment_and_transcript_source(monkeypatch):
    monkeypatch.setattr(
        "src.evaluation.baselines.call_provider", _canned_provider(_MINIMAL_JUDGMENT)
    )
    tracker = UsageTracker()
    judgment, source_text = run_baseline_a(TRANSCRIPT, tracker=tracker)

    assert isinstance(judgment, Judgment)
    assert judgment.primary_goal == "Move to the Product team."
    assert "Sarah" in source_text
    assert "Turn 1" in source_text and "Turn 2" in source_text


def test_run_baseline_b2_updates_summary_then_judges_it(monkeypatch):
    calls = []

    def _call(provider_name, system_prompt, messages, schema, temperature, component="unknown", tracker=None):
        calls.append(component)
        if component == "Baseline-B2-summary":
            return json.dumps({"summary": "User wants a transfer; Sarah keeps deferring."})
        return json.dumps(_MINIMAL_JUDGMENT)

    monkeypatch.setattr("src.evaluation.baselines.call_provider", _call)
    tracker = UsageTracker()
    judgment, source_text = run_baseline_b2(TRANSCRIPT, tracker=tracker)

    assert isinstance(judgment, Judgment)
    assert source_text == "User wants a transfer; Sarah keeps deferring."
    # one summary-update call per turn, plus one final judgment call
    assert calls.count("Baseline-B2-summary") == len(TRANSCRIPT)
    assert calls.count("Baseline-B2-judgment") == 1


def test_run_confidant_runs_pipeline_then_judges_final_worldstate(monkeypatch):
    monkeypatch.setattr(
        "src.interpretation.engine.call_provider", _canned_provider(_MINIMAL_INTERPRETATION)
    )
    monkeypatch.setattr(
        "src.judgment.engine.call_provider", _canned_provider(_MINIMAL_JUDGMENT)
    )
    tracker = UsageTracker()
    judgment, source_text = run_confidant(TRANSCRIPT, tracker=tracker)

    assert isinstance(judgment, Judgment)
    assert judgment.primary_goal == "Move to the Product team."
    # source_text is the final WorldState JSON -- should contain accumulated content
    parsed = json.loads(source_text)
    assert "Sarah" in [e["name"] for e in parsed["entities"]]


def test_metrics_groundedness_heuristic_flags_ungrounded_evidence():
    judgment = Judgment(**{**_MINIMAL_JUDGMENT, "supporting_evidence": ["The moon landing was faked."]})
    result = groundedness_heuristic(judgment, "User wants to move to the Product team. Sarah keeps deferring.")
    assert result["entries"] == 1
    assert result["plausibly_grounded"] == 0
    assert result["rate"] == 0.0


def test_metrics_groundedness_heuristic_passes_grounded_evidence():
    judgment = Judgment(**_MINIMAL_JUDGMENT)
    source = "User wants to move to the Product team. Sarah keeps deferring without a clear reason."
    result = groundedness_heuristic(judgment, source)
    assert result["rate"] > 0.0


def test_metrics_constraint_violation_heuristic_flags_advice_language():
    judgment = Judgment(**{**_MINIMAL_JUDGMENT, "risks": ["You should talk to Sarah directly."]})
    result = constraint_violation_heuristic(judgment)
    assert result["flagged"] >= 1


def test_metrics_constraint_violation_heuristic_clean_on_neutral_language():
    judgment = Judgment(**_MINIMAL_JUDGMENT)
    result = constraint_violation_heuristic(judgment)
    assert result["flagged"] == 0


def test_metrics_structural_summary_counts_match_fields():
    judgment = Judgment(**_MINIMAL_JUDGMENT)
    summary = structural_summary(judgment)
    assert summary["key_blockers"] == 1
    assert summary["supporting_evidence"] == 2
    assert summary["primary_problem_empty"] is False


def test_compute_all_returns_all_three_sections():
    judgment = Judgment(**_MINIMAL_JUDGMENT)
    result = compute_all(judgment, "some source text")
    assert set(result.keys()) == {"structural", "groundedness_heuristic", "constraint_violation_heuristic"}
