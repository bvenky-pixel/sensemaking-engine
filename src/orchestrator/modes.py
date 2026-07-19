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
- A FOURTH Realign round (2026-07-18, see engine/decisions.md "Realign
  rotation precomputed in Python"): re-verifying the turn_count % 5 fix
  against newly pinned production models found it still converged onto
  ONE concept (the retrospective framing) in 4 of 6 observed turns, even
  though the original verbatim-phrase problem stayed fixed -- asking the
  MODEL to compute the modulo and select a concept turned out to be
  exactly the kind of instruction-following step that varies by which
  model is primary. Fixed by moving the selection into Python entirely
  (`_realign_concept_for_turn`, called from `response_mode_focus_note`)
  -- the model is now handed one already-resolved concept per turn and
  never asked to choose or compute anything.

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
sits near one of these dimensions. Mapping: Vent->Stress,
Strategize->Motivation, Commit->Motivation (competence), Explore->
Learning Style. Realign is deliberately UNCHANGED -- its existing
turn_count % 5 rotation already asks an Identity/Narrative-flavored
question EVERY turn by design (not occasionally), so it already
satisfies its own mapping (Identity + Narrative) without a competing
modulo gate. Theory of Mind isn't mode-specific -- it's about how the
person reads named OTHER people, not something a single mode's own
register naturally elicits -- so no mode gained a Theory-of-Mind
clause; it's still (correctly) whatever naturally comes up whenever a
named person is central to a turn.

Thinnest-system-aware targeting (2026-07-18, same day, see
engine/decisions.md "POM early seeding: thinnest-system-aware
targeting"): the FIRST version above fired its `turn_count % 3 == 0`
clause blindly, regardless of whether the mapped dimension was already
well-established for this specific account, and asked the MODEL to
evaluate that modulo itself -- exactly the arithmetic/selection
unreliability the Realign saga (see "Realign rotation precomputed in
Python") already showed doesn't hold up across models. `_should_seed_pom`
now combines the same `turn_count % 3` cadence with a Python-computed
check of whether THIS account's own mapped dimension is still thin
(`_pom_dimension_is_thin`, using the account's real, per-user POM --
threaded from src/api/server.py through run_turn/run_response_generator)
-- once a dimension is no longer thin, its mode's deeper probe stops
firing entirely, and the model is never asked to compute or choose
anything. `_POM_SEED_CLAUSES` holds each mode's supplementary clause
alone; RESPONSE_MODE_FOCUS's own baseline entries no longer mention POM
seeding at all.

Deliberately a light structural nudge, never a mandate: each clause is
strictly secondary to the mode's own primary job and grounded in what
was actually said, never inventing content to manufacture a data point.

Insight-triggered conversational callback (2026-07-19, backlog #210,
see engine/decisions.md "POM: Insight-triggered conversational
callback"): a different shape from the POM-seeding clauses above --
mode-agnostic (fires the same way regardless of which of the six modes
is active, including realign, which POM-seeding deliberately skips) and
gated on `turn_count == 1` (the first turn of a brand-new Journey) AND
on a real, already-resolved Insight rather than a per-mode dimension
check. The relevance decision itself is made entirely OUTSIDE this
module (src.insight.engine.select_relevant_insight, called from
src/response/engine.py before response_mode_focus_note), same "resolve
the decision entirely in Python, hand the model only the outcome"
discipline as Realign's rotation and POM-seeding's thinness check --
this module never evaluates relevance itself, only whether to append
the already-resolved Insight's clause.
"""

from __future__ import annotations

from typing import Dict, Literal, Optional

from src.insight.schema import Insight
from src.pom.schema import PersonalOperatingModel

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
        "Planner), so left to free choice you will independently converge "
        "on the same words turn after turn even without meaning to, and "
        "even a list of alternatives to 'pick from' tends to collapse onto "
        "whichever one or two feel most natural, repeated verbatim.\n"
        "\n"
        "The rotation is RESOLVED FOR YOU, not left to your own judgment "
        "(2026-07-18, see engine/decisions.md \"Realign rotation "
        "precomputed in Python\" -- a live re-check found the prior "
        "\"compute turn_count % 5 yourself\" design still converged onto "
        "ONE concept most turns once a different model became primary, "
        "even though it stopped the original verbatim-phrase problem): "
        "for THIS turn specifically, sentence 2 should draw on the "
        "following concept -- {concept} -- write an ORIGINAL sentence "
        "around it, grounded in this turn's own specific WorldState/ "
        "Judgment/Planner content; do not quote a fixed template verbatim "
        "even if this exact concept recurs on a later turn in this same "
        "Journey (it will, roughly every 5 turns) -- rephrase it fresh "
        "each time using this turn's own specific details.\n"
        "\n"
        "Regardless of which concept this is, never phrase it as "
        "'vision,' 'trajectory,' 'envision(ing),' or 'aspiration(s)' for "
        "your career -- that whole family of words is overused and banned "
        "here, not just the two exact phrases 'vision for your career' and "
        "'long-term career aspirations.' Never assert a values/identity "
        "frame more specific than what WorldState actually supports."
    ),
}

# POM early seeding, thinnest-system-aware (2026-07-18, see
# engine/decisions.md "POM early seeding: thinnest-system-aware
# targeting"): the FIRST version of this (see the module docstring's own
# "POM early seeding via mode design" section) fired the deeper probe on
# a blind `turn_count % 3 == 0` schedule regardless of whether the
# mapped POM dimension was already well-established for this account --
# meaning Vent kept nudging toward Stress content forever, even for an
# account whose Stress reading was already confident and well-evidenced.
# Also, that first version asked the MODEL to evaluate `turn_count % 3 ==
# 0` itself -- exactly the kind of arithmetic/selection step the Realign
# saga (see "Realign rotation precomputed in Python") already showed is
# unreliable across models. Both are fixed the same way here: the gate
# is now computed in Python (_should_seed_pom), combining the same
# turn_count % 3 cadence with a check of whether THIS account's own
# mapped POM dimension is still thin (unclear/no evidence) -- once it's
# no longer thin, the deeper probe stops firing entirely, and the model
# is never asked to evaluate anything itself.
#
# Each entry is the SUPPLEMENTARY clause alone (appended to the mode's
# baseline RESPONSE_MODE_FOCUS text only when _should_seed_pom is True)
# -- not a self-contained "on turn N do X, otherwise do Y" instruction,
# since Python now decides which turns qualify, not the model.
_POM_SEED_CLAUSES: Dict[str, str] = {
    "vent": (
        "POM early seeding (2026-07-18, see engine/decisions.md \"POM "
        "early seeding: thinnest-system-aware targeting\"): this "
        "account's own Stress reading is still thin, so THIS turn, let "
        "sentence 2 go one layer deeper into what this feeling is "
        "actually carrying -- how long it's been building, or what's "
        "making it feel heavier right now than usual (e.g. something "
        "like 'Has this been building for a while, or did today just "
        "make it worse?') -- still purely validating, never diagnostic, "
        "and grounded only in what's already been said."
    ),
    "strategize": (
        "POM early seeding (2026-07-18, see engine/decisions.md \"POM "
        "early seeding: thinnest-system-aware targeting\"): this "
        "account's own Motivation reading is still thin, so THIS turn, "
        "replace the framing question with one that asks WHY the option "
        "they're leaning toward actually appeals to them personally -- "
        "e.g. something like 'What is it about that one that feels right "
        "to you -- that you'd be doing it your own way, that you'd feel "
        "confident pulling it off, or something else?' -- grounded in "
        "what they've actually said, never inventing a reason for them."
    ),
    "commit": (
        "POM early seeding (2026-07-18, see engine/decisions.md \"POM "
        "early seeding: thinnest-system-aware targeting\"): this "
        "account's own Motivation/competence reading is still thin, so "
        "THIS turn, alongside the dated-commitment question, also ask "
        "what's actually making follow-through hard for them "
        "specifically -- e.g. something like 'Is it that you don't feel "
        "set up to pull this off, or is something else getting in the "
        "way?' -- grounded in what's already been said, never a generic "
        "diagnostic question detached from this turn's content."
    ),
    "explore": (
        "POM early seeding (2026-07-18, see engine/decisions.md \"POM "
        "early seeding: thinnest-system-aware targeting\"): this "
        "account's own Learning Style reading is still thin, so THIS "
        "turn, phrase the challenge as a question about how they'd "
        "actually go about checking whether the assumption is true -- "
        "e.g. something like 'How would you actually find out -- ask "
        "them directly, look for evidence yourself, or something else?' "
        "-- this reveals how they approach uncertainty, not just what "
        "they currently assume."
    ),
}


def _pom_dimension_is_thin(mode: str, pom: Optional[PersonalOperatingModel]) -> bool:
    """True when this account's own POM reading for the dimension `mode`
    maps to (see _POM_SEED_CLAUSES above) is still unclear/unevidenced --
    including when `pom` itself is None (never computed yet, or an
    anonymous caller with no standing profile at all), which is the
    thinnest possible state. Once a dimension has a confident,
    evidenced reading, this returns False permanently for that
    dimension -- the deeper probe stops being asked once it's no longer
    needed, same "omit rather than show a hollow signal" discipline
    already used when POM itself decides whether to render a system at
    all (see PersonalOperatingModel.svelte)."""
    if pom is None:
        return True
    if mode == "vent":
        return pom.stress.level == "unclear" or not pom.stress.evidence
    if mode == "strategize":
        return (
            pom.motivation.autonomy == "unclear" or not pom.motivation.autonomy_evidence
        ) or (
            pom.motivation.competence == "unclear" or not pom.motivation.competence_evidence
        )
    if mode == "commit":
        return pom.motivation.competence == "unclear" or not pom.motivation.competence_evidence
    if mode == "explore":
        return not pom.learning_style.style or not pom.learning_style.evidence
    return False


def _should_seed_pom(mode: str, turn_count: int, pom: Optional[PersonalOperatingModel]) -> bool:
    """Both conditions must hold: the same turn_count % 3 cadence the
    first version of this feature used (kept -- even for a persistently
    thin dimension, a deeper probe every single turn would read as
    fishing, not attentive), AND this account's own mapped dimension is
    still thin (see _pom_dimension_is_thin). Modes with no POM-seeding
    clause at all (realign, or any unrecognized mode) always return
    False."""
    if mode not in _POM_SEED_CLAUSES:
        return False
    return turn_count % 3 == 0 and _pom_dimension_is_thin(mode, pom)

# Realign rotation, precomputed in Python (2026-07-18, see
# engine/decisions.md "Realign rotation precomputed in Python"): the
# ORIGINAL turn_count % 5 fix (see the module docstring's "Realign round
# four" history) asked the MODEL to compute the modulo and pick a
# concept itself. A live re-verification against the new pinned models
# (Qwen3-32B primary for Planner, see engine/decisions.md "Per-component
# paid model pinning") found 4 of 6 observed turns converged on the SAME
# concept (index 1, the retrospective framing) regardless of what
# turn_count actually was -- the specific banned-phrase problem this
# rotation was built to fix stayed fixed, but the underlying "a
# memoryless generator collapses onto one comfortable framing" failure
# mode came back via a different concept, this time because the
# arithmetic/selection step itself isn't reliably followed by every
# model. Fix: compute the index in Python (deterministic regardless of
# which model is primary) and inject only the single resolved concept
# into the prompt -- the model is never asked to choose or compute
# anything, only to write an original sentence around what it's given.
_REALIGN_CONCEPTS = [
    "the cost or tradeoff of choosing this path",
    "looking back on this a year from now and asking whether it held up",
    "whether this is genuinely wanted vs. expected of them",
    "what it says about their priorities",
    "what kind of professional or person they're trying to become",
]


def _realign_concept_for_turn(turn_count: int) -> str:
    return _REALIGN_CONCEPTS[turn_count % len(_REALIGN_CONCEPTS)]


# Insight-triggered conversational callback (2026-07-19, backlog #210) --
# a light, secondary acknowledgment, never the turn's main content;
# explicitly allowed to be skipped by the model if it would feel forced,
# same "never a mandate" discipline as the POM-seeding clauses above.
_INSIGHT_CALLBACK_CLAUSE = (
    "Insight-triggered conversational callback (2026-07-19, see "
    "engine/decisions.md \"POM: Insight-triggered conversational "
    "callback\"): this account has a recurring cross-session theme -- "
    "{theme}: {detail} -- that appears genuinely connected to what this "
    "brand-new Journey has already touched on this turn. Naturally, "
    "briefly acknowledge that connection somewhere in your response "
    "(e.g. something in the register of \"This sounds connected to "
    "something we've noticed before...\") -- do not force it if it "
    "would read as a non sequitur, and never let it crowd out this "
    "turn's own primary response; this is a light, secondary "
    "acknowledgment, not the turn's main content."
)


def _insight_callback_note(turn_count: int, insight: Optional[Insight]) -> str:
    """Returns the Insight-callback clause for THIS turn, or "" when it
    shouldn't fire. Only ever on turn_count == 1 (the first turn of a
    brand-new Journey, see WorldState.turn_count) and only when
    `insight` -- already resolved by
    src.insight.engine.select_relevant_insight against this turn's own
    content -- is not None; this function never decides relevance
    itself, only whether to surface the already-resolved choice."""
    if turn_count != 1 or insight is None:
        return ""
    return _INSIGHT_CALLBACK_CLAUSE.format(theme=insight.theme, detail=insight.detail)


def planner_mode_focus_note(mode: Optional[str]) -> str:
    """Returns Planner's prompt-injection paragraph for a given mode, or
    "" when no mode was chosen -- a Journey started before this feature
    existed (or an unrecognized value) has no note, which must never
    break Planner: it already has well-defined default behavior without
    one."""
    if not mode:
        return ""
    return PLANNER_MODE_FOCUS.get(mode, "")


def response_mode_focus_note(
    mode: Optional[str],
    turn_count: int = 0,
    pom: Optional[PersonalOperatingModel] = None,
    insight: Optional[Insight] = None,
) -> str:
    """Same contract as planner_mode_focus_note above, for Response's
    own, separately-worded focus text.

    turn_count (2026-07-18, see engine/decisions.md "Realign rotation
    precomputed in Python"): WorldState.turn_count for THIS turn -- used
    by Realign's own deterministic concept rotation
    (_realign_concept_for_turn above), by the POM-seeding cadence check
    below (_should_seed_pom), and by the Insight-callback gate
    (_insight_callback_note, only turn_count == 1); every other mode's
    note ignores it entirely, same as before it existed. Realign's own
    entry contains a literal `{concept}` format placeholder filled in
    here rather than left for the model to resolve itself -- a live
    re-verification found the model-computes-the-modulo design still
    converged onto one concept most turns once a different model became
    Planner's primary, so the selection is now made in Python, not left
    to the model's own arithmetic/instruction-following.

    pom (2026-07-18, see engine/decisions.md "POM early seeding:
    thinnest-system-aware targeting"): this account's own current
    PersonalOperatingModel (None for an anonymous caller, or an account
    whose POM has never been computed) -- used ONLY to decide whether
    Vent/Strategize/Commit/Explore's POM-seeding clause should fire this
    turn (see _should_seed_pom); ignored by every other mode, and by
    these same four modes once their mapped dimension is no longer
    thin.

    insight (2026-07-19, backlog #210, see engine/decisions.md "POM:
    Insight-triggered conversational callback"): the single Insight
    already selected as relevant to THIS turn
    (src.insight.engine.select_relevant_insight), or None if no Insight
    exists or none scored as relevant -- unlike POM-seeding, this clause
    is mode-agnostic and appends to EVERY mode's note, including
    realign, whenever turn_count == 1 and insight is not None; see
    _insight_callback_note."""
    note = ""
    if mode:
        note = RESPONSE_MODE_FOCUS.get(mode, "")
        if mode == "realign" and note:
            note = note.format(concept=_realign_concept_for_turn(turn_count))
        elif note and _should_seed_pom(mode, turn_count, pom):
            note = note + "\n\n" + _POM_SEED_CLAUSES[mode]
    callback = _insight_callback_note(turn_count, insight)
    if callback:
        note = f"{note}\n\n{callback}" if note else callback
    return note
