"""
Counseling modes (2026-07-15, see engine/decisions.md "Counseling
modes"): five frontend-selectable entry points, one chosen per Journey
at creation time, each corresponding to one of the five coaching
perspectives named in the founder's uploaded vision doc
(`Confidant_Architecture.docx`'s Layer 9 -- Judgement): Strategic
Advisor, Accountability Coach, Mentor, Supportive Companion, Socratic
Guide.

Originally NOT the full multi-perspective Judgement + Synthesis system
the vision doc describes -- Phase 1/2 evidence (Learning, Memory Store,
Insight Engine, Retrieval) hadn't shipped yet when this was first built,
so the five fixed modes below were a much smaller, buildable slice: the
person picks ONE lens up front, and Planner/Response stay biased toward
that lens for the whole Journey, rather than running all five
perspectives and synthesizing tensions every turn.

Synthesis (2026-07-16, see engine/decisions.md "Synthesis"): a sixth
mode, "adaptive", added once Phase 1/2 evidence existed. Rather than a
separate multi-call fusion pipeline (5 lens calls plus a fusion call --
6x a normal turn's LLM cost), Adaptive keeps Planner's one existing call
but gives it all five lenses' own established guidance as options and
asks it to choose whichever fits THIS TURN specifically (see
PLANNER_MODE_FOCUS["adaptive"] below), set that choice on a new
`active_lens` output field (src/planner/schema.py), and plan accordingly
under it. Orchestrator then resolves that per-turn choice into the
`mode` Response itself receives (see src/orchestrator/engine.py::run_turn),
so Response reuses that lens's own existing, already-tuned
RESPONSE_MODE_FOCUS text directly -- no separate Adaptive-specific
Response text to keep in sync. Same per-turn LLM cost as any other mode;
the "fusion" is choosing among established lenses each turn, not running
all five and synthesizing them.

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
- Realign took THREE further live-dispatch rounds after that (see the
  "realign" entry's own internal comments are in engine/decisions.md,
  not duplicated here): each fix chased the model to a new narrow
  fallback rather than producing real variety, until rotation was keyed
  to WorldState.turn_count (visible, deterministic, no memory needed)
  instead of left to free choice among alternatives -- a free "pick one
  of these" list still collapses onto whichever one or two feel most
  natural, repeated verbatim.

Planner and Response get SEPARATE focus notes per mode (below) --
Planner's own job (deciding what to prioritize) and Response's (deciding
how to phrase it, and whether to populate `options`) diverge enough per
mode that one shared paragraph could no longer serve both without being
vague in one direction or the other.

POM early seeding via mode design (2026-07-18, see engine/decisions.md
"POM early seeding via mode design"): Personal Operating Model
(src/pom/engine.py) needs enough grounded evidence per system before it
trusts a field above "unclear" -- for a new account, that evidence only
exists once enough conversation has touched each of the 6 LLM-inferred
systems (Identity, Motivation/SDT, Learning Style, Stress, Narrative,
Theory of Mind; Belief/Relationship are mechanical and already seed from
turn one regardless of mode). Each mode's own natural question already
sits near one of these dimensions, so RESPONSE_MODE_FOCUS below adds one
`turn_count % 3 == 0` clause per mode -- deterministic, same discipline
Realign's own rotation already established, since a vague "occasionally
ask about X" instruction doesn't reliably produce real variety from a
memoryless generator. Mapping: Vent->Stress, Strategize->Motivation,
Commit->Motivation (competence), Explore->Learning Style. Realign is
deliberately UNCHANGED -- its existing turn_count % 5 rotation already
asks an Identity/Narrative-flavored question EVERY turn by design (not
occasionally), so it already satisfies its own mapping (Identity +
Narrative) without a competing modulo gate. Theory of Mind isn't
mode-specific -- it's about how the person reads named OTHER people, not
something a single mode's own register naturally elicits -- so no mode
gained a Theory-of-Mind clause; it's still (correctly) whatever
naturally comes up whenever a named person is central to a turn.
Deliberately a light structural nudge, never a mandate: each clause is
strictly secondary to the mode's own primary job and grounded in what
was actually said, never inventing content to manufacture a data point.
"""

