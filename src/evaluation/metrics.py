"""
Quantitative, automatically-derivable metrics for the Judgment v2
evaluation smoke test -- per explicit scope decision, this round skips
the design's blind human ranking / LLM-judge protocol
(engine/specs/judgment-v2-evaluation-design.md Sec. 5-6) and only
computes signals a script can derive on its own.

Two of these (`groundedness_heuristic`, `constraint_violation_heuristic`)
are approximate PROXIES for design-doc dimensions that the real
methodology scores with human/LLM judges -- they are heuristics, not the
real thing, and are labeled as such wherever they're reported:

- `groundedness_heuristic`: reuses the same word-overlap technique already
  calibrated elsewhere in this codebase (src/state/builder.py's unknown-
  resolution matcher, itself adapted from src/interpretation/engine.py's
  grounding filters) to check whether each `supporting_evidence` string
  shares enough vocabulary with the condition's own source text to be
  plausibly grounded in it. A low overlap score is a signal worth a human
  looking at, not proof of hallucination -- word overlap can't tell a
  faithful paraphrase from a fabrication, only flag vocabulary that
  doesn't appear in the source at all.
- `constraint_violation_heuristic`: a keyword scan for coaching/advice-
  giving phrasing in the Judgment's free-text fields, as a cheap proxy
  for the design doc's constraint-adherence dimension. A real violation
  check needs a human or LLM judge reading for intent, not just phrasing
  -- this only catches the most literal violations.

Everything else here (`structural_summary`) is a plain, non-heuristic
count -- no proxy, no judgment call.
"""

from __future__ import annotations

import re
from typing import Dict, List

from src.judgment.schema import Judgment

_WORD_RE = re.compile(r"[a-z']+")

GROUNDEDNESS_OVERLAP_THRESHOLD = 0.5

_VIOLATION_PATTERNS = [
    r"\byou should\b",
    r"\byou need to\b",
    r"\bi recommend\b",
    r"\bi suggest\b",
    r"\btry to\b",
    r"\bconsider (doing|trying)\b",
    r"\bit (would|might) help to\b",
    r"\?\s*$",  # a trailing question mark anywhere a MUST-NOT field ends in one
]
_VIOLATION_RE = re.compile("|".join(_VIOLATION_PATTERNS), re.IGNORECASE)


def _word_set(text: str) -> set:
    return set(_WORD_RE.findall(text.lower()))


def _overlap(evidence: str, source: str) -> float:
    evidence_words = _word_set(evidence)
    if not evidence_words:
        return 0.0
    return len(evidence_words & _word_set(source)) / len(evidence_words)


def groundedness_heuristic(judgment: Judgment, source_text: str) -> Dict:
    """% of supporting_evidence entries whose word-overlap against
    source_text meets GROUNDEDNESS_OVERLAP_THRESHOLD -- see module
    docstring for why this is a heuristic proxy, not a real groundedness
    check."""
    entries = judgment.supporting_evidence
    if not entries:
        return {"entries": 0, "plausibly_grounded": 0, "rate": None}

    scores = [_overlap(entry, source_text) for entry in entries]
    grounded = sum(1 for s in scores if s >= GROUNDEDNESS_OVERLAP_THRESHOLD)
    return {
        "entries": len(entries),
        "plausibly_grounded": grounded,
        "rate": grounded / len(entries),
        "scores": scores,
    }


def _free_text_fields(judgment: Judgment) -> List[str]:
    return [
        judgment.primary_problem,
        judgment.primary_goal,
        judgment.current_focus,
        *judgment.key_blockers,
        *judgment.risks,
        *judgment.opportunities,
    ]


def constraint_violation_heuristic(judgment: Judgment) -> Dict:
    """Keyword scan across the Judgment's free-text fields for literal
    coaching/advice/question phrasing -- see module docstring."""
    hits = []
    for field_value in _free_text_fields(judgment):
        if field_value and _VIOLATION_RE.search(field_value):
            hits.append(field_value)
    return {"fields_checked": len(_free_text_fields(judgment)), "flagged": len(hits), "examples": hits}


def structural_summary(judgment: Judgment) -> Dict:
    """Plain counts -- no heuristic, no judgment call."""
    return {
        "key_blockers": len(judgment.key_blockers),
        "open_unknowns": len(judgment.open_unknowns),
        "active_decisions": len(judgment.active_decisions),
        "contradictions": len(judgment.contradictions),
        "risks": len(judgment.risks),
        "opportunities": len(judgment.opportunities),
        "supporting_evidence": len(judgment.supporting_evidence),
        "confidence": judgment.confidence,
        "primary_problem_empty": judgment.primary_problem == "",
        "primary_goal_empty": judgment.primary_goal == "",
    }


def compute_all(judgment: Judgment, source_text: str) -> Dict:
    return {
        "structural": structural_summary(judgment),
        "groundedness_heuristic": groundedness_heuristic(judgment, source_text),
        "constraint_violation_heuristic": constraint_violation_heuristic(judgment),
    }
