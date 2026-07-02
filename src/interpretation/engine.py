"""
Interpretation Engine -- calls a local Ollama model to turn raw user text
into a structured Interpretation.

This is the MVP provider (free, local, fast iteration on the schema).
The plan is to swap this for the Claude API once the schema stabilizes --
see engine/state_updater.py for the structured-outputs pattern that swap
should follow, and engine/decisions.md for why Ollama was chosen for now.
"""

from __future__ import annotations

import json
import re
from typing import Optional

import requests
from pydantic import ValidationError

from src.interpretation.prompt import build_messages
from src.interpretation.schema import Interpretation

OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
MODEL = "llama3.2:3b"
TEMPERATURE = 0.15  # low: this is extraction, not creative generation

# Fraction of a bias's evidence-string words that must actually appear in
# the user's own text for the bias to be kept. Bias-evidence fabrication
# (the model writing its own summary sentence instead of quoting the
# user) survived three consecutive rounds of prompt-only fixes -- see
# engine/decisions.md 2026-07-02 "v0.5" through "v0.7". This is now a
# hard code-level gate rather than another prompt request.
_BIAS_EVIDENCE_OVERLAP_THRESHOLD = 0.6
_WORD_RE = re.compile(r"[a-z']+")


def _word_set(text: str) -> set:
    return set(_WORD_RE.findall(text.lower()))


def _is_evidence_grounded(evidence: str, user_text: str) -> bool:
    """
    Rough but deterministic check: most of the evidence string's words
    must actually appear somewhere in what the user said. This won't
    catch every case of paraphrase-as-fabrication, but it reliably
    catches the pattern we've seen repeatedly: the model composing a
    fluent summary sentence instead of pointing at the user's actual
    words.
    """
    evidence_words = _word_set(evidence)
    if not evidence_words:
        return False
    user_words = _word_set(user_text)
    overlap = len(evidence_words & user_words) / len(evidence_words)
    return overlap >= _BIAS_EVIDENCE_OVERLAP_THRESHOLD


class InterpretationError(Exception):
    """Raised when the model's output can't be parsed into a valid Interpretation."""

    def __init__(self, message: str, raw_output: Optional[str] = None):
        super().__init__(message)
        self.raw_output = raw_output


def run_interpretation(user_text: str) -> Interpretation:
    system_prompt, messages = build_messages(user_text)

    try:
        response = requests.post(
            OLLAMA_CHAT_URL,
            json={
                "model": MODEL,
                "system": system_prompt,
                "messages": messages,
                "stream": False,
                # Passing the actual schema (not just the string "json")
                # constrains generation via grammar -- this is what makes
                # the output actually match Interpretation's shape, not
                # just be syntactically-valid-but-arbitrary JSON. Requires
                # Ollama >= 0.3.0. See engine/decisions.md.
                "format": Interpretation.model_json_schema(),
                "options": {"temperature": TEMPERATURE},
            },
            timeout=180,
        )
    except requests.RequestException as exc:
        raise InterpretationError(f"Ollama request failed: {exc}") from exc

    if not response.ok:
        # Ollama returns the real reason as JSON in the body -- surface it
        # instead of letting raise_for_status() discard it.
        try:
            detail = response.json().get("error", response.text)
        except ValueError:
            detail = response.text
        raise InterpretationError(
            f"Ollama returned {response.status_code}: {detail}", raw_output=response.text
        )

    try:
        raw = response.json()["message"]["content"].strip()
    except (KeyError, ValueError) as exc:
        raise InterpretationError(
            f"Unexpected Ollama response shape: {exc}", raw_output=response.text
        ) from exc

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

    return interp
