"""
Deterministic third-person -> second-person voice rewrite for Executor's
Clarity Brief fields (see engine.py::build_clarity_brief).

Confidant's internal cognitive layers (Interpretation/Judgment/Planner)
are deliberately written in third person throughout -- correct for
internal reasoning artifacts, wrong for the Understanding panel, which
is one of the few places (besides Response Generator's own
response_text) this text reaches an actual person. Executor is a pure,
no-LLM-call template by design (see engine.py's module docstring for why
that stays true), so this stays a plain regex rewrite rather than a new
LLM call -- an explicit trade-off, not an oversight (see
engine/decisions.md "Major update" for the discussion).

Not grammatically perfect on every sentence shape -- accepted. "they"/
"their"/"them" are only rewritten when the string contains no other
person noun a bare pronoun could plausibly refer to instead (see
_THIRD_PARTY_MARKERS below) -- conservative under-rewriting (leaving a
pronoun as "them" when it should say "you") is preferred over
misattributing another person's pronoun to the user.
"""

from __future__ import annotations

import re

_THIRD_PARTY_MARKERS = re.compile(
    r"\b(manager|partner|friend|colleague|parent|parents|spouse|boss|"
    r"co-founder|cofounder|family|therapist|doctor|sibling|sister|brother|"
    r"mother|father|mom|dad|coworker|teammate|roommate|landlord)\b",
    re.IGNORECASE,
)

# Third-person singular -> second-person verb forms, only rewritten when
# the verb directly follows "user"/"the user" (see _USER_PLUS_VERB) --
# scoped narrowly so this never touches an unrelated verb elsewhere in
# the sentence.
_VERB_INFLECTIONS = {
    "is": "are", "was": "were", "has": "have", "does": "do",
    "wants": "want", "believes": "believe", "feels": "feel",
    "considers": "consider", "thinks": "think", "needs": "need",
    "seems": "seem", "appears": "appear", "worries": "worry",
    "struggles": "struggle", "hopes": "hope", "fears": "fear",
    "wonders": "wonder", "plans": "plan", "assumes": "assume",
    "deserves": "deserve", "keeps": "keep", "remains": "remain",
}
_VERB_ALTERNATION = "|".join(_VERB_INFLECTIONS)

_USER_POSSESSIVE = re.compile(r"\b(?:the\s+)?[Uu]ser's\b")
_USER_PLUS_VERB = re.compile(rf"\b(?:the\s+)?[Uu]ser\s+({_VERB_ALTERNATION})\b")

# Question-inversion form ("Does the user...?", "Has the user...?") --
# the auxiliary precedes "user" instead of following it, so _USER_PLUS_VERB
# above doesn't catch it. Handled separately: rewrites the auxiliary too
# (does -> do, has -> have, is -> are, was -> were), so "What does the
# user want?" becomes "What do you want?" rather than the still-broken
# "What does you want?" a bare "user" -> "you" swap alone would leave.
_INVERTED_AUX = {
    "does": "do", "has": "have", "is": "are", "was": "were",
}
_INVERTED_AUX_ALTERNATION = "|".join(_INVERTED_AUX)
_AUX_PLUS_USER = re.compile(
    rf"\b({_INVERTED_AUX_ALTERNATION})\s+(?:the\s+)?[Uu]ser\b", re.IGNORECASE
)

# Fallback for a verb after "user" not in _VERB_INFLECTIONS above (e.g.
# "gains", "expects") -- naive "strip the trailing s" English
# third-person-singular rule. Runs only on whatever _USER_PLUS_VERB left
# unmatched, so the explicit map above always takes priority for the
# irregular forms (is/was/has/does) it exists specifically to handle.
_USER_PLUS_UNKNOWN_VERB = re.compile(r"\b(?:the\s+)?[Uu]ser\s+(\w+s)\b")

_BARE_USER = re.compile(r"\b(?:the\s+)?[Uu]ser\b")
_THEY = re.compile(r"\b[Tt]hey\b")
_THEIR = re.compile(r"\b[Tt]heir\b")
_THEM = re.compile(r"\b[Tt]hem\b")


def _cased(original: str, lower: str) -> str:
    """Preserve capitalization: if `original`'s first letter was
    uppercase, capitalize `lower`'s first letter too."""
    if original[:1].isupper():
        return lower[:1].upper() + lower[1:]
    return lower


def to_second_person(text: str) -> str:
    """Rewrites third-person "user" references to second-person "you"
    references. A no-op on text that doesn't mention "user" at all --
    most Judgment/Planner-sourced strings won't."""
    if not text:
        return text

    def _verb_repl(match: "re.Match[str]") -> str:
        verb = match.group(1).lower()
        return f"{_cased(match.group(0), 'you')} {_VERB_INFLECTIONS[verb]}"

    def _aux_repl(match: "re.Match[str]") -> str:
        aux = match.group(1).lower()
        return f"{_cased(match.group(1), _INVERTED_AUX[aux])} you"

    def _unknown_verb_repl(match: "re.Match[str]") -> str:
        verb = match.group(1)
        stripped = verb[:-1] if verb.endswith("s") else verb
        return f"{_cased(match.group(0), 'you')} {stripped}"

    text = _USER_POSSESSIVE.sub(lambda m: _cased(m.group(0), "your"), text)
    text = _USER_PLUS_VERB.sub(_verb_repl, text)
    text = _AUX_PLUS_USER.sub(_aux_repl, text)
    text = _USER_PLUS_UNKNOWN_VERB.sub(_unknown_verb_repl, text)
    text = _BARE_USER.sub(lambda m: _cased(m.group(0), "you"), text)

    if not _THIRD_PARTY_MARKERS.search(text):
        text = _THEY.sub(lambda m: _cased(m.group(0), "you"), text)
        text = _THEIR.sub(lambda m: _cased(m.group(0), "your"), text)
        text = _THEM.sub(lambda m: _cased(m.group(0), "you"), text)

    return text
