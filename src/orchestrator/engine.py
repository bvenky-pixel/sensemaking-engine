"""
Orchestrator v1 -- coordinates one turn through the Sensemaking Engine
pipeline. First real System Architecture v2 component built after
Instrumentation (see engine/decisions.md).

Implements the Orchestrator section of
engine/specs/system-architecture-v2-specification.md, scoped down
deliberately, same discipline as every other "build X" task on this
branch:

BUILT: sequencing/coordination (which processes run, in what order) and
stage-level recovery (if a stage fails, stop the turn and report exactly
how far it got, including whatever state/artifacts earlier stages
already produced). This was previously duplicated, inline, in two driver
scripts (conversation_runner.py, scripts/run_worldstate_walkthrough.py)
-- extracting it here doesn't invent new behavior, it gives already-
working coordination logic one tested, shared home, and fixes a real
correctness bug found in the process (see TurnResult's docstring).

NOT built, deliberately deferred (named in the spec, no implementation
here yet, same as Learning's status):
- "Skipping unnecessary computation" (e.g. skip Judgment if Interpretation
  produced nothing new) -- no evidence yet that this optimization is
  needed, and the spec's own restriction ("skip logic must stay
  mechanical/structural, never semantic") means this would need a real
  structural trigger design, not a guess.
- "Selecting models" as interaction-level policy (e.g. a stronger model
  tier for a higher-stakes turn) -- no criteria for "higher-stakes"
  exists anywhere in this codebase today; inventing one now would be
  exactly the kind of ungrounded capability this project avoids building
  ahead of evidence.
- "Managing retries" beyond the stage-level stop-and-report done here --
  there's no evidence yet that retrying a whole failed stage (as opposed
  to the call-level provider fallback each engine already does) would
  help; the call-level retry/fallback chain already lives in
  src/llm/providers.py and stays there, per the spec's explicit scope
  boundary.

BOUNDED SINGLE-STAGE RETRY (2026-07-19, backlog #250, see
engine/decisions.md "Orchestrator: bounded single-stage retry" -- the
founder's own explicit choice, distinct from the "managing retries"
non-goal above, which still holds for anything beyond this): each of
the four stages now gets exactly ONE additional attempt, at the stage
level, if its first attempt raises that stage's own *Error -- i.e. only
after `src/llm/providers.py`'s own call-level fallback has already
exhausted every configured provider once. A transient failure isn't
guaranteed to repeat on a second, fully independent attempt, so this
recovers some turns the old stop-immediately behavior would have failed
outright. Still bounded to exactly one retry, never a loop, never a
retry of the whole turn or of stages that already succeeded -- if the
SECOND attempt also raises, that exception propagates to this
function's own except clause exactly as before, and the turn still
fails honestly. See `_with_bounded_retry` below.

Orchestrator never performs user reasoning: it only sequences calls and
reports what happened, never judging what any stage's output means.
"""

from __future__ import annotations

from typing import Callable, List, Optional, Type, TypeVar

T = TypeVar("T")

from src.insight.schema import Insight
from src.instrumentation.events import diff_behavioral_events
from src.instrumentation.usage import UsageTracker, default_tracker
from src.interpretation.engine import InterpretationError, run_interpretation
from src.judgment.engine import JudgmentError, recommend_phase_transition, run_judgment
from src.orchestrator.schema import TurnResult
from src.planner.engine import PlannerError, apply_repeated_question_filter, run_planner
from src.pom.schema import PersonalOperatingModel
from src.response.engine import ResponseGeneratorError, run_response_generator
from src.response.schema import Response
from src.state.builder import apply_judgment_resolutions, apply_knowledge_corrections, update_state
from src.state.world_state import WorldState
from src.understanding.engine import build_tier1_statements
from src.understanding.tier2_engine import update_tier2


def _with_bounded_retry(run_stage: Callable[[], T], error_type: Type[Exception]) -> T:
    """Calls `run_stage()`, retrying exactly once more if the FIRST call
    raises `error_type` (backlog #250 -- see this module's own docstring).
    The second attempt's exception, if it also raises, propagates
    unchanged -- this never swallows a genuine total failure, it only
    delays reporting it by one independent attempt at the same stage."""
    try:
        return run_stage()
    except error_type:
        return run_stage()


