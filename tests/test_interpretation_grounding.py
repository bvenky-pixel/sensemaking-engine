"""
Tests for src/interpretation/engine.py's deterministic grounding filters
-- pure Python, no LLM calls, first dedicated coverage these functions
have ever had (previously only exercised indirectly via live LLM runs;
see engine/decisions.md's multi-round hardening history).

Written for Interpretation v2 Priority 1 (see engine/decisions.md
"Interpretation v2 Priority 1"): a plan-review pass found that v2's own
drafted worked examples for the ASSUMPTIONS/GOALS prompt sections would
have been silently stripped by the existing word-overlap grounding
filters -- the same failure shape as the documented A04 assumption_check
saga. `_CAUSAL_CONNECTOR` was extended (implies/indicates/reflects/
suggests) and the affected examples reworded to retain more of the
user's own words; these tests confirm both survive, and that the
original fabrication-catching behavior the filters exist for is
unchanged.
"""

from __future__ import annotations

from src.interpretation.engine import _is_assumption_grounded, _is_goal_grounded


def test_reworded_assumption_examples_pass_grounding():
    """The exact three assumption examples shipped in
    src/interpretation/prompt.py's ASSUMPTIONS section, reworded from
    v2's original drafts to survive _ASSUMPTION_OVERLAP_THRESHOLD."""
    cases = [
        (
            "Silence implies the friend is angry.",
            "My friend hasn't replied in three days. I think they're angry.",
        ),
        (
            "The promotion outcome reflects how much my manager values me.",
            "I wasn't promoted. My manager must not value me.",
        ),
        (
            "Disagreement implies the co-founder doesn't trust me.",
            "My co-founder disagreed with me. He clearly doesn't trust me.",
        ),
    ]
    for assumption, user_text in cases:
        assert _is_assumption_grounded(assumption, user_text), assumption


def test_reworded_goal_example_passes_grounding():
    goal = "Stop having the same recurring argument with their partner."
    user_text = "My partner says we keep having the same argument."
    assert _is_goal_grounded(goal, user_text)


def test_original_drafted_examples_would_have_failed_grounding():
    """Documents the actual bug found before it was fixed -- the v2
    proposal's own original wording, unmodified, does NOT survive the
    grounding filters. This is why the examples above were reworded
    rather than shipped as originally drafted."""
    assert not _is_assumption_grounded(
        "Lack of response indicates anger.",
        "My friend hasn't replied in three days. I think they're angry.",
    )
    assert not _is_goal_grounded(
        "Improve relationship conflict.",
        "My partner says we keep having the same argument.",
    )


def test_fabricated_causal_assumption_still_correctly_rejected():
    """Regression check: extending _CAUSAL_CONNECTOR with implication
    verbs must not weaken the original fabrication-catching behavior it
    was built for (see engine.py's module-level comment on the 5-run
    dataset this threshold was calibrated against)."""
    fabricated = (
        "The boss is not willing to grant the move because the boss secretly "
        "wants to keep the user on the current team for personal reasons."
    )
    user_text = "My boss keeps saying no to my request to move to the Product team."
    assert not _is_assumption_grounded(fabricated, user_text)


def test_genuinely_grounded_causal_assumption_still_accepted():
    """The original, already-working causal-connector case (a real
    inference, clause after 'because' genuinely grounded) must still pass."""
    assumption = "User assumes the delay is because the boss doesn't value the move."
    user_text = "My boss keeps delaying my request to move to the Product team."
    assert _is_assumption_grounded(assumption, user_text)
