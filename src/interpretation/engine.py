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
from typing import Optional

import requests
from pydantic import ValidationError

from src.interpretation.prompt import build_messages
from src.interpretation.schema import Interpretation

OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
MODEL = "llama3.2:3b"
TEMPERATURE = 0.15  # low: this is extraction, not creative generation


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
                "format": Interpretation.model_json_schema(),
                "options": {"temperature": TEMPERATURE},
            },
            timeout=180,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise InterpretationError(f"Ollama request failed: {exc}") from exc

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
        return Interpretation(**data)
    except ValidationError as exc:
        raise InterpretationError(f"Model output failed schema validation: {exc}", raw_output=raw) from exc