def run_turn(
    message: str,
    state: WorldState,
    tracker: Optional[UsageTracker] = None,
    session_id: str = "",
    on_stage_complete: Optional[Callable[[str], None]] = None,
    mode: Optional[str] = None,
    retrieved_context: str = "",
    pom: Optional[PersonalOperatingModel] = None,
    insights: Optional[List[Insight]] = None,
    run_tier2: bool = True,
    on_response_token: Optional[Callable[[str], None]] = None,
) -> TurnResult:
    """
    Runs one turn through the fixed pipeline: Interpretation ->
    WorldState update/phase -> Judgment -> Planner -> Response Generator.
    This is the only order the Sensemaking Engine spec supports today --
    each stage's input is the previous stage's committed output, so
    there's no reordering or parallelism to decide between yet.

    Stops at the first stage that fails and returns immediately,
    reporting `failed_stage` and `error` -- but every stage that already
    succeeded before that point is still reflected in the returned
    TurnResult (`state`, and whichever of `interpretation`/`judgment`/
    `planner` already completed). Never raises -- a failure at any stage
    is data (a TurnResult), not an exception the caller has to catch.

    tracker: optional UsageTracker, passed through to every stage
    unchanged -- Orchestrator doesn't own instrumentation, it just makes
    sure every stage it calls gets the same one.

    session_id: optional, defaults to "" for every existing caller that
    doesn't pass one (conversation_runner.py, scripts/run_worldstate_walkthrough.py,
    tests) -- only used to stamp Phase 1 Learning's behavioral_events
    (see src/instrumentation/events.py), never anything upstream of that.

    on_stage_complete: optional callback invoked once, synchronously,
    immediately after each stage's try/except block succeeds, with that
    stage's internal id ("interpretation"/"judgment"/"planner"/
    "response"). Default None is a true no-op -- every existing caller
    is unaffected. Added for real-time streaming (see src/api/server.py's
    GET /sessions/{id}/stream, engine/decisions.md "Major update") --
    a callback, not a generator, so this function's `result = run_turn(...)`
    contract stays unchanged for every other caller.

    mode: optional Counseling mode id (see src/orchestrator/modes.py),
    chosen once at session creation and passed through unchanged on
    every subsequent turn (src/api/server.py fetches it from the
    session's own db row) -- Orchestrator only threads it to run_planner
    and run_response_generator, the two stages whose prompts actually
    reference it; Interpretation and Judgment are unaffected, same
    reasoning as `phase` staying entirely their own concern elsewhere.
    Default None is a true no-op for every existing caller.

    Synthesis (2026-07-16, see engine/decisions.md "Synthesis"): when
    mode == "adaptive", Planner itself chooses which of the five concrete
    lenses fits THIS TURN and reports it on `plan.active_lens` -- Response
    must be given THAT concrete lens, not the literal string "adaptive"
    (which has no entry of its own in RESPONSE_MODE_FOCUS), so it reuses
    the same, already-tuned focus text a Journey fixed to that lens from
    the start would get. Every other mode's `effective_mode` is just
    `mode` unchanged -- `plan.active_lens` is only ever set when Planner
    was actually asked to choose one.

    retrieved_context: optional, already-formatted Retrieval output (see
    src/retrieval/engine.py::build_retrieved_context and
    engine/decisions.md "Retrieval") -- Orchestrator threads it ONLY to
    run_judgment, the one stage whose prompt references it; Interpretation
    never sees it (per its own "no memory across turns" scope), and
    Planner/Response only ever see it indirectly, through whatever
    Judgment itself chooses to surface in supporting_evidence. Default ""
    is a true no-op for every existing caller.

    pom: this account's own current PersonalOperatingModel, or None for
    an anonymous caller / an account whose POM has never been computed
    (2026-07-18, see engine/decisions.md "POM early seeding:
    thinnest-system-aware targeting") -- Orchestrator threads it ONLY to
    run_response_generator, which uses it (alongside `state.turn_count`)
    to decide whether that mode's POM-seeding clause should fire this
    turn; every other stage is unaffected. Default None is a true no-op
    for every existing caller.

    insights: this account's own computed Insights (2026-07-19, backlog
    #210, see engine/decisions.md "POM: Insight-triggered conversational
    callback") -- Orchestrator threads it ONLY to run_response_generator,
    same as `pom` above; every other stage is unaffected. Default None
    is a true no-op for every existing caller.

    run_tier2: whether this call should compute Tier2 itself (2026-07-22,
    backlog #235, see engine/decisions.md "Tier2 moved off the
    critical path"). Default True preserves every existing caller's
    behavior unchanged (conversation_runner.py, scripts/run_worldstate_
    walkthrough.py, tests). src/api/server.py is the one caller that
    passes False: Tier2 has no data dependency on Planner/Response (it
    only ever reads WorldState, confirmed via
    src/understanding/tier2_engine.py's own module docstring) and
    nothing downstream of it -- Planner, Response -- reads its output
    either, so there was never a real reason for its LLM call (4-14s
    observed live) to block the user's response. When False, `state` is
    returned with whatever Tier2 the PREVIOUS turn already computed
    still in place (exactly the staleness the frontend's Clarity Brief
    already tolerates for one whole turn by design, see backlog #236) --
    the caller is expected to invoke update_tier2 itself afterward,
    off the response path.

    on_response_token: optional callback invoked with each raw text
    fragment of `response_text` AS IT'S GENERATED (2026-07-22, backlog
    #233, see engine/decisions.md "Stream Response text token-by-token"
    and src/response/streaming.py's own docstring for how the fragment
    boundaries are chosen). Threaded ONLY to run_response_generator --
    every earlier stage's own call stays fully synchronous/non-streaming,
    since Response is the only stage whose output a person actually
    reads. Default None is a true no-op for every existing caller
    (conversation_runner.py, scripts/run_worldstate_walkthrough.py,
    tests) -- src/api/server.py is the only caller that passes one.
    """
    tracker = tracker or default_tracker
    behavioral_events = []

    def _notify(stage: str) -> None:
        if on_stage_complete is not None:
            on_stage_complete(stage)

    try:
        interp = _with_bounded_retry(
            lambda: run_interpretation(message, tracker=tracker), InterpretationError
        )
    except InterpretationError as exc:
        return TurnResult(state=state, failed_stage="interpretation", error=str(exc))
    _notify("interpretation")

    # WorldState must be updated with this turn's Interpretation BEFORE
    # Judgment runs -- Judgment only ever sees WorldState, never the raw
    # Interpretation. Once this commits, `state` genuinely has changed,
    # regardless of what happens next.
    pre_update_state = state
    state = update_state(state, interp)
    behavioral_events += diff_behavioral_events(
        pre_update_state, state, session_id=session_id, turn=state.turn_count
    )
    next_phase = recommend_phase_transition(state)
    if next_phase:
        state.phase = next_phase

    # Added 2026-07-12 (see engine/decisions.md "Understanding layer --
    # Journey-scoped identity"): Tier 1 is a pure, deterministic template
    # over WorldState's own knowledge items -- same discipline as
    # recommend_phase_transition just above (cheap, WorldState-only,
    # always executed regardless of what Judgment/Planner/Response later
    # do). Deliberately NOT gated behind a try/except -- unlike the four
    # real pipeline stages below, this has no external call and no
    # failure mode worth guarding against.
    state.understanding.tier1 = build_tier1_statements(state)

    try:
        judgment = _with_bounded_retry(
            lambda: run_judgment(state, tracker=tracker, retrieved_context=retrieved_context),
            JudgmentError,
        )
    except JudgmentError as exc:
        return TurnResult(
            state=state, interpretation=interp, failed_stage="judgment", error=str(exc),
            behavioral_events=behavioral_events,
        )
    _notify("judgment")

    # Judgment itself never writes to WorldState (it only ever reads it,
    # per its own design principles) -- this and apply_knowledge_corrections
    # just below are the two deliberate, narrowly-scoped write-back
    # exceptions (2026-07-19, see engine/decisions.md "Judgment write-back:
    # confirmed as case-by-case policy", backlog #247 -- the founder
    # confirmed case-by-case exceptions, not a general write-back
    # mechanism, as the ongoing policy). This one turns Judgment's
    # decision_resolutions assessment into an actual WorldState.decisions
    # status update, so this turn's Planner/Response (and every later
    # turn) see the corrected status instead of it staying silently stuck
    # at "open". See engine/decisions.md "decision lifecycle, round 3".
    pre_resolution_state = state
    state = apply_judgment_resolutions(state, judgment)
    behavioral_events += diff_behavioral_events(
        pre_resolution_state, state, session_id=session_id, turn=state.turn_count
    )

    # The second of the two write-back exceptions (see comment above),
    # for the two knowledge tiers (Fact/Claim) that never had a
    # correction pathway at all -- see engine/decisions.md "Fact/Claim
    # correction and near-duplicate consolidation".
    pre_correction_state = state
    state = apply_knowledge_corrections(state, judgment)
    behavioral_events += diff_behavioral_events(
        pre_correction_state, state, session_id=session_id, turn=state.turn_count
    )

    # Added 2026-07-15 (see engine/decisions.md "Tier 2 design" and
    # src/understanding/tier2_engine.py's own module docstring): unlike
    # Tier 1 above, this is CONDITIONAL (most turns skip the LLM call
    # entirely -- see should_recompute_tier2) and NON-BLOCKING (any
    # failure inside update_tier2 is already caught there; it returns
    # state unchanged rather than raising). Placed here, not after
    # Planner/Response, because Tier 2 only depends on WorldState
    # (already fully updated by the corrections above) -- it doesn't
    # need Planner/Response to have run, so it still gets a chance to
    # update even on a turn where one of those two later fails.
    if run_tier2:
        state = update_tier2(state, tracker=tracker)

    try:
        plan = _with_bounded_retry(
            lambda: run_planner(state, judgment, tracker=tracker, mode=mode), PlannerError
        )
    except PlannerError as exc:
        return TurnResult(
            state=state, interpretation=interp, judgment=judgment,
            failed_stage="planner", error=str(exc),
            behavioral_events=behavioral_events,
        )
    _notify("planner")

    # Repeated-question mechanical backstop (2026-07-22, see
    # src/planner/engine.py::apply_repeated_question_filter's own
    # docstring) -- applied here, not inside run_planner, so run_planner
    # stays a pure "call the LLM" function; this is the one step that
    # both reads AND writes WorldState (recent_planner_questions), same
    # "explicit state in, state out" shape as update_tier2 above.
    plan, recent_questions = apply_repeated_question_filter(state, plan)
    state = state.model_copy(update={"recent_planner_questions": recent_questions})

    # Synthesis (see mode's own docstring paragraph above): Adaptive
    # mode's per-turn lens choice lives on `plan.active_lens`, not on
    # `mode` itself -- resolve it here, once, so Response gets whichever
    # concrete lens Planner actually chose this turn.
    effective_mode = plan.active_lens if mode == "adaptive" and plan.active_lens else mode

    # on_response_token (2026-07-22, backlog #233, see engine/decisions.md
    # "Stream Response text token-by-token"): only the FIRST attempt gets
    # the real callback -- _with_bounded_retry can call run_stage() a
    # second time if the first raises ResponseGeneratorError (e.g. a
    # streamed response that failed schema validation), and a retry's
    # tokens would otherwise land on top of whatever partial text the
    # failed first attempt already streamed, showing the person a
    # garbled mix of two different draft responses. A retry silently
    # falls back to non-streaming instead -- rare (provider failure),
    # and the eventual POST /messages response is unaffected either way.
    _response_attempt_count = {"n": 0}

    def _run_response() -> Response:
        _response_attempt_count["n"] += 1
        # `on_token` only added to this call's kwargs when actually
        # streaming -- every existing caller/test double that mocks
        # run_response_generator with its pre-#233 signature keeps
        # working unchanged, since a non-streaming call looks identical
        # to before.
        call_kwargs = {}
        if on_response_token is not None and _response_attempt_count["n"] == 1:
            call_kwargs["on_token"] = on_response_token
        return run_response_generator(
            state, judgment, plan, tracker=tracker, mode=effective_mode, pom=pom, insights=insights,
            **call_kwargs,
        )

    try:
        response = _with_bounded_retry(_run_response, ResponseGeneratorError)
    except ResponseGeneratorError as exc:
        return TurnResult(
            state=state, interpretation=interp, judgment=judgment, planner=plan,
            failed_stage="response", error=str(exc),
            behavioral_events=behavioral_events,
        )
    _notify("response")

    return TurnResult(
        state=state, interpretation=interp, judgment=judgment, planner=plan, response=response,
        behavioral_events=behavioral_events,
    )
