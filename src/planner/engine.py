"""
Planner Engine v1 -- calls an LLM to turn WorldState + Judgment into a
Planner: the single highest-value conversational objective to pursue
next.

Implements engine/specs/planner-specification-v1.md. Explicit scope
decisions made before implementation (see engine/decisions.md for the
full discussion):
- Input is WorldState + Judgment ONLY -- never the raw conversation,
  Interpretation, or any previous prompt, per the spec's Inputs section.
- `phase` (Prepare/Discover/Discern/...) stays exactly where it already
  is: a separate, deterministic concern in src/judgment/engine.py's
  `recommend_phase_transition`. The Judgment v2 implementation entry in
  decisions.md flagged phase's "long-term owner" as "the future Planner,
  not expanded here" -- but this spec never mentions phase at all, so
  nothing was moved. Inventing a phase-transition responsibility for
  Planner that the spec doesn't ask for would repeat the exact mistake
  this codebase has corrected for repeatedly elsewhere (building ahead of
  a spec that doesn't call for it yet).
- This is a full LLM call, not a rule engine -- same "one call, one
  schema" simplicity already chosen for Judgment v2, for the same reason:
  every field, including ones that look like plain selection
  (priority_topics, assumptions_to_test), comes from one structured-output
  call over WorldState + Judgment together.
"""

from __future__ import annotations

import json
import re
from typing import List, Optional, Tuple

from pydantic import ValidationError

from src.instrumentation.usage import AttemptRecord, UsageTracker, default_tracker
from src.judgment.schema import Judgment
from src.llm.providers import ProviderCallError, call_provider, resolve_provider_chain
from src.orchestrator.modes import planner_mode_focus_note
from src.planner.prompt import build_messages
from src.planner.schema import Planner
from src.state.world_state import PROMPT_EXCLUDED_FIELDS, WorldState

TEMPERATURE = 0.15  # low: this is assessment/planning, not creative generation


class PlannerError(Exception):
    """Raised when no configured provider could produce a valid Planner."""

    def __init__(self, message: str, raw_output: Optional[str] = None):
        super().__init__(message)
        self.raw_output = raw_output


def run_planner(
    state: WorldState, judgment: Judgment, tracker: Optional[UsageTracker] = None,
    mode: Optional[str] = None,
) -> Planner:
    """
    Calls an LLM to produce a Planner from the given WorldState and
    Judgment. Tries each configured provider in order (see
    src/llm/providers.py -- OpenRouter is the only registered provider
    today, same as Interpretation and Judgment). Raises PlannerError if
    every provider fails.

    Callers should call this AFTER run_judgment, on the same Judgment
    object -- Planner's rationale is required to reference Judgment, so
    it needs a real Judgment, not a stale or placeholder one.

    tracker: optional UsageTracker (src/instrumentation/usage.py) to record
    token/cost/latency into. Defaults to the shared default_tracker if not
    given -- recording itself is still a no-op unless CONFIDANT_TRACK_USAGE
    is set, so this has no effect on normal runs either way.

    mode: optional Counseling mode id (see src/orchestrator/modes.py),
    the raw session-level value -- resolved to its prompt-injection note
    here (via planner_mode_focus_note), not by the caller, so every caller of
    run_planner passes the same raw id run_response_generator does,
    rather than each resolving it independently.
    """
    world_state_json = state.model_dump_json(indent=2, exclude=PROMPT_EXCLUDED_FIELDS)
    judgment_json = judgment.model_dump_json(indent=2)
    system_prompt, messages = build_messages(world_state_json, judgment_json, planner_mode_focus_note(mode))
    schema = Planner.model_json_schema()
    tracker = tracker or default_tracker

    failures: List[str] = []
    for provider_name in resolve_provider_chain():
        try:
            raw = call_provider(
                provider_name, system_prompt, messages, schema, TEMPERATURE,
                component="Planner", tracker=tracker,
            )
        except ProviderCallError as exc:
            failures.append(f"{provider_name}: {exc}")
            tracker.record_outcome(AttemptRecord(
                component="Planner", provider=provider_name,
                outcome="provider_call_error", detail=str(exc),
            ))
            continue

        raw = raw.replace("```json", "").replace("```", "").strip()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            failures.append(f"{provider_name}: model output was not valid JSON: {exc}")
            tracker.record_outcome(AttemptRecord(
                component="Planner", provider=provider_name,
                outcome="invalid_json", detail=str(exc),
            ))
            continue

        try:
            result = Planner(**data)
        except ValidationError as exc:
            failures.append(f"{provider_name}: model output failed schema validation: {exc}")
            tracker.record_outcome(AttemptRecord(
                component="Planner", provider=provider_name,
                outcome="schema_validation_failed", detail=str(exc),
            ))
            continue

        tracker.record_outcome(AttemptRecord(
            component="Planner", provider=provider_name, outcome="success",
        ))
        return result

    raise PlannerError("All configured LLM providers failed: " + "; ".join(failures))


