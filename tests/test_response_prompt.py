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
    assert "ONE construction, not the" in SYSTEM_PROMPT
    assert "house style" in SYSTEM_PROMPT


def test_prompt_gives_an_alternate_grounding_opening_besides_it_sounds_like():
    assert "still no read on where Sarah stands" in SYSTEM_PROMPT


def test_checklist_includes_the_repeated_opening_check():
    assert 'Does sentence 1 open with the exact same construction' in SYSTEM_PROMPT


def test_prompt_has_a_governing_law_against_repeating_a_recent_question():
    """Regression test for the second live "hardest part" regression
    (2026-07-22): even after Planner's own candidate-list filter shipped,
    Response kept independently reinventing the same generic question in
    its own words, since it never saw its own recent output."""
    assert "Never repeat a recently-asked question" in SYSTEM_PROMPT
    assert "hardest/toughest/most" in SYSTEM_PROMPT
    assert "difficult/most challenging part" in SYSTEM_PROMPT


def test_prompt_gives_the_real_observed_repeat_as_a_bad_example():
    assert "same generic shape," in SYSTEM_PROMPT
    assert "different topical dressing" in SYSTEM_PROMPT


def test_prompt_v4_bans_analytical_reflection_in_sentence_one():
    """Regression test for the founder's product-direction redirect
    (2026-07-22): "the responses right now are not valuable, the role
    of the response is to ask the still unclear questions and not
    think." Sentence 1 must become a minimal acknowledgment, not a v3-
    style analytical read of the situation."""
    assert "minimal acknowledgment, NOT reflection" in SYSTEM_PROMPT
    assert "it must" in SYSTEM_PROMPT
    assert "not characterize, interpret, or assess anything" in SYSTEM_PROMPT


def test_prompt_v4_requires_sentence_two_from_still_uncertain_content():
    assert "MUST be sourced from the highest-" in SYSTEM_PROMPT
    assert "priority entry in Judgment.open_unknowns" in SYSTEM_PROMPT
    assert "fallback ONLY" in SYSTEM_PROMPT


def test_prompt_v4_checklist_has_a_still_uncertain_sourcing_check():
    assert "did you default to a" in SYSTEM_PROMPT
    assert "generic exploratory question because nothing specific came to mind" in SYSTEM_PROMPT
