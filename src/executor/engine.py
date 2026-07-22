"""
Executor v1 -- System Architecture v2's fourth component, built last.

Implements the Executor section of
engine/specs/system-architecture-v2-specification.md. Scoped to exactly
the one worked example the spec itself gives: the Clarity Brief. No
other artifact type (email drafts, reminders, documents) is built here
-- those stay named-but-unimplemented, same status as Learning, until a
real need for one exists.

`build_clarity_brief` is a FIXED, DESIGN-TIME TEMPLATE, authored once
here and applied uniformly to whatever WorldState/Judgment/Planner
contain -- never a fresh per-instance decision about what belongs. This
is what keeps Executor's "never reasons" claim true (see
engine/specs/system-architecture-v2-review.md's correction on this exact
point). The mapping below is a genuine design decision, stated
explicitly so it can be reviewed and revised as a mapping change, not
silently guessed at call time:

- situation        <- WorldState.surface_complaint (the plain-language
                       description of what's going on)
- key_insights      <- Judgment.primary_problem + Judgment.risks +
                       Judgment.opportunities (the assessed MEANING of
                       the situation -- what Judgment concluded, not a
                       restatement of raw WorldState content)
- current_direction <- Planner.desired_outcome (Planner's own forward-
                       facing field -- literally "the desired
                       conversational outcome," the closest existing
                       concept to "current direction")
- remaining_unknowns <- Judgment.open_unknowns (already the curated
                       subset of WorldState.unknowns Judgment determined
                       MATERIALLY affects an active goal or decision --
                       using this instead of raw WorldState.unknowns
                       avoids re-doing that filtering ourselves, which
                       would be a new judgment call, not a template)
- decisions         <- WorldState.decisions, filtered to status "open" or
                       "deferred" only (see _BRIEF_DECISION_STATUSES below
                       -- unlike Tier 1's own _DECISION_VISIBLE_STATUSES,
                       the brief's "In play"/"weighing as an option"
                       framing is only true of a decision still actually
                       being weighed; Tier 1 is a complete historical
                       record and deliberately keeps "resolved" visible,
                       but this template isn't that)

Major update (2026-07-22, see engine/decisions.md and
engine/specs/clarity-brief-specification-v1.md "The Eight Sections" --
the founder/CPO's "living model" product-direction memo): four new
sections, additive to the five above (none of the five original fields
or their mappings change, except `situation`'s SOURCE -- see below).
Every new mapping is either a direct reorganization of a field Judgment/
WorldState already produces, or (`known_facts`) a new Executor-level
template with no Judgment change at all -- same "never a new judgment
call" discipline as everything above.

- situation (SOURCE CHANGE ONLY, same field/section) <-
                       Judgment.situation_assessment, falling back to
                       Judgment.primary_problem when situation_assessment
                       is still empty (e.g. very early in a Journey,
                       before Judgment can characterize the situation's
                       own frame yet). Previously sourced from
                       WorldState.surface_complaint, which is BY
                       CONSTRUCTION a light paraphrase of the person's
                       own last message -- situation_assessment is
                       Judgment's own synthesized frame, never a copy of
                       raw WorldState content (Judgment's Governing Law
                       2: "produces conclusions, not memory"), so this is
                       a real improvement over echoing the last message,
                       not just a rename. The echo-suppression check
                       below (_SITUATION_ECHO_THRESHOLD) still runs
                       defensively against whichever text ends up here,
                       even though the new source is structurally far
                       less likely to trigger it.
- known_facts       <- WorldState.facts, filtered to status="active" and
                       capped to the _KNOWN_FACTS_CAP most-recently-
                       updated (via Provenance.last_updated) -- a NEW
                       Executor-level template, deliberately NOT a new
                       Judgment field: Judgment's own governing law is
                       "produces conclusions, not memory... never restate
                       WorldState verbatim," so a plain facts listing
                       belongs at this deterministic-template layer, same
                       as `decisions` already does. First-cut,
                       uncalibrated cap -- see clarity-brief-
                       specification-v1.md Open Question 1.
- competing_priorities <- Judgment.competing_priorities directly (new
                       Judgment field, see src/judgment/schema.py --
                       tension BETWEEN two things that are both true and
                       both matter, distinct from contradictions below).
- contradictions    <- Judgment.contradictions, with
                       Judgment.contradiction_significance appended as
                       one final entry (when non-empty) -- the "what this
                       tension implies" sentence reads naturally as the
                       last line of this section, not a separate
                       sub-section, since it only ever applies to the
                       contradictions already listed above it in the same
                       section. Confirmed via
                       test_build_clarity_brief_never_touches_judgment_key_blockers_or_active_decisions's
                       own history: contradictions was previously,
                       deliberately, never mapped at all -- this is the
                       single highest-leverage change in this rollout,
                       real backend capability that was already computed
                       every turn and already grounded, just invisible.
- emerging_patterns <- WorldState.understanding.tier2 (each
                       UnderstandingStatement's own `.text`) -- a
                       reframe, not a new build: this is the exact same
                       content already rendered today as the "Putting it
                       together" card, now folded into the Brief as its
                       own section instead of a separate adjacent panel
                       that also claims to be "the current
                       understanding." No new synthesis, no change to
                       Tier 2's own conditional-recompute gating.

Sparse-by-default holds here the same way it does throughout the
Sensemaking Engine: an empty section is a structural consequence of an
empty upstream field, not a gap Executor tries to fill.

Major update (2026-07-11, see engine/decisions.md): every field below is
passed through voice.py's `to_second_person` before being placed on
ClarityBrief. The mapping above is unchanged -- this is a voice rewrite
applied at the point of assignment, not a new source of content, so it
doesn't compromise the "fixed, design-time template" claim above.

Major update (2026-07-15, see engine/decisions.md "Frontend UX pass --
grammar/redundancy fixes"), two fixes, both still template-level (no
new judgment call, per the module's own "never reasons" claim above):

- `decisions` was a bare `to_second_person(d.content)` passthrough --
  `Decision.content` is a bare noun-phrase label ("House", "MBA"), not a
  sentence, and `to_second_person` is a documented no-op on text with no
  "user"/"they" token, so this rendered as an isolated single-word
  bullet ("In play: House / MBA"). This is the EXACT bug already fixed
  in `src/understanding/engine.py::build_tier1_statements` (Failure Mode
  #6) -- that fix only touched Tier 1's own render loop, never this
  independent one. Same sentence template applied here now.
- `situation` (WorldState.surface_complaint) is, BY CONSTRUCTION, a
  light paraphrase of whatever the person most recently said -- it will
  ALWAYS closely echo the live transcript's own last message, not just
  occasionally. Confirmed live: a real Journey's "Where things stand"
  card showed the person's own last chat message repeated back nearly
  verbatim, directly beneath the actual message. `last_user_message`
  (new, optional parameter -- callers that don't have it, e.g. any
  existing test fixture, get the old unconditional behavior) lets this
  function blank `situation` when it's a near-duplicate of that message,
  via the same word-overlap primitive `src/state/builder.py` and
  `src/interpretation/engine.py` each already independently implement
  for their own fuzzy-matching needs -- duplicated here too rather than
  imported, same "separate frozen layers" reasoning those two give for
  their own duplication (see src/interpretation/schema.py's
  GoalUpdateStatus comment).
"""

