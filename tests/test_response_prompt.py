"""
Tests for src/response/prompt.py's anti-templating guidance (2026-07-22,
direct founder bug report from manual production testing: repeated "It
sounds like..." grounding sentences across turns "sounding unauthentic"
-- see engine/decisions.md "Direct question sourcing / anti-templating").

Root cause: every worked example in this prompt opened the grounding
sentence with the literal phrase "It sounds like," a strong anchoring
signal toward that one construction regardless of the STRUCTURE section's
general "vary your wording" spirit (which, before this round, only
explicitly applied to the solution-gesture rewrite case, not sentence 1's
own opening). Plain prompt-presence checks, matching this codebase's
established style for Judgment's own SYSTEM_PROMPT
(test_judgment_v3_fields.py).
"""

from __future__ import annotations

from src.response.prompt import SYSTEM_PROMPT


def test_prompt_requires_varying_sentence_one_construction():
    assert "Sentence 1's OWN construction must vary turn to turn" in SYSTEM_PROMPT


def test_prompt_names_it_sounds_like_as_one_example_not_the_house_style():
    assert "ONE example sentence, not the" in SYSTEM_PROMPT
    assert "house style" in SYSTEM_PROMPT


def test_prompt_gives_an_alternate_grounding_opening_besides_it_sounds_like():
    assert "You've mentioned Sarah a few times" in SYSTEM_PROMPT


def test_checklist_includes_the_repeated_opening_check():
    assert 'Does sentence 1 open with the exact same construction' in SYSTEM_PROMPT
