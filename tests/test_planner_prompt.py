"""
Tests for src/planner/prompt.py's questions_to_explore guidance
(2026-07-22, direct founder bug report from manual production testing --
see engine/decisions.md "Direct question sourcing" and
scripts/run_worldstate_walkthrough.py's own Clarity Brief output for the
same live transcript this was diagnosed against).

Root cause: questions_to_explore was documented as "internal planning
questions... NOT necessarily asked directly," with no guidance on WHEN a
concrete, already-known Judgment.open_unknown should just be surfaced
as-is. Response Generator's own STRUCTURE rule (src/response/prompt.py)
lifts the load-bearing entry from THIS list nearly verbatim into the
actual question the user reads -- so a vague internal paraphrase here
became a generic, recycled question there, instead of the specific
unresolved question WorldState already named. These are plain
prompt-presence checks, matching this codebase's established style for
Judgment's own SYSTEM_PROMPT (test_judgment_v3_fields.py).
"""

from __future__ import annotations

from src.planner.prompt import SYSTEM_PROMPT


def test_prompt_prefers_a_concrete_open_unknown_over_a_vague_paraphrase():
    assert "put THAT entry here close to verbatim" in SYSTEM_PROMPT


def test_prompt_explains_why_a_vague_paraphrase_becomes_a_generic_question():
    assert "Response Generator's" in SYSTEM_PROMPT
    assert "recycled question" in SYSTEM_PROMPT


def test_prompt_gives_a_worked_example_of_the_verbatim_preference():
    assert "Who is responsible for acknowledging" in SYSTEM_PROMPT


def test_prompt_forbids_desired_outcome_from_asserting_the_users_feelings():
    """Regression test for a real, live-observed Clarity Brief (2026-07-22,
    direct founder bug report): "You feel heard and validated regarding
    your current emotional state" rendered as the Brief's own "current
    direction" -- desired_outcome asserting the user's feelings back to
    them as an accomplished fact. Founder's own framing: "we should not
    tell the user how they feel, if they feel heard and validated they
    will tell us." """
    assert "MUST NEVER assert or presume the user's own emotional" in SYSTEM_PROMPT


def test_prompt_desired_outcome_rule_is_tense_agnostic():
    assert "in any tense" in SYSTEM_PROMPT
    assert "is still a claim" in SYSTEM_PROMPT
    assert "about their feelings, not a conversational outcome" in SYSTEM_PROMPT


def test_prompt_gives_the_real_observed_bad_example_for_desired_outcome():
    assert "User feels heard and validated regarding their current" in SYSTEM_PROMPT


def test_prompt_gives_a_good_example_for_desired_outcome():
    assert "User articulates what's been hardest about this transition." in SYSTEM_PROMPT