# Leaked-id mechanical backstop (2026-07-22): a live 11-turn walkthrough
# dispatch (the same run that validated the repeated-question filter
# below) caught Planner echoing a raw WorldState item id back into
# questions_to_explore verbatim -- e.g. "...explanation? (id:
# 51eef282-70f4-45db-97fa-58270a357492)" -- despite src/planner/prompt.py's
# own explicit law against it (added the same round as the analogous
# Tier2/Judgment/Response guards, see engine/decisions.md). Same "prompt
# alone isn't enough" lesson as the repeated-question filter below,
# applied here to the id-leak case specifically -- real, live-observed,
# not a hypothetical.
_LEAKED_ID_RE = re.compile(
    r"\s*\(\s*id:\s*[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\s*\)"
)


def _strip_leaked_id(text: str) -> str:
    return _LEAKED_ID_RE.sub("", text).strip()


def strip_leaked_ids(planner: Planner) -> Planner:
    """Strips a "(id: <uuid>)"-shaped suffix from every free-text field
    Response might carry through toward the user largely as-is."""
    return planner.model_copy(update={
        "primary_objective": _strip_leaked_id(planner.primary_objective),
        "rationale": _strip_leaked_id(planner.rationale),
        "resolution_blocker": _strip_leaked_id(planner.resolution_blocker),
        "priority_topics": [_strip_leaked_id(t) for t in planner.priority_topics],
        "questions_to_explore": [_strip_leaked_id(q) for q in planner.questions_to_explore],
        "assumptions_to_test": [_strip_leaked_id(a) for a in planner.assumptions_to_test],
        "planning_constraints": [_strip_leaked_id(c) for c in planner.planning_constraints],
        "desired_outcome": _strip_leaked_id(planner.desired_outcome),
    })


# Repeated-question mechanical backstop (2026-07-22, direct founder
# feedback: conversations felt "repetitive... asked the same questions
# again and again" -- see engine/decisions.md). The prompt-only mandatory
# rule added alongside this (src/planner/prompt.py -- don't re-select a
# question Judgment.stagnation_notes just flagged as stuck) was live-
# dispatched against the real 11-turn walkthrough transcript BEFORE this
# function existed: compliance was inconsistent, and one specific
# question ("What are Sarah's potential reasons for not giving a clear
# explanation?") recurred VERBATIM in 6 of 11 turns' questions_to_explore
# regardless of the prompt rule, including turns where Judgment had
# already flagged it as stagnant. This is the exact "detected but didn't
# act on it" compliance gap this codebase has hit repeatedly elsewhere
# (has_risk_signal, has_decision_resolution, grounding_item_ids) -- every
# prior instance was fixed with mechanical, code-level enforcement
# backing the prompt, never by wording the prompt harder alone. This is
# that enforcement, specifically for questions_to_explore.
#
# Deliberately NOT keyed off Judgment.stagnation_notes at all -- a plain
# "was this near-identical question already asked recently" check is
# simpler, doesn't depend on Judgment's own synthesis correctly flagging
# the repeat, and catches a repeat Judgment might miss just as well as
# one it flags.
_QUESTION_WORD_RE = re.compile(r"[a-z]+")


def _question_word_set(text: str) -> set:
    return set(_QUESTION_WORD_RE.findall(text.lower()))


def _question_overlap(a: str, b: str) -> float:
    """Larger of (shared words / len(a)) and (shared words / len(b)) --
    catches a reworded near-duplicate AND a shorter question fully
    contained in a longer one, either direction. Same "first-cut,
    uncalibrated threshold" status as every other fuzzy-match constant in
    this codebase (e.g. UNKNOWN_RESOLUTION_OVERLAP_THRESHOLD,
    _SITUATION_ECHO_THRESHOLD)."""
    words_a, words_b = _question_word_set(a), _question_word_set(b)
    if not words_a or not words_b:
        return 0.0
    shared = len(words_a & words_b)
    return max(shared / len(words_a), shared / len(words_b))


