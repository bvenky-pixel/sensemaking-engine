"""
Baseline conditions for the Judgment v2 evaluation (see
engine/specs/judgment-v2-evaluation-design.md Sec. 2).

Model invariance (Sec. 1 of the design doc) requires every condition to
use the identical Judgment schema and identical system-prompt governance
(GOVERNING LAWS / FIELD DEFINITIONS / JUDGMENT MUST NOT), varying only the
*input representation*. So `_adapt_judgment_prompt` below starts from the
real `src/judgment/prompt.py` SYSTEM_PROMPT -- not a hand-copied rewrite,
which could drift or diverge in wording -- and mechanically swaps only the
opening paragraph describing what the model is given, plus the few
"WorldState"-specific references inside FIELD DEFINITIONS that only make
sense for Confidant's typed structure (e.g. "status=active in
WorldState.goals" becomes "in the input"). Everything else is
byte-identical to what Confidant's own Judgment call uses.

Baseline A (raw transcript) and Baseline B2 (incremental summary) both
produce a `Judgment` via `_run_judgment_call`, which duplicates
src/judgment/engine.py's run_judgment provider-loop/parse/validate logic
rather than importing it -- deliberately: these calls use a different
system prompt and different `component` tags, and duplicating a dozen
lines of retry/parse logic here is simpler and safer than adding
eval-only parameters to the production Judgment engine.
"""

from __future__ import annotations

import json
import re
from typing import List, Optional, Tuple

from pydantic import BaseModel, Field, ValidationError

from src.instrumentation.usage import UsageTracker, default_tracker
from src.judgment.engine import TEMPERATURE, JudgmentError
from src.judgment.prompt import SYSTEM_PROMPT as CONFIDANT_JUDGMENT_SYSTEM_PROMPT
from src.judgment.providers import ProviderCallError, call_provider, resolve_provider_chain
from src.judgment.schema import Judgment

_WORLDSTATE_FIELD_REF_RE = re.compile(r"WorldState\.\w+")

_OPENING_PARAGRAPH = (
    "You are given a WorldState -- a JSON object recording everything\n"
    "currently known about the user's world: Facts, Claims, Goals, Decisions,\n"
    "Unknowns, and Entities (each with a status), plus some working-memory\n"
    "fields (the current core question, surfaced assumptions/inferences/\n"
    "biases). You do NOT see the raw conversation. You reason only over what's\n"
    "in this WorldState."
)
_SOLE_JOB_SENTENCE = "Your sole job: given this WorldState, what conclusions are justified?"


def _adapt_judgment_prompt(input_intro: str, sole_job_clause: str, source_label: str) -> str:
    """Derive a baseline system prompt from Confidant's real Judgment
    SYSTEM_PROMPT by substitution, not rewriting -- see module docstring."""
    prompt = CONFIDANT_JUDGMENT_SYSTEM_PROMPT.replace(_OPENING_PARAGRAPH, input_intro)
    prompt = prompt.replace(_SOLE_JOB_SENTENCE, f"Your sole job: {sole_job_clause}")
    prompt = _WORLDSTATE_FIELD_REF_RE.sub("the input", prompt)
    # Longest/most-specific substrings first so e.g. "the WorldState" doesn't
    # become "the the transcript" once the bare "WorldState" replace runs.
    prompt = prompt.replace("the WorldState", f"the {source_label}")
    prompt = prompt.replace("in WorldState", f"in the {source_label}")
    prompt = prompt.replace("WorldState", source_label)
    return prompt


BASELINE_A_INTRO = (
    "You are given the full raw conversation transcript, verbatim -- every\n"
    "message the user sent, in order, turn by turn. You do NOT see any\n"
    "structured extraction or summary of it -- only the raw text of what was\n"
    "said."
)

BASELINE_B2_INTRO = (
    "You are given a plain-language running summary of the conversation so\n"
    "far, incrementally updated turn by turn as each new message arrived. You\n"
    "do NOT see the raw conversation or any structured extraction -- only\n"
    "this summary."
)


