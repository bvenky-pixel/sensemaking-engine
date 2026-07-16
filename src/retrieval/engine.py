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

Need State Inference (2026-07-16, see engine/decisions.md "Need State
Inference", src/need_state/engine.py): now that Layer 7 exists,
`build_retrieved_context` accepts the inferred NeedState too --
LABEL-ONLY, not filtering. Patterns/insights stay exactly as unfiltered
as they were before Need State Inference existed; the inferred need is
surfaced as an explicit, visible line so Judgment can weigh the
(still-complete) evidence knowing what this turn actually needs, rather
than Retrieval silently hiding a pattern based on an unvalidated
text-relevance match against free-text pattern_type/theme fields (the
"actually filter" alternative considered and rejected -- see
engine/decisions.md for the full fork).
"""

from __future__ import annotations

from typing import List, Optional

from src.insight.schema import Insight
from src.learning.engine import Pattern
from src.need_state.schema import NeedState

# Plain-language framing per need -- injected as the Retrieved Context
# label so Judgment sees WHY this need was inferred, not just its bare
# id. No "general" entry: general conveys nothing actionable, so it's
# deliberately omitted from the prompt entirely rather than surfaced as
# a hollow label (same "omit rather than show an empty signal"
# discipline as src/orchestrator/modes.py's own focus notes).
_NEED_STATE_LABELS = {
    "decision": "an open decision genuinely being weighed",
    "accountability": "a goal or decision that has stalled without a status change",
    "reflection": "a goal exists to weigh the situation against, with no sharper signal yet",
}


def build_retrieved_context(
    patterns: List[Pattern], insights: List[Insight], need_state: Optional[NeedState] = None,
) -> str:
    """
    Formats already-computed Patterns/Insights (plus, optionally, the
    inferred NeedState) into a plain-text block for Judgment's prompt.
    Pure function, no I/O -- callers (see src/api/server.py::send_message)
    are responsible for actually reading src/api/db.py's
    `get_learned_patterns`/`get_insights` and converting each row into a
    Pattern/Insight first, and for calling
    src/need_state/engine.py::infer_need_state themselves; this module
    has no database or WorldState dependency of its own, matching every
    other engine package's separation from src/api.

    Empty inputs (no patterns, no insights, and no meaningful need_state)
    produce "" -- a brand-new Journey, or a single-user history with
    nothing learned yet, must not see an empty-but-present "Retrieved
    Context" section, matching every other optional-input contract
    already established (e.g. src/orchestrator/modes.py's own
    mode_focus_note returning "" rather than a hollow labeled section).
    need_state="general" is treated the same as None here -- it conveys
    nothing actionable, so it never earns its own line.
    """
    need_label = _NEED_STATE_LABELS.get(need_state) if need_state else None

    if not patterns and not insights and not need_label:
        return ""

    lines: List[str] = []
    if need_label:
        lines.append(f"This turn's inferred need: {need_state} ({need_label}).")
    if patterns:
        lines.append("Known behavioral patterns (from past Journeys):")
        for p in patterns:
            lines.append(f"- [{p.pattern_type}] {p.detail} (evidence_count={p.evidence_count})")
    if insights:
        lines.append("Recurring cross-session themes (from past Journeys):")
        for i in insights:
            lines.append(f"- {i.theme}: {i.detail}")
    return "\n".join(lines)
