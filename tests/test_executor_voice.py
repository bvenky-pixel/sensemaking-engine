"""
Tests for src/executor/voice.py's deterministic to_second_person rewrite
-- pure Python, no LLM calls. Every case below is a real sentence a live
pipeline run produced this session (see engine/decisions.md "Major
update"), not a synthetic example, so these tests double as a record of
what the fix actually needed to handle.
"""

from __future__ import annotations

from src.executor.voice import to_second_person


def test_empty_string_is_a_noop():
    assert to_second_person("") == ""


def test_text_without_user_mention_is_unchanged():
    text = "Your manager provided positive feedback last quarter."
    assert to_second_person(text) == text


def test_sentence_initial_user_plus_verb():
    assert (
        to_second_person("User is thinking of quitting without another job lined up.")
        == "You are thinking of quitting without another job lined up."
    )


def test_possessive_with_third_party_marker_preserves_their_pronoun():
    # "they" refers to the manager, not the user -- must NOT be rewritten
    # because a third-party marker ("manager") is present in the string.
    assert (
        to_second_person("User's manager says they are doing great.")
        == "Your manager says they are doing great."
    )


def test_believing_clause_they_refers_to_user_and_is_rewritten():
    # No third-party marker present -- "they" here is the user themselves.
    assert (
        to_second_person(
            "User feels guilty despite believing they haven't done anything wrong."
        )
        == "You feel guilty despite believing you haven't done anything wrong."
    )


def test_the_user_believes_pattern():
    assert (
        to_second_person(
            "Assumes the user believes failure is a likely outcome of starting a company."
        )
        == "Assumes you believe failure is a likely outcome of starting a company."
    )


def test_possessive_mid_sentence_lowercase():
    assert (
        to_second_person(
            "Your lack of enjoyment may lead to further emotional distress or "
            "disengagement from activities, grounded in the claim that they "
            "don't enjoy anything."
        )
        == "Your lack of enjoyment may lead to further emotional distress or "
        "disengagement from activities, grounded in the claim that you "
        "don't enjoy anything."
    )


def test_was_inflection():
    assert (
        to_second_person("User was passed over for promotion again.")
        == "You were passed over for promotion again."
    )


def test_unlisted_verb_falls_back_to_stripping_trailing_s():
    # "gains" isn't in the explicit _VERB_INFLECTIONS map -- the generic
    # fallback still produces grammatical output.
    assert (
        to_second_person("user gains clarity on next steps")
        == "you gain clarity on next steps"
    )


def test_has_inflection():
    assert (
        to_second_person("User has been trying to move to the Product team.")
        == "You have been trying to move to the Product team."
    )


def test_bare_user_without_following_verb():
    assert to_second_person("This decision belongs to the user.") == "This decision belongs to you."


def test_question_inversion_does_the_user():
    # Auxiliary precedes "user" (open_unknowns is often phrased this way)
    # -- a bare "user" -> "you" swap alone would leave "What does you
    # want next?", still broken; the auxiliary itself must also flip.
    assert (
        to_second_person("What does the user want next?")
        == "What do you want next?"
    )


def test_question_inversion_has_the_user():
    assert (
        to_second_person("Has the user considered other options?")
        == "Have you considered other options?"
    )


def test_third_party_marker_suppresses_their_and_them_globally_in_string():
    # Conservative, accepted trade-off: "them" here actually refers to the
    # user (the co-founder doesn't trust the user), but the presence of
    # "co-founder" suppresses pronoun rewriting to avoid the worse error
    # of misattributing a third party's own pronoun to the user elsewhere.
    text = "User assumes the co-founder doesn't trust them."
    result = to_second_person(text)
    assert result == "You assume the co-founder doesn't trust them."
