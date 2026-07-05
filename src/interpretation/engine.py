"""
Interpretation Engine -- calls an LLM to turn raw user text into a
structured Interpretation.

OpenRouter is the primary provider, with a local Ollama as an automatic
fallback (see src/interpretation/providers.py for the provider chain and
an important caveat: the grounding filters and thresholds below were
calibrated against Ollama/llama3.2:3b specifically -- see
engine/decisions.md for the full history and why the OpenRouter path
hasn't been through that same n=10 validation yet).
"""

from __future__ import annotations

import json
import re
from typing import Optional

from pydantic import ValidationError

from src.instrumentation.usage import UsageTracker, default_tracker
from src.interpretation.prompt import build_messages
from src.interpretation.providers import ProviderCallError, call_provider, resolve_provider_chain
from src.interpretation.schema import Interpretation

TEMPERATURE = 0.15  # low: this is extraction, not creative generation

_WORD_RE = re.compile(r"[a-z']+")


def _word_set(text: str) -> set:
    return set(_WORD_RE.findall(text.lower()))


def _word_overlap(text: str, user_text: str) -> float:
    """
    Fraction of `text`'s words that actually appear somewhere in the
    user's own words. Cheap and deterministic -- won't catch every case
    of paraphrase-as-fabrication, but reliably catches the pattern seen
    repeatedly across every failure round: the model composing a fluent
    sentence of its own instead of staying anchored to what was said.
    """
    text_words = _word_set(text)
    if not text_words:
        return 0.0
    return len(text_words & _word_set(user_text)) / len(text_words)


# Bias-evidence fabrication survived three consecutive rounds of
# prompt-only fixes -- see engine/decisions.md 2026-07-02 "v0.5"-"v0.7".
_BIAS_EVIDENCE_OVERLAP_THRESHOLD = 0.6

# Decision Options must be STRICTLY EXTRACTIVE (explicit product decision,
# 2026-07-02 recap) -- only the choices the user actually named. The
# 5-run test showed real extractive options score 0.67-1.00 overlap while
# every invented one (negotiate, HR mediation, internal roles...) scored
# 0.00-0.33. 0.5 cleanly separates them with margin on both sides.
_DECISION_OPTION_OVERLAP_THRESHOLD = 0.5

# Goals: legit goals scored 0.50-1.00 in the 5-run test; fabricated
# "helpfulness" additions ("find alternative solution", "move forward in
# career") scored 0.00-0.33. 0.4 separates cleanly.
_GOAL_OVERLAP_THRESHOLD = 0.4

# Assumptions are the hardest case: whole-sentence overlap FAILED to
# separate fabricated from real ones in the 5-run test (fabricated
# assumptions scored 0.67-0.71 because the model prefixes the invented
# reason with a restated version of the input, e.g. "my boss is not
# willing to grant me the move because [fabricated reason]" -- the
# restated preamble inflates the score and hides the fabrication in the
# tail). This directly matches the "causal permission layer" diagnosis:
# the fabrication specifically lives in the REASON the model invents for
# another person's behavior, not the whole sentence. So for assumptions
# containing a causal connector, only the clause AFTER it is checked --
# isolating just the invented reason dropped fabricated scores from
# 0.67-0.71 down to 0.00-0.43, cleanly separable at 0.45.
_ASSUMPTION_OVERLAP_THRESHOLD = 0.45
_CAUSAL_CONNECTOR = re.compile(
    r"\b(because|since|due to|as he|as she|as they)\b", flags=re.IGNORECASE
)

# v0.9: entities never had a grounding filter at all -- only possessive-
# stripping. A test run showed fabricated entities ("career coach,"
# "therapist") pulled directly from a corrupted `stakes` field in the
# same generation (see decisions.md 2026-07-02 "v0.8"). Now that stakes
# is a closed enum (impact_domains), that specific leak vector should be
# structurally closed -- this filter is a backstop, not the primary fix.
_ENTITY_OVERLAP_THRESHOLD = 0.5

# v0.9->v1.0: unknowns were consistently "career coach brainstorming next
# steps" rather than genuine gaps in the situation as stated. Pattern-
# based backstop: reject planning/advice-shaped questions outright,
# regardless of what the prompt says. Broadened after n=10 testing found
# two more real leak shapes not caught by the original pattern: "how to
# X" (no "I") and "what kind of X would be a good fit."
_PLANNING_QUESTION = re.compile(
    r"^(how (can|do|should|will) i|what should i|what (can|steps) i|"
    r"how (can|will|do) (you|we)|"
    r"how to\b|what to do\b|"
    r"what kind of .*\b(good fit|fit for)\b|"
    r"what are the (best|potential|specific)\s*(steps|risks|challenges|options|ways)\b)",
    flags=re.IGNORECASE,
)

# v0.9: found a new assumption failure shape -- the user's own full
# question dumped whole into `assumptions`. Passes the causal-clause
# grounding filter fine (it's ~100% grounded, it's literally their
# words) because the filter checks "is this grounded," not "is this the
# right tier." Two-part backstop: reject if it ends in "?" (a belief
# statement is never phrased as a question), and reject if it's
# near-identical to something already in observed_facts or
# surface_complaint (that content already has a home; duplicating it
# into assumptions isn't surfacing a new belief).
# v0.9->v1.0: lowered from 0.8 -- real n=10 data showed near-duplicate
# rewordings ("job market is weak" vs a claim reading "weak job market")
# scoring 0.75, just under the original threshold, letting an obvious
# duplicate through.
_DUPLICATE_OVERLAP_THRESHOLD = 0.7


def _is_evidence_grounded(evidence: str, user_text: str) -> bool:
    return _word_overlap(evidence, user_text) >= _BIAS_EVIDENCE_OVERLAP_THRESHOLD


