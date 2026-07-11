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
"""

from __future__ import annotations

from src.executor.schema import ClarityBrief
from src.executor.voice import to_second_person
from src.judgment.schema import Judgment
from src.planner.schema import Planner
from src.state.world_state import WorldState


def build_clarity_brief(state: WorldState, judgment: Judgment, planner: Planner) -> ClarityBrief:
    return ClarityBrief(
        situation=to_second_person(state.surface_complaint),
        key_insights=[
            to_second_person(item)
            for item in [judgment.primary_problem, *judgment.risks, *judgment.opportunities]
        ],
        current_direction=to_second_person(planner.desired_outcome),
        remaining_unknowns=[to_second_person(item) for item in judgment.open_unknowns],
        decisions=[to_second_person(d.content) for d in state.decisions],
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