from __future__ import annotations

import re
from typing import List, Optional

from src.executor.schema import ClarityBrief
from src.executor.voice import to_second_person
from src.judgment.schema import Judgment
from src.planner.schema import Planner
from src.state.world_state import WorldState

_WORD_RE = re.compile(r"[a-z']+")


def _word_set(text: str) -> set:
    return set(_WORD_RE.findall(text.lower()))


def _word_overlap(text: str, reference: str) -> float:
    """Fraction of `text`'s words that also appear in `reference`."""
    text_words = _word_set(text)
    if not text_words:
        return 0.0
    return len(text_words & _word_set(reference)) / len(text_words)


# First-cut, uncalibrated threshold -- same "not the final word" status
# as every other fuzzy-match threshold in this codebase (e.g.
# src/state/builder.py's UNKNOWN_RESOLUTION_OVERLAP_THRESHOLD).
_SITUATION_ECHO_THRESHOLD = 0.6

# The brief's "In play" section reads as "you're weighing X as an
# option" -- only true while a decision is still actually open or
# deferred. "resolved"/"expired" decisions must not linger here forever
# (see module docstring's `decisions` mapping entry).
_BRIEF_DECISION_STATUSES = {"open", "deferred"}

# First-cut, uncalibrated -- same "not the final word" status as
# _SITUATION_ECHO_THRESHOLD above. See clarity-brief-specification-v1.md
# Open Question 1.
_KNOWN_FACTS_CAP = 5

_FACT_VISIBLE_STATUSES = {"active"}


def _select_known_facts(state: WorldState) -> List[str]:
    """Most-recently-updated active Facts, capped -- a new Executor-level
    template, not a Judgment field (see module docstring's `known_facts`
    entry)."""
    active_facts = [f for f in state.facts if f.status in _FACT_VISIBLE_STATUSES]
    active_facts.sort(
        key=lambda f: f.provenance.last_updated if f.provenance else -1,
        reverse=True,
    )
    return [to_second_person(f.content) for f in active_facts[:_KNOWN_FACTS_CAP]]


