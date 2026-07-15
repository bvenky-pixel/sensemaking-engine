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
- decisions         <- WorldState.decisions (every currently tracked
                       decision's content, as-is)

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


def build_clarity_brief(
    state: WorldState, judgment: Judgment, planner: Planner, last_user_message: str = "",
) -> ClarityBrief:
    situation = to_second_person(state.surface_complaint)
    if situation and last_user_message and (
        _word_overlap(situation, last_user_message) >= _SITUATION_ECHO_THRESHOLD
        or _word_overlap(last_user_message, situation) >= _SITUATION_ECHO_THRESHOLD
    ):
        situation = ""

    return ClarityBrief(
        situation=situation,
        key_insights=[
            to_second_person(item)
            for item in [judgment.primary_problem, *judgment.risks, *judgment.opportunities]
        ],
        current_direction=to_second_person(planner.desired_outcome),
        remaining_unknowns=[to_second_person(item) for item in judgment.open_unknowns],
        decisions=[
            f"You're weighing {to_second_person(d.content)} as an option." for d in state.decisions
        ],
    )


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
        "## Remaining Unknowns\n"
        f"{_bullets(brief.remaining_unknowns)}\n\n"
        "## Decisions\n"
        f"{_bullets(brief.decisions)}\n"
    )
