"""
Tests for src/understanding/tier2_prompt.py's anti-paraphrase guidance
(2026-07-22, direct founder bug report from manual production testing:
"this is not really insightful it's just my statements reframed," said
of the real rendered "Putting it together" Clarity Brief section, which
is sourced from Tier 2 synthesis -- see engine/decisions.md and
src/executor/engine.py's own emerging_patterns mapping comment).

Root cause: law 3 already forbade single-candidate restatement, but the
real observed failures joined TWO candidates with a causal connector
("compounded by," "exacerbated by," "stems from") -- technically citing
two ids, but adding no information beyond what the two candidates
already said. Plain prompt-presence checks, matching this codebase's
established style for every other SYSTEM_PROMPT test.
"""

from __future__ import annotations

from src.understanding.tier2_prompt import SYSTEM_PROMPT


def test_prompt_flags_causal_connector_concatenation_as_still_a_paraphrase():
    assert "compounded by" in SYSTEM_PROMPT
    assert "is still a paraphrase, not synthesis" in SYSTEM_PROMPT


def test_prompt_gives_the_real_observed_bad_example_for_connector_concatenation():
    assert (
        "The difficulty you are experiencing coping with"
        in SYSTEM_PROMPT
    )


def test_prompt_states_the_correct_test_for_connector_concatenation():
    assert (
        "assert something a reader could NOT already get from reading the"
        in SYSTEM_PROMPT
    )
