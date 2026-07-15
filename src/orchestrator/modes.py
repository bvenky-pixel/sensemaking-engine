"""
Counseling modes (2026-07-15, see engine/decisions.md "Counseling
modes"): five frontend-selectable entry points, one chosen per Journey
at creation time, each corresponding to one of the five coaching
perspectives named in the founder's uploaded vision doc
(`Confidant_Architecture.docx`'s Layer 9 -- Judgement): Strategic
Advisor, Accountability Coach, Mentor, Supportive Companion, Socratic
Guide.

NOT the full multi-perspective Judgement + Synthesis system that vision
doc describes -- this project's own `engine/specs/architecture-roadmap-v1.md`
explicitly gates that as Phase 3, pending real Phase 1/2 evidence. This
is a much smaller, buildable slice: the person picks ONE lens up front,
and Planner/Response stay biased toward that lens for the whole Journey,
rather than running all five perspectives and synthesizing tensions
every turn.

Labels are plain, emotive action verbs a person would actually tap
("Vent", "Strategize") -- never the vision doc's internal coaching
jargon ("Supportive Companion", "Socratic Guide"), which is never meant
to reach a prompt or a person.
"""

from __future__ import annotations

from typing import Dict, Literal, Optional

CounselingMode = Literal["vent", "strategize", "commit", "explore", "realign"]

# Frontend copy: label + one-line description shown on the mode-select
# screen (see frontend/app/src/screens/ModeSelect.svelte). Kept here,
# not duplicated in the frontend, so the backend's prompt framing below
# and the person's own understanding of what they picked never drift
# apart -- the API is the single source of truth for what each mode
# means, same "reflection of backend truth" principle already governing
# every other frontend/api.js call.
MODE_COPY: Dict[str, Dict[str, str]] = {
    "vent": {
        "label": "Vent",
        "description": "Just get this out. No fixing needed yet.",
    },
    "strategize": {
        "label": "Strategize",
        "description": "Weigh the options and the tradeoffs.",
    },
    "commit": {
        "label": "Commit",
        "description": "Get real about follow-through.",
    },
    "explore": {
        "label": "Explore",
        "description": "Think it through out loud, one question at a time.",
    },
    "realign": {
        "label": "Realign",
        "description": "Check this against what actually matters to you.",
    },
}

# Injected into Planner's and Response's own prompts (see build_messages
# in each) as a short, plain-language framing of that lens's focus.
# Deliberately a separate dict from MODE_COPY above, even though both
# derive from the same lens: MODE_COPY is what the PERSON reads before
# picking, worded as an invitation; this is what the MODEL reads every
# turn, worded as an instruction -- same content, different audience,
# same reason response_text and its own prompt guidance are never the
# same string.
MODE_FOCUS: Dict[str, str] = {
    "vent": (
        "This Journey was started in Vent mode: the person wants to be heard "
        "right now, not steered toward a decision or a plan. Prioritize "
        "acknowledgment and emotional validation; avoid tradeoff analysis, "
        "action steps, or advice unless the person actually asks for it."
    ),
    "strategize": (
        "This Journey was started in Strategize mode: the person wants help "
        "weighing options. Prioritize opportunity cost, tradeoffs, risk, and "
        "prioritization in what you focus on and ask about."
    ),
    "commit": (
        "This Journey was started in Commit mode: the person wants help with "
        "follow-through. Prioritize execution, consistency, and concrete "
        "next steps over open-ended exploration."
    ),
    "explore": (
        "This Journey was started in Explore mode: the person wants to think "
        "out loud. Prioritize genuinely open questions that help them arrive "
        "at their own read on the situation, rather than offering "
        "conclusions or a plan."
    ),
    "realign": (
        "This Journey was started in Realign mode: the person wants to check "
        "this against their own values and direction. Prioritize identity, "
        "values, and what this situation means for who they're trying to "
        "become."
    ),
}


def mode_focus_note(mode: Optional[str]) -> str:
    """Returns the prompt-injection paragraph for a given mode, or ""
    when no mode was chosen -- a Journey started before this feature
    existed (or an unrecognized value) has no note, which must never
    break Planner/Response: both already have a well-defined default
    behavior without one."""
    if not mode:
        return ""
    return MODE_FOCUS.get(mode, "")