from __future__ import annotations

from typing import Dict, Literal, Optional

CounselingMode = Literal["vent", "strategize", "commit", "explore", "realign", "adaptive"]

# The five CONCRETE lenses -- every CounselingMode except "adaptive"
# itself, which doesn't commit to one. Used to type Planner's own
# `active_lens` output field (see src/planner/schema.py) and to build
# Adaptive mode's own focus note below, so Adaptive never has to name
# the five ids as a separate, driftable literal list.
ConcreteLens = Literal["vent", "strategize", "commit", "explore", "realign"]
_CONCRETE_LENS_IDS = ("vent", "strategize", "commit", "explore", "realign")

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
    "adaptive": {
        "label": "Adaptive",
        "description": "Confidant senses what you need, turn by turn.",
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

# Synthesis v1 (see engine/decisions.md "Synthesis"): rather than a
# separate multi-call fusion pipeline (5 lens calls + a fusion call --
# 6x today's per-turn cost), Adaptive is Planner's EXISTING single call,
# given all five lenses' own established guidance as options and asked
# to pick the one that fits THIS TURN, then plan accordingly under it.
# Built from the five entries above, not retyped, so Adaptive's guidance
# can never drift from what each lens actually says elsewhere in this
# file -- editing a lens's own entry automatically updates what Adaptive
# sees too.
_ADAPTIVE_LENS_SUMMARIES = "\n\n".join(
    f'[{lens_id}]\n{PLANNER_MODE_FOCUS[lens_id]}' for lens_id in _CONCRETE_LENS_IDS
)

PLANNER_MODE_FOCUS["adaptive"] = (
    "This Journey was started in Adaptive mode: the person did not commit "
    "to one lens up front -- your job this turn is to choose whichever of "
    "the five lenses below actually fits what THIS TURN's message and "
    "current WorldState/Judgment call for, then plan exactly as that "
    "lens's own guidance directs. This is a PER-TURN choice, not a "
    "whole-Journey one like the other five modes: a different turn later "
    "in this same Journey may genuinely call for a different lens, and "
    "that is correct, not an inconsistency to avoid.\n"
    "\n"
    f"{_ADAPTIVE_LENS_SUMMARIES}\n"
    "\n"
    "Ground the choice in what's actually present this turn -- e.g. "
    "distress with nothing yet to solve points to vent; a decision "
    "needing to be narrowed points to strategize; a stalled commitment "
    "flagged in stagnation_notes points to commit; a flagged assumption "
    "or contradiction ripe to press on points to explore; content "
    "touching a value, identity, or long-term throughline points to "
    "realign. Never invent signal that isn't there just to justify a "
    "choice. Set `active_lens` to the id of whichever lens you chose "
    "(exactly one of: vent, strategize, commit, explore, realign -- never "
    "'adaptive' itself), and let every other output field follow that "
    "lens's own guidance above for this turn."
)

# No separate RESPONSE_MODE_FOCUS["adaptive"] entry -- Response is given
# the CONCRETE lens Planner actually chose (state.orchestrator.engine
# resolves plan.active_lens into the `mode` passed to Response, see
# run_turn), so Response reuses that lens's own existing, already-tuned
# RESPONSE_MODE_FOCUS entry directly rather than a duplicate Adaptive-
# specific text that could drift from it.

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
        "mechanical, not attentive.\n"
        "\n"
        "POM early seeding (2026-07-18, see engine/decisions.md \"POM "
        "early seeding via mode design\"): on every third turn "
        "(`turn_count % 3 == 0`), let sentence 2 go one layer deeper into "
        "what this feeling is actually carrying -- how long it's been "
        "building, or what's making it feel heavier right now than usual "
        "(e.g. something like 'Has this been building for a while, or did "
        "today just make it worse?') -- still purely validating, never "
        "diagnostic, and grounded only in what's already been said. On "
        "every OTHER turn, stay with the lighter check-in register above; "
        "this deeper probe is occasional by design, not a checklist item "
        "to hit every turn."
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
        "inventing an option nothing upstream actually named.\n"
        "\n"
        "POM early seeding (2026-07-18, see engine/decisions.md \"POM "
        "early seeding via mode design\"): on every third turn "
        "(`turn_count % 3 == 0`), replace the framing question with one "
        "that asks WHY the option they're leaning toward actually appeals "
        "to them personally -- e.g. something like 'What is it about that "
        "one that feels right to you -- that you'd be doing it your own "
        "way, that you'd feel confident pulling it off, or something "
        "else?' -- grounded in what they've actually said, never inventing "
        "a reason for them. On every OTHER turn, use the plain framing "
        "question above instead."
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
        "says right now, never an invented or stale characterization.\n"
        "\n"
        "POM early seeding (2026-07-18, see engine/decisions.md \"POM "
        "early seeding via mode design\"): on every third turn "
        "(`turn_count % 3 == 0`), alongside the dated-commitment question, "
        "also ask what's actually making follow-through hard for them "
        "specifically -- e.g. something like 'Is it that you don't feel "
        "set up to pull this off, or is something else getting in the "
        "way?' -- grounded in what's already been said, never a generic "
        "diagnostic question detached from this turn's content. On every "
        "OTHER turn, stick to the plain dated-commitment question above."
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
        "asserting they're wrong or telling them what to conclude.\n"
        "\n"
        "POM early seeding (2026-07-18, see engine/decisions.md \"POM "
        "early seeding via mode design\"): on every third turn "
        "(`turn_count % 3 == 0`), phrase the challenge as a question about "
        "how they'd actually go about checking whether the assumption is "
        "true -- e.g. something like 'How would you actually find out -- "
        "ask them directly, look for evidence yourself, or something "
        "else?' -- this reveals how they approach uncertainty, not just "
        "what they currently assume. On every OTHER turn, use the direct "
        "challenge register above instead."
    ),
    "realign": (
        "This Journey was started in Realign mode: you are, in this mode, "
        "a mentor focused on the throughline of who this person is "
        "becoming, not the immediate tactical problem. Ground sentence 2 in "
        "the SPECIFIC goal already present in WorldState -- the goal itself "
        "can be the same one every turn, that's fine, it's real -- but you "
        "have NO memory of how you phrased earlier turns' questions (you "
        "never see prior responses, only this turn's WorldState/Judgment/ "
        "Planner), so left to free choice you will independently converge "
        "on the same words turn after turn even without meaning to, and "
        "even a list of alternatives to 'pick from' tends to collapse onto "
        "whichever one or two feel most natural, repeated verbatim.\n"
        "\n"
        "Resolve this WITHOUT needing memory: WorldState includes "
        "`turn_count`, a plain integer you already see this turn. Compute "
        "`turn_count % 5` and let the result select which underlying "
        "CONCEPT sentence 2 draws on this turn (0=cost/tradeoff of this "
        "path, 1=looking back on this a year from now, 2=whether this is "
        "genuinely wanted vs. expected of them, 3=what it says about their "
        "priorities, 4=what kind of professional/person they're trying to "
        "become) -- a deterministic rotation needs no memory of past turns, "
        "just this turn's own visible number. Write an ORIGINAL sentence "
        "around whatever concept that index points to; do not quote a fixed "
        "template verbatim turn after turn even when the same index recurs "
        "later in a long Journey (turn_count % 5 repeats every 5 turns) -- "
        "rephrase it fresh each time using this turn's own specific details.\n"
        "\n"
        "Regardless of which concept you land on, never phrase it as "
        "'vision,' 'trajectory,' 'envision(ing),' or 'aspiration(s)' for "
        "your career -- that whole family of words is overused and banned "
        "here, not just the two exact phrases 'vision for your career' and "
        "'long-term career aspirations.' Never assert a values/identity "
        "frame more specific than what WorldState actually supports."
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