REPEATED_QUESTION_OVERLAP_THRESHOLD = 0.7

# Second-round live-observed gap (2026-07-22, direct founder bug report
# from manual production testing, after the round above had already
# shipped): a fresh transcript showed "What's been the hardest part
# about it lately?" recur, reworded, three times across seven turns
# ("...the hardest part of this situation for you right now?", "...the
# hardest part of adjusting to this new dynamic?"). Computed directly
# against these real strings, _question_overlap scores these pairs at
# 0.556-0.667 -- BELOW REPEATED_QUESTION_OVERLAP_THRESHOLD, so the
# existing filter let all of them through.
#
# The fix is deliberately NOT a lower threshold: an initial attempt at
# 0.55 also caught "What steps has the user taken to move to the
# Product team?" vs. "What is preventing the user from moving to the
# Product team?" as a false-positive duplicate (0.6 overlap) -- two
# genuinely different questions that happen to share a narrow topic's
# vocabulary (test_genuinely_different_question_is_kept's own sibling
# case). Plain word-overlap cannot safely distinguish "the same generic
# question reworded" from "two different questions sharing a subject"
# at any single global threshold, because a narrow topic's own shared
# nouns can push overlap just as high as a genuine repeat.
#
# Instead: a second, narrower, orthogonal check specifically for a
# recognizable GENERIC scaffolding shape -- "what's the
# hardest/toughest/most difficult part," independent of subject matter
# -- since this exact shape is what recurred live, and it carries no
# topic-specific content that could produce a legitimate reason to ask
# it twice with different wording. Deliberately narrow (this one
# pattern, not a general meta-question detector) rather than broad and
# risky.
_GENERIC_DIFFICULTY_QUESTION_RE = re.compile(
    r"\b(hardest|toughest|most difficult|most challenging)\b.{0,40}\bpart\b"
    r"|\bpart\b.{0,40}\b(hardest|toughest|most difficult|most challenging)\b",
    re.IGNORECASE,
)


def _is_generic_difficulty_question(text: str) -> bool:
    return bool(_GENERIC_DIFFICULTY_QUESTION_RE.search(text))


# How many of the most recently-produced questions stay eligible to
# match against -- unbounded growth would make every turn's filtering
# slower for no real benefit, and a question asked many turns ago is no
# longer what's actually driving a "didn't we already ask this" feeling
# this turn.
RECENT_QUESTIONS_WINDOW = 20


def apply_repeated_question_filter(
    state: WorldState, planner: Planner
) -> Tuple[Planner, List[str]]:
    """
    Drops any question from planner.questions_to_explore that's a near-
    duplicate (see REPEATED_QUESTION_OVERLAP_THRESHOLD) of a question
    already produced in a recent prior turn (state.recent_planner_questions),
    OR that matches the same generic difficulty-question shape (see
    _GENERIC_DIFFICULTY_QUESTION_RE) as one already produced -- this
    second check exists because that one recognizable shape ("what's the
    hardest/toughest part") recurred, reworded, in a real conversation at
    a word-overlap score below what a globally safe threshold can catch
    (see that regex's own comment for why a lower global threshold isn't
    the fix).

    Returns (filtered_planner, updated_recent_questions) -- this function
    does NOT mutate WorldState itself, matching run_planner's own pure-
    function contract above; the caller (src/orchestrator/engine.py) is
    responsible for writing updated_recent_questions back onto
    state.recent_planner_questions.
    """
    seen = state.recent_planner_questions
    seen_has_generic_difficulty_question = any(_is_generic_difficulty_question(q) for q in seen)
    kept = [
        q for q in planner.questions_to_explore
        if not any(_question_overlap(q, prior) >= REPEATED_QUESTION_OVERLAP_THRESHOLD for prior in seen)
        and not (seen_has_generic_difficulty_question and _is_generic_difficulty_question(q))
    ]
    filtered_planner = planner.model_copy(update={"questions_to_explore": kept})
    updated_recent = (seen + kept)[-RECENT_QUESTIONS_WINDOW:]
    return filtered_planner, updated_recent
