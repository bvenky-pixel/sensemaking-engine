"""
Retrieval v1 -- the vision doc's Layer 8 (see
engine/specs/architecture-roadmap-v1.md), scoped honestly narrow: NOT
need-aware selective retrieval. The vision doc's own description
("Retrieval is need-aware" -- Decision Retrieval, Accountability
Retrieval, Reflection Retrieval, each pulling different context per the
inferred need) depends on Layer 7 Need State Inference, which doesn't
exist in this codebase yet. Building selective retrieval logic ahead of
that would mean inventing a relevance model with no evidence behind it
-- exactly the mistake this codebase has refused to make everywhere
else (see Learning's own MIN_EVIDENCE discipline, Planner's "resist
tuning until real samples exist").

What this DOES do: surface everything Learning (src/learning/engine.py)
and Insight Engine (src/insight/engine.py) have already, offline,
evidence-gated computed about this person, unfiltered. Correct at this
project's single-user MVP scale, where "everything currently known" is
still a handful of short entries. Revisit once either real usage volume
grows enough that unfiltered surfacing stops being cheap, or Need State
Inference exists to make genuinely selective retrieval possible.

Feeds Judgment only (see src/judgment/prompt.py's "Retrieved Context"
section) -- the vision doc's own pipeline has Judgement as the first
layer downstream of Retrieval, and Judgment already owns synthesizing
"what's true" (WorldState) into "what it means." Cross-session patterns/
themes are additional input to that synthesis, not a new pipeline stage
with its own independent LLM reasoning -- no new LLM call here, this
module is a pure formatting function, same "mechanical, not a call"
category as src/judgment/engine.py::compute_stagnation_signals.
"""

from __future__ import annotations

from typing import List

from src.insight.schema import Insight
from src.learning.engine import Pattern


def build_retrieved_context(patterns: List[Pattern], insights: List[Insight]) -> str:
    """
    Formats already-computed Patterns/Insights into a plain-text block
    for Judgment's prompt. Pure function, no I/O -- callers (see
    src/api/server.py::send_message) are responsible for actually
    reading src/api/db.py's `get_learned_patterns`/`get_insights` and
    converting each row into a Pattern/Insight first; this module has no
    database dependency of its own, matching every other engine
    package's separation from src/api.

    Empty inputs produce "" -- a brand-new Journey, or a single-user
    history with nothing learned yet, must not see an empty-but-present
    "Retrieved Context" section, matching every other optional-input
    contract already established (e.g. src/orchestrator/modes.py's own
    mode_focus_note returning "" rather than a hollow labeled section).
    """
    if not patterns and not insights:
        return ""

    lines: List[str] = []
    if patterns:
        lines.append("Known behavioral patterns (from past Journeys):")
        for p in patterns:
            lines.append(f"- [{p.pattern_type}] {p.detail} (evidence_count={p.evidence_count})")
    if insights:
        lines.append("Recurring cross-session themes (from past Journeys):")
        for i in insights:
            lines.append(f"- {i.theme}: {i.detail}")
    return "\n".join(lines)
