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

Distinct character per mode (2026-07-15, same day, direct follow-up):
the first cut's focus notes were too similar in shape across all five
modes -- each nudged emphasis without actually changing behavior in a
felt way. Explicit user examples set the bar: Vent should read as a
genuinely different, validation-first voice (an empathetic listener,
not a softer version of the default); Strategize should actively
enumerate concrete choices toward a decision, not just discuss tradeoffs
in the abstract; Explore should actually challenge/push back on the
person's own stated assumptions, not just ask neutrally open questions.
Planner and Response now get SEPARATE focus notes per mode (below) --
Planner's own job (deciding what to prioritize) and Response's (deciding
how to phrase it, and whether to populate `options`) diverge enough per
mode that one shared paragraph could no longer serve both without being
vague in one direction or the other.
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
        "description": "Lay out real choices and move toward a decision.",
    },
    "commit": {
        "label": "Commit",
        "description": "Get real about follow-through.",
    },
    "explore": {
        "label": "Explore",
        "description": "Get pushed on your own thinking, not just asked about it.",
    },
    "realign": {
        "label": "Realign",
        "description": "Check this against what actually matters to you.",
    },
}

# Injected into Planner's own prompt (see src/planner/prompt.py's
# build_messages) -- what THIS mode means for what to prioritize
# deciding: primary_objective, questions_to_explore, priority_topics.
# Never authorizes overriding user agency (Governing Law 2) or inventing
# content WorldState/Judgment don't already support -- a mode changes
# emphasis, not the Grounding law.
PLANNER_MODE_FOCUS: Dict[str, str] = {
    "vent": (
        "This Journey was started in Vent mode: the person wants to be heard "
        "right now, not steered toward a decision or a plan. Your "
        "primary_objective and questions_to_explore should stay in emotional/ "
        "validating territory (acknowledging feelings, inviting them to say "
        "more) rather than fact-finding, tradeoff analysis, or action "
        "steps -- even if WorldState/Judgment surface an unresolved decision "
        "or risk, leave it for a later turn unless the person's own message "
        "clearly asks for help solving something."
    ),
    "strategize": (
        "This Journey was started in Strategize mode: the person wants "
        "concrete options laid out and help moving toward an actual "
        "decision, not just reflection on the situation. Your "
        "primary_objective and questions_to_explore should push toward "
        "naming and comparing specific options (grounded in WorldState's "
        "decision_options/active_decisions) and narrowing toward a choice, "
        "not stay purely exploratory or abstract about tradeoffs."
    ),
    "commit": (
        "This Journey was started in Commit mode: the person wants help "
        "committing to concrete follow-through, not open-ended reflection. "
        "Your primary_objective and questions_to_explore should push for "
        "specifics -- what exactly, by when -- rather than staying at the "
        "level of general intentions; if WorldState's commitments/goals are "
        "vague, aim to pin them down rather than explore around them."
    ),
    "explore": (
        "This Journey was started in Explore mode: the person wants their "
        "own thinking challenged, not gently reflected back. Your "
        "primary_objective should aim to press on a SPECIFIC assumption, "
        "contradiction, or unexamined belief Judgment has already "
        "identified (assumptions_to_test, contradictions, risks) rather "
        "than stay neutral or purely open-ended -- pick the single most "
        "load-bearing one to test this turn, same as any other turn's "
        "single-highest-priority-objective discipline."
    ),
    "realign": (
        "This Journey was started in Realign mode: the person wants to "
        "check this against their own values and direction. Your "
        "primary_objective should connect the current situation back to "
        "WorldState's own goals/facts about who this person is or is "
        "trying to become, not stay purely situational."
    ),
}

# Injected into Response's own prompt (see src/response/prompt.py's
# build_messages) -- what THIS mode means for HOW to phrase sentence 2
# (see Response's own STRUCTURE guidance) and whether to populate
# `options`. Separate dict from PLANNER_MODE_FOCUS above because
# Response's job (expression) diverges from Planner's (deciding what)
# enough per mode that one shared paragraph stopped being useful for
# either -- e.g. Strategize's push to actually populate `options` is a
# Response-layer concern, not a Planner one.
RESPONSE_MODE_FOCUS: Dict[str, str] = {
    "vent": (
        "This Journey was started in Vent mode: you are, in this mode, an "
        "empathetic listener first -- your primary job is emotional "
        "validation, not problem-solving. Do not offer advice, tradeoffs, "
        "or action steps unless the person explicitly asks for them. "
        "Sentence 2 (the question) should invite the person to say more "
        "about how they're feeling or what's underneath this -- a check-in "
        "question ('What's the hardest part of this for you right now?'), "
        "never a diagnostic one aimed at solving anything."
    ),
    "strategize": (
        "This Journey was started in Strategize mode: the person wants "
        "real choices rattled out, not just an open question. Whenever "
        "WorldState/Planner already name 2-3 concrete options relevant to "
        "this turn (e.g. decision_options), actively populate `options` "
        "(see below) with them -- lean into using it in this mode, rather "
        "than leaving it empty by default the way other modes usually "
        "would. Sentence 2 should push toward a decision (e.g. 'Which of "
        "these feels closer to the right call?') rather than stay purely "
        "open-ended -- still grounded, never inventing an option nothing "
        "upstream actually named."
    ),
    "commit": (
        "This Journey was started in Commit mode: the person wants "
        "concrete follow-through, not general reflection. Sentence 2 "
        "should ask for a specific commitment -- what exactly, by when -- "
        "rather than a general check-in question, grounded in whatever "
        "WorldState's goals/commitments already say."
    ),
    "explore": (
        "This Journey was started in Explore mode: the person wants their "
        "own statements and assumptions challenged, not just asked about. "
        "Sentence 2 should push back on something SPECIFIC Judgment/Planner "
        "already flagged (an assumption_to_test, a contradiction, a risk) -- "
        "phrase it as a real challenge ('You said X -- but doesn't that "
        "assume Y? What if that's not true?'), not a neutral open question. "
        "Still grounded (never invent a new critique WorldState/Judgment "
        "didn't support) and still respects user agency: challenging their "
        "thinking means surfacing a real tension for them to examine, never "
        "asserting they're wrong or telling them what to conclude."
    ),
    "realign": (
        "This Journey was started in Realign mode: the person wants this "
        "checked against their own values and direction. Sentence 2 should "
        "connect the situation to identity/values -- asking whether this "
        "choice fits who they're trying to become, grounded in WorldState's "
        "own goals/facts, not an invented values framework."
    ),
}


def planner_mode_focus_note(mode: Optional[str]) -> str:
    """Returns Planner's prompt-injection paragraph for a given mode, or
    "" when no mode was chosen -- a Journey started before this feature
    existed (or an unrecognized value) has no note, which must never
    break Planner: it already has well-defined default behavior without
    one."""
    if not mode:
        return ""
    return PLANNER_MODE_FOCUS.get(mode, "")


def response_mode_focus_note(mode: Optional[str]) -> str:
    """Same contract as planner_mode_focus_note above, for Response's
    own, separately-worded focus text."""
    if not mode:
        return ""
    return RESPONSE_MODE_FOCUS.get(mode, "")