def _is_option_grounded(option: str, user_text: str) -> bool:
    return _word_overlap(option, user_text) >= _DECISION_OPTION_OVERLAP_THRESHOLD


def _is_goal_grounded(goal: str, user_text: str) -> bool:
    return _word_overlap(goal, user_text) >= _GOAL_OVERLAP_THRESHOLD


def _is_entity_grounded(entity: str, user_text: str) -> bool:
    return _word_overlap(entity, user_text) >= _ENTITY_OVERLAP_THRESHOLD


def _is_planning_question(unknown: str) -> bool:
    return bool(_PLANNING_QUESTION.match(unknown.strip()))


# v1.0-candidate: the second n=10 batch showed the duplicate-tier check
# above wasn't the actual dominant failure. In 5 of 6 misfiled cases
# ("the job market is weak" landing in assumptions), there was no
# matching claims/observed_facts entry THAT TURN to deduplicate against
# at all -- the model just picked assumptions outright, with nothing to
# compare it to. The real rule needed: an assumption with NO causal
# connector (no "because"/"since"/"due to" -- i.e. no actual inference
# being made) that's near-verbatim to the user's own raw words is a bare
# restatement of a fact, not an implied belief, REGARDLESS of whether a
# sibling field happens to duplicate it this turn. This checks against
# the raw user_text directly, not sibling fields -- a genuinely different
# (and more direct) test than _is_duplicate_of_other_tier above.
_BARE_RESTATEMENT_THRESHOLD = 0.7


def _is_bare_restatement(assumption: str, user_text: str) -> bool:
    if _CAUSAL_CONNECTOR.search(assumption):
        return False  # has a causal connector -- it's making an inference, not just restating
    return _word_overlap(assumption, user_text) >= _BARE_RESTATEMENT_THRESHOLD


def _is_duplicate_of_other_tier(assumption: str, observed_facts: list, claims: list, surface_complaint: str) -> bool:
    """
    True if `assumption` is basically the same content as something
    already captured in observed_facts, claims, or surface_complaint --
    a sign it's misfiled, not a new belief. Extended to check `claims`
    after n=10 testing showed directly-stated content ("the job market
    is weak" -- something the user said outright) oscillating between
    claims and assumptions across runs on identical input. The root
    issue: the tier definitions never explicitly ruled out directly-said
    content from assumptions -- see the prompt's ASSUMPTIONS section for
    the corresponding clarification.
    """
    candidates = list(observed_facts) + list(claims) + [surface_complaint]
    return any(_word_overlap(assumption, c) >= _DUPLICATE_OVERLAP_THRESHOLD for c in candidates)


def _is_assumption_grounded(assumption: str, user_text: str) -> bool:
    """
    If the assumption invokes a causal connector ("because", "since",
    "due to"...), only the reason-clause after it needs to be grounded --
    that's specifically where fabrication hides (see module-level note
    above). Otherwise, check the whole string.
    """
    parts = _CAUSAL_CONNECTOR.split(assumption)
    clause_to_check = parts[-1] if len(parts) > 1 else assumption
    return _word_overlap(clause_to_check, user_text) >= _ASSUMPTION_OVERLAP_THRESHOLD


class InterpretationError(Exception):
    """Raised when the model's output can't be parsed into a valid Interpretation."""

    def __init__(self, message: str, raw_output: Optional[str] = None):
        super().__init__(message)
        self.raw_output = raw_output


def run_interpretation(user_text: str, tracker: Optional[UsageTracker] = None) -> Interpretation:
    """
    tracker: optional UsageTracker (src/instrumentation/usage.py) to record
    token/cost/latency into. Defaults to the shared default_tracker if not
    given -- recording itself is still a no-op unless CONFIDANT_TRACK_USAGE
    is set, so this has no effect on normal runs either way.
    """
    system_prompt, messages = build_messages(user_text)
    schema = Interpretation.model_json_schema()
    tracker = tracker or default_tracker

    raw: Optional[str] = None
    failures = []
    for provider_name in resolve_provider_chain():
        try:
            raw = call_provider(
                provider_name, system_prompt, messages, schema, TEMPERATURE,
                component="Interpretation", tracker=tracker,
            )
            break
        except ProviderCallError as exc:
            failures.append(f"{provider_name}: {exc}")
            continue

    if raw is None:
        raise InterpretationError(
            "All configured LLM providers failed: " + "; ".join(failures)
        )

    # Small models sometimes wrap JSON in fences despite instructions not to.
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise InterpretationError(f"Model output was not valid JSON: {exc}", raw_output=raw) from exc

    try:
        interp = Interpretation(**data)
    except ValidationError as exc:
        raise InterpretationError(f"Model output failed schema validation: {exc}", raw_output=raw) from exc

    interp.biases = [
        b for b in interp.biases if _is_evidence_grounded(b.evidence, user_text)
    ]
    interp.assumptions = [
        a for a in interp.assumptions
        if _is_assumption_grounded(a, user_text)
        and not a.strip().endswith("?")
        and not _is_duplicate_of_other_tier(a, interp.observed_facts, interp.claims, interp.surface_complaint)
        and not _is_bare_restatement(a, user_text)
    ]
    interp.goals = [
        g for g in interp.goals if _is_goal_grounded(g, user_text)
    ]
    interp.decision_options = [
        d for d in interp.decision_options if _is_option_grounded(d, user_text)
    ]
    interp.entities = [
        e for e in interp.entities if _is_entity_grounded(e, user_text)
    ]
    interp.unknowns = [
        u for u in interp.unknowns if not _is_planning_question(u)
    ]

    return interp
