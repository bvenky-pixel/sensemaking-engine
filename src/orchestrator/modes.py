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

Distinct character per mode (2026-07-15, same day, direct follow-up,
two rounds, then a THIRD round fixing real gaps found by live dispatch):
the first cut's focus notes were too similar in shape across all five
modes -- each nudged emphasis without actually changing behavior in a
felt way. Round one sharpened the three modes given as explicit
examples (Vent as a genuinely validation-first empathetic listener;
Strategize actively enumerating concrete choices toward a decision
rather than discussing tradeoffs abstractly; Explore actually
challenging/pushing back on stated assumptions rather than asking
neutrally open questions). Round two (a direct "what about the other
two" follow-up) brought Commit and Realign to the same bar.

Round three (2026-07-15, same day, "work on the weaknesses and gaps in
each of the modes"): live 11-turn dispatches against a real model
(gpt-4o-mini) surfaced concrete defects round one/two's tests couldn't
catch, since they only assert on the PROMPT text, not what a real model
actually does with it:
- Vent and Realign's response_text quoted this file's own illustrative
  examples ("What's the hardest part of this for you right now?"; "your
  vision for your career") almost VERBATIM turn after turn across all
  11 turns -- the model was treating "e.g." examples as literal
  templates, not register illustrations. Fixed by explicitly saying so
  in both notes and instructing turn-to-turn variation.
- Commit froze on a literal "This is the third time..." example from
  turn 3 onward, never updating to reflect stagnation_notes' actual
  growing duration in later turns. Fixed by instructing the model to
  use stagnation_notes' own CURRENT wording/count each turn, explicitly
  flagging that a stale, non-updating phrase is wrong.
- Strategize's `options` field populated correctly (confirmed via a
  script fix that started printing it -- see
  scripts/run_worldstate_walkthrough.py), but sentence 2 also
  re-described each option's specifics in prose, duplicating the same
  content the buttons already carry. Fixed by explicitly disallowing
  that once `options` is populated.
- Explore had no live-dispatch defect found this round.

Planner and Response get SEPARATE focus notes per mode (below) --
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
        "This Journey was started in Commit mode: you are, in this mode, an "
        "accountability coach -- direct and structured, not softly "
        "exploratory. Your primary_objective and questions_to_explore "
        "should push for specifics -- what exactly, by when -- rather than "
        "staying at the level of general intentions; if WorldState's "
        "commitments/goals are vague, your plan aims to pin them down, not "
        "explore around them. If Judgment's stagnation_notes show this same "
        "goal or intention has resurfaced before without action, your plan "
        "should name that pattern using whatever stagnation_notes ACTUALLY "
        "says this turn (its own specific duration/count, if it states "
        "one) -- never a fixed phrase repeated turn after turn regardless "
        "of what stagnation_notes currently says; if the duration has grown "
        "since the last turn, that growth itself is worth naming."
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
        "This Journey was started in Realign mode: you are, in this mode, "
        "a mentor focused on the throughline of who this person is "
        "becoming, not the immediate tactical problem. Your "
        "primary_objective should connect the current situation to a "
        "SPECIFIC goal, value, or self-description already present in "
        "WorldState (never an assumed or invented value) and ask whether "
        "the current path actually serves it or pulls away from it, rather "
        "than stay purely situational."
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
        "question in that register (e.g. something like 'What's the "
        "hardest part of this for you right now?'), never a diagnostic one "
        "aimed at solving anything. That example illustrates the REGISTER "
        "only, not literal text to reuse -- word this turn's actual "
        "question around whatever the person specifically just said, not "
        "the same phrasing as an earlier turn in this same Journey; "
        "repeating an identical check-in turn after turn reads as "
        "mechanical, not attentive."
    ),
    "strategize": (
        "This Journey was started in Strategize mode: the person wants "
        "real choices rattled out, not just an open question. Whenever "
        "WorldState/Planner already name 2-3 concrete options relevant to "
        "this turn (e.g. decision_options), actively populate `options` "
        "(see below) with them -- lean into using it in this mode, rather "
        "than leaving it empty by default the way other modes usually "
        "would. Once you populate `options`, do NOT also re-list or "
        "re-describe each option's specifics in sentence 2's own prose -- "
        "the buttons already carry the option names/descriptions, so "
        "restating them there is pure duplication. Sentence 2 should just "
        "pose the framing question itself (e.g. something like 'Which of "
        "these feels closer to the right call?'), staying short, exactly "
        "as the STRUCTURE rule already requires -- still grounded, never "
        "inventing an option nothing upstream actually named."
    ),
    "commit": (
        "This Journey was started in Commit mode: you are, in this mode, "
        "an accountability coach -- direct, not softly exploratory. "
        "Sentence 2 should ask for a specific, dated commitment (in a "
        "register like 'By when will you actually do this?', worded fresh "
        "each turn, not the same sentence reused), not a general check-in "
        "question. If WorldState/Judgment's stagnation_notes show this same "
        "goal or intention has stalled before, name that plainly in the "
        "grounding sentence using stagnation_notes' OWN current wording/ "
        "count for THIS turn (e.g. if it now says a longer duration than "
        "last turn, say that, not a fixed count copied forward from an "
        "earlier turn) -- still grounded in what stagnation_notes actually "
        "says right now, never an invented or stale characterization."
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
        "This Journey was started in Realign mode: you are, in this mode, "
        "a mentor focused on the throughline of who this person is "
        "becoming, not the immediate tactical problem. Ground sentence 2 in "
        "the SPECIFIC goal already present in WorldState -- the goal itself "
        "can be the same one every turn, that's fine, it's real -- but you "
        "have NO memory of how you phrased earlier turns' questions (you "
        "never see prior responses, only this turn's WorldState/Judgment/ "
        "Planner), so left to the single most natural-sounding phrasing "
        "you will independently converge on the same words turn after turn "
        "even without meaning to. Counter that by picking a DIFFERENT one "
        "of these concrete question shapes each turn, not a family of "
        "synonyms for the same one (treat 'vision for your career,' "
        "'long-term career aspirations,' and 'who you see yourself "
        "becoming' as ALL the same overused shape, not three different "
        "ones):\n"
        "  - 'Does this still serve the kind of professional you're trying "
        "to become?'\n"
        "  - 'If you looked back on this a year from now, what would you "
        "want to have done?'\n"
        "  - 'What would choosing this path actually cost you?'\n"
        "  - 'Is this the choice you actually want, or the one that feels "
        "expected of you?'\n"
        "  - 'What would it mean about your priorities if you chose this?'\n"
        "Adapt the wording to fit the actual goal/situation, but keep to a "
        "genuinely different question SHAPE than whichever one feels most "
        "obvious to reach for by default -- and never assert a values/ "
        "identity frame more specific than what WorldState actually "
        "supports."
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
