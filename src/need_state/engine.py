"""
Need State Inference v1 -- the vision doc's Layer 7 (see
engine/specs/architecture-roadmap-v1.md, engine/decisions.md
"Need State Inference"). Must run BEFORE Retrieval, which feeds
Judgment -- unlike Synthesis's `active_lens` (chosen inside Planner's
own call, which runs AFTER Retrieval/Judgment), there is no existing
LLM call already happening at the right point in the pipeline to fold
this into for free.

Two design forks existed here (mechanical vs. a new LLM call; label-only
vs. actually filtering Retrieval's output). Originally decided without
founder confirmation -- AskUserQuestion was attempted twice at build
time and both attempts failed with a tool-level stream error rather than
a user response, so the implementer proceeded on best judgment rather
than block indefinitely. **Both forks were later put directly to the
founder (2026-07-19, backlog #224/#225, see engine/decisions.md) and
CONFIRMED as the right calls** -- this is no longer an unconfirmed,
override-if-wanted placeholder; it's the founder's own deliberate
choice.

Chosen and confirmed: **deterministic, no new LLM call** -- a pure
function over already-existing WorldState signals, same trusted category
as src/judgment/engine.py::compute_stagnation_signals and
recommend_phase_transition (mechanical, not a judgment call). A real
LLM-based inference step would be the vision's more faithful design, but
is exactly the "invent a scored model with no evidence to calibrate it
against" risk this project's own roadmap doc flags for this specific
layer -- and it would add a new LLM call, hence cost, to every turn.
This can be revisited once real usage exists to justify and calibrate a
learned version; nothing here forecloses that.

The stagnation-gap arithmetic below is intentionally duplicated from
compute_stagnation_signals rather than imported -- same "small utility
functions deliberately duplicated across modules, not shared" convention
already established (see src/orchestrator/modes.py's own module
docstring on why Planner/Response's focus notes aren't merged into one).
"""

from __future__ import annotations

from src.need_state.schema import NeedState
from src.state.world_state import WorldState

# Mirrors src/judgment/engine.py's STAGNATION_TURN_THRESHOLD -- same
# "not empirically calibrated yet" honesty applies here too.
_STAGNATION_TURN_THRESHOLD = 3


def infer_need_state(state: WorldState, threshold: int = _STAGNATION_TURN_THRESHOLD) -> NeedState:
    """
    Deterministic classification over WorldState only -- no Judgment
    input, since this must run before Judgment (Retrieval feeds
    Judgment, and this gates/labels what Retrieval surfaces). Checked in
    priority order, each one a real, already-established signal
    elsewhere in this codebase:

    1. `accountability` -- a Goal or Decision has gone `threshold`+ turns
       without a status change (same signal Commit mode and Judgment's
       own stagnation_notes already act on). Checked first: a stalled
       item is a more urgent need than an open-but-fresh one.
    2. `decision` -- an open Decision exists, not yet stagnant. Mirrors
       Strategize mode's own criterion (decision_options/active_decisions
       present).
    3. `reflection` -- at least one Goal with status="active" exists,
       but nothing above fired. There's something to weigh the situation
       against, even without a sharper signal. Scoped to "active" only --
       same convention as compute_stagnation_signals: a paused/completed/
       abandoned Goal isn't neglected, it's already been accounted for,
       so it shouldn't drive a "reflection" need on its own.
    4. `general` -- none of the above; too little structure yet to infer
       anything more specific (e.g. a brand-new Journey).

    Never invents a need beyond what's structurally present -- a Journey
    with nothing yet correctly returns "general", not a guessed need.
    """
    for goal in state.goals:
        if goal.status == "active" and goal.provenance is not None:
            if state.turn_count - goal.provenance.last_updated >= threshold:
                return "accountability"
    for decision in state.decisions:
        if decision.status == "open" and decision.provenance is not None:
            if state.turn_count - decision.provenance.last_updated >= threshold:
                return "accountability"

    for decision in state.decisions:
        if decision.status == "open":
            return "decision"

    if any(goal.status == "active" for goal in state.goals):
        return "reflection"

    return "general"