def build_clarity_brief(
    state: WorldState, judgment: Judgment, planner: Planner, last_user_message: str = "",
) -> ClarityBrief:
    situation = to_second_person(judgment.situation_assessment or judgment.primary_problem)
    if situation and last_user_message and (
        _word_overlap(situation, last_user_message) >= _SITUATION_ECHO_THRESHOLD
        or _word_overlap(last_user_message, situation) >= _SITUATION_ECHO_THRESHOLD
    ):
        situation = ""

    contradictions = [to_second_person(item) for item in judgment.contradictions]
    if judgment.contradiction_significance:
        contradictions.append(to_second_person(judgment.contradiction_significance))

    return ClarityBrief(
        situation=situation,
        key_insights=[
            to_second_person(item)
            for item in [judgment.primary_problem, *judgment.risks, *judgment.opportunities]
        ],
        current_direction=to_second_person(planner.desired_outcome),
        remaining_unknowns=[to_second_person(item) for item in judgment.open_unknowns],
        decisions=[
            f"You're weighing {to_second_person(d.content)} as an option."
            for d in state.decisions
            if d.status in _BRIEF_DECISION_STATUSES
        ],
        known_facts=_select_known_facts(state),
        competing_priorities=[to_second_person(item) for item in judgment.competing_priorities],
        contradictions=contradictions,
        emerging_patterns=[to_second_person(item.text) for item in state.understanding.tier2],
    )


def diff_clarity_briefs(previous: Optional[ClarityBrief], current: ClarityBrief) -> List[str]:
    """
    "What changed recently" (section 8, clarity-brief-specification-v1.md).
    Decided (founder/CPO, 2026-07-22): server-side, not a frontend concern
    -- "This is not a presentation concern; it's a product intelligence
    concern." Called from the same call site build_clarity_brief already
    runs from (src/api/server.py::get_clarity_brief), against
    `sessions.previous_brief_json` (the brief as of the last time this
    endpoint was called, persisted by that same call site) -- so any
    future client (mobile app, a future API consumer) gets identical
    "what changed" content, not a reimplementation of
    frontend/app/src/lib/deepeningClarity.js's own count-based JS diff
    (which this supersedes).

    A mechanical SET DIFF over the already-decided content in `current`
    vs. `previous` -- no new judgment call, same "reorganizing already-
    decided content" discipline as build_clarity_brief itself. Compared
    by membership, not position, so a reordering alone (e.g. Judgment
    listing the same two contradictions in a different sequence) is
    never reported as a change.

    `previous=None` (no prior brief exists yet -- a session's first
    completed turn) returns [] unconditionally: there is nothing to have
    changed FROM yet, not an empty-but-real diff.
    """
    if previous is None:
        return []

    changes: List[str] = []

    new_contradictions = [c for c in current.contradictions if c not in previous.contradictions]
    for c in new_contradictions:
        changes.append(f"A new contradiction surfaced: {c}")

    resolved_decisions = [d for d in previous.decisions if d not in current.decisions]
    for d in resolved_decisions:
        changes.append(f"No longer weighing this: {d}")

    resolved_unknowns = [
        u for u in previous.remaining_unknowns if u not in current.remaining_unknowns
    ]
    for u in resolved_unknowns:
        changes.append(f"This has been resolved: {u}")

    new_priorities = [
        p for p in current.competing_priorities if p not in previous.competing_priorities
    ]
    for p in new_priorities:
        changes.append(f"A new competing priority emerged: {p}")

    # emerging_patterns (Tier 2 synthesis) deliberately does NOT feed
    # "what changed" (2026-07-22, direct founder product-direction
    # redirect, see engine/decisions.md): "putting it together is not as
    # valuable... we are literally putting together my words" -- the
    # frontend no longer renders a "Putting it together" card for the
    # same reason, and resurfacing the same content through this diff
    # would just reintroduce it through a side door.

    return changes


def render_clarity_brief(brief: ClarityBrief) -> str:
    """
    Plain markdown rendering -- the actual persistent artifact a user
    would see (a document, not internal JSON). "(none)" for an empty
    section rather than an empty heading with nothing under it, so the
    document reads as complete rather than broken; this is a formatting
    choice, not a claim that something is missing that shouldn't be.
    """
    def _bullets(items):
        return "\n".join(f"- {item}" for item in items) if items else "(none)"

    return (
        "# Clarity Brief\n\n"
        "## Situation\n"
        f"{brief.situation or '(none)'}\n\n"
        "## Key Insights\n"
        f"{_bullets(brief.key_insights)}\n\n"
        "## Current Direction\n"
        f"{brief.current_direction or '(none)'}\n\n"
        "## Known Facts\n"
        f"{_bullets(brief.known_facts)}\n\n"
        "## Remaining Unknowns\n"
        f"{_bullets(brief.remaining_unknowns)}\n\n"
        "## Competing Priorities\n"
        f"{_bullets(brief.competing_priorities)}\n\n"
        "## Contradictions\n"
        f"{_bullets(brief.contradictions)}\n\n"
        "## Decisions\n"
        f"{_bullets(brief.decisions)}\n\n"
        "## Emerging Patterns\n"
        f"{_bullets(brief.emerging_patterns)}\n"
    )