def _run_judgment_call(system_prompt: str, user_content: str, component: str, tracker: UsageTracker) -> Judgment:
    """Same provider-loop/parse/validate semantics as
    src/judgment/engine.py's run_judgment, duplicated here (see module
    docstring) so it can be pointed at a different system prompt/component
    tag without touching the production Judgment engine."""
    messages = [{"role": "user", "content": user_content}]
    schema = Judgment.model_json_schema()

    failures: List[str] = []
    for provider_name in resolve_provider_chain():
        try:
            raw = call_provider(
                provider_name, system_prompt, messages, schema, TEMPERATURE,
                component=component, tracker=tracker,
            )
        except ProviderCallError as exc:
            failures.append(f"{provider_name}: {exc}")
            continue

        raw = raw.replace("```json", "").replace("```", "").strip()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            failures.append(f"{provider_name}: model output was not valid JSON: {exc}")
            continue

        try:
            return Judgment(**data)
        except ValidationError as exc:
            failures.append(f"{provider_name}: model output failed schema validation: {exc}")
            continue

    raise JudgmentError("All configured LLM providers failed: " + "; ".join(failures))


def run_baseline_a(transcript: List[str], tracker: Optional[UsageTracker] = None) -> Tuple[Judgment, str]:
    """Baseline A -- single LLM call reasoning directly over the full raw
    transcript, same Judgment schema/governance as Confidant. Returns
    (Judgment, source_text) -- source_text is the joined transcript, used
    by src/evaluation/metrics.py to heuristically check groundedness."""
    tracker = tracker or default_tracker
    system_prompt = _adapt_judgment_prompt(
        BASELINE_A_INTRO, "given this transcript, what conclusions are justified?", "transcript"
    )
    joined = "\n".join(f"Turn {i}: {message}" for i, message in enumerate(transcript, start=1))
    judgment = _run_judgment_call(
        system_prompt, f"Conversation transcript:\n{joined}", "Baseline-A", tracker
    )
    return judgment, joined


class _SummaryUpdate(BaseModel):
    summary: str = Field(description="The updated running summary, folding in the new message.")


_SUMMARY_UPDATE_SYSTEM_PROMPT = """You maintain a running plain-language summary of an ongoing conversation.

You are given the current summary (empty on the first turn) and the
user's newest message. Fold the new message into the summary: keep
everything from the old summary that is still relevant, add whatever new
information the message contains, and update anything the new message
supersedes or clarifies. Do not comfort, coach, advise, or ask questions.
Do not invent information that isn't in the old summary or the new
message. Output ONLY a JSON object matching the required schema -- no
prose, no markdown fences.
"""


def _update_summary(summary: str, message: str, tracker: UsageTracker) -> str:
    schema = _SummaryUpdate.model_json_schema()
    messages = [
        {
            "role": "user",
            "content": f"Current summary:\n{summary or '(empty -- this is the first message)'}\n\nNew message:\n{message}",
        }
    ]

    failures: List[str] = []
    for provider_name in resolve_provider_chain():
        try:
            raw = call_provider(
                provider_name, _SUMMARY_UPDATE_SYSTEM_PROMPT, messages, schema, TEMPERATURE,
                component="Baseline-B2-summary", tracker=tracker,
            )
        except ProviderCallError as exc:
            failures.append(f"{provider_name}: {exc}")
            continue

        raw = raw.replace("```json", "").replace("```", "").strip()
        try:
            data = json.loads(raw)
            return _SummaryUpdate(**data).summary
        except (json.JSONDecodeError, ValidationError) as exc:
            failures.append(f"{provider_name}: {exc}")
            continue

    raise JudgmentError("All configured LLM providers failed to update summary: " + "; ".join(failures))


def run_baseline_b2(transcript: List[str], tracker: Optional[UsageTracker] = None) -> Tuple[Judgment, str]:
    """Baseline B2 -- incremental summary maintained turn-by-turn (never
    re-reading the full transcript), then a final Judgment-schema call
    reasoning over the last summary only. Isolates persistence-without-
    structure from Confidant's persistence-with-structure. Returns
    (Judgment, source_text) -- source_text is the final summary."""
    tracker = tracker or default_tracker
    summary = ""
    for message in transcript:
        summary = _update_summary(summary, message, tracker)

    system_prompt = _adapt_judgment_prompt(
        BASELINE_B2_INTRO, "given this summary, what conclusions are justified?", "summary"
    )
    judgment = _run_judgment_call(
        system_prompt, f"Running summary:\n{summary}", "Baseline-B2-judgment", tracker
    )
    return judgment, summary
