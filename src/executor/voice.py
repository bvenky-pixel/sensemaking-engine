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

_THIRD_PARTY_MARKER_WORDS = (
    r"manager|partner|friend|colleague|parent|parents|spouse|boss|"
    r"co-founder|cofounder|family|therapist|doctor|sibling|sister|brother|"
    r"mother|father|mom|dad|coworker|teammate|roommate|landlord"
)
_THIRD_PARTY_MARKERS = re.compile(rf"\b({_THIRD_PARTY_MARKER_WORDS})\b", re.IGNORECASE)

# Confirmed live false-positive (see engine/decisions.md "Tier 1
# completeness + has_knowledge_correction calibration" -- validation
# report Failure Mode #7, replaying captured case R02): "User thinks
# their friend is angry with them." rewrites to "You think their friend
# is angry with them." -- "their" is left unrewritten even though it
# clearly refers to the user here ("their friend" = the user's friend),
# because the third-party marker bailout below suppresses they/their/
# them globally the moment ANY marker appears anywhere in the string.
#
# A possessive "their" immediately followed by the SAME third-party-
# marker noun it would otherwise be suppressed for is a narrower, safe
# case to fix on its own: a person cannot simultaneously possess and BE
# the noun phrase that follows ("their friend" can never mean "the
# friend's own friend"), so this specific adjacency can only be the
# user's possessive -- given this codebase's own convention that these
# template strings only ever narrate the user's beliefs/feelings
# (see module docstring), never a third party's independent actions,
# "their <marker>" reliably means "the user's <marker>" every time it's
# been observed. Rewritten unconditionally, BEFORE the broader bailout
# below (which still applies, unchanged, to every other they/their/them
# in the string -- e.g. the "them" in the same R02 sentence remains
# conservatively unrewritten, since it's genuinely ambiguous whether it
# refers to the user or the friend without real coreference resolution).
_POSSESSIVE_BEFORE_THIRD_PARTY_MARKER = re.compile(
    rf"\b[Tt]heir(?=\s+(?:{_THIRD_PARTY_MARKER_WORDS})\b)", re.IGNORECASE
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

# NOTE (found live, see engine/decisions.md "Tier 1 completeness +
# has_knowledge_correction calibration" -- grammar regression follow-up):
# `(?:the\s+)?` was case-sensitive on every one of these four regexes
# except _AUX_PLUS_USER below, which already carries re.IGNORECASE.
# A sentence-initial "The user hopes..." (capitalized "The") failed to
# match the leading-article group at all -- only "user hopes" matched,
# leaving a stray "The " in front of the replacement ("The you hope...").
# _cased() already derives correct capitalization from the actual
# match, so re.IGNORECASE alone fixes this: the whole "The user" is now
# consumed as one match, and _cased sees the real leading "T" to
# capitalize "You" correctly.
_USER_POSSESSIVE = re.compile(r"\b(?:the\s+)?[Uu]ser's\b", re.IGNORECASE)
_USER_PLUS_VERB = re.compile(rf"\b(?:the\s+)?[Uu]ser\s+({_VERB_ALTERNATION})\b", re.IGNORECASE)

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
# "gains", "identifies", "watches"). Runs only on whatever _USER_PLUS_VERB
# left unmatched, so the explicit map above always takes priority for the
# irregular forms (is/was/has/does) it exists specifically to handle.
_USER_PLUS_UNKNOWN_VERB = re.compile(r"\b(?:the\s+)?[Uu]ser\s+(\w+s)\b", re.IGNORECASE)

# A small number of verbs already ending in "ie" (die/lie/tie) form their
# third-person-singular by adding a plain "s" ("dies"/"lies"/"ties"), which
# is spelled identically to the far more common "consonant+y -> ies"
# pattern below ("tries"/"denies") -- these three must be special-cased
# before that suffix rule runs, or "dies"/"lies"/"ties" would be wrongly
# rewritten to "dy"/"ly"/"ty".
_IE_VERBS = {"dies": "die", "lies": "lie", "ties": "tie", "vies": "vie"}

_BARE_USER = re.compile(r"\b(?:the\s+)?[Uu]ser\b", re.IGNORECASE)
_THEY = re.compile(r"\b[Tt]hey\b")
_THEIR = re.compile(r"\b[Tt]heir\b")
_THEM = re.compile(r"\b[Tt]hem\b")


def _cased(original: str, lower: str) -> str:
    """Preserve capitalization: if `original`'s first letter was
    uppercase, capitalize `lower`'s first letter too."""
    if original[:1].isupper():
        return lower[:1].upper() + lower[1:]
    return lower


def _third_person_to_base(verb: str) -> str:
    """
    Reverses regular English third-person-singular conjugation, for a
    verb after "user" not covered by _VERB_INFLECTIONS' explicit map.
    Naively stripping one trailing "s" (the original, buggy version of
    this function) is only correct for the plain "add s" case
    ("gains" -> "gain") -- it silently misspells the two other regular
    patterns English actually uses:
      - a sibilant-ending base takes "es", not "s" ("watch" -> "watches",
        "wish" -> "wishes", "discuss" -> "discusses", "miss" -> "misses",
        "fix" -> "fixes", "buzz" -> "buzzes") -- stripping only the final
        "s" leaves a stray trailing "e" ("watche", "discusse").
      - a consonant-plus-y base changes y -> ies ("try" -> "tries",
        "identify" -> "identifies", "deny" -> "denies", "rely" ->
        "relies") -- stripping the final "s" leaves "trie"/"identifie".
    Both of these are exactly the shape of verb Judgment/Planner's own
    natural-language fields regularly produce (e.g. Planner's own shipped
    desired_outcome example, "user identifies the next action") -- see
    engine/decisions.md "Major update" for the live regression this fixed.
    """
    lower = verb.lower()
    if lower in _IE_VERBS:
        return _IE_VERBS[lower]
    if lower.endswith("ies"):
        return verb[:-3] + "y"
    if lower.endswith(("sses", "shes", "ches", "xes", "zzes", "oes")):
        return verb[:-2]
    if lower.endswith("s"):
        return verb[:-1]
    return verb


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
        stripped = _third_person_to_base(verb)
        return f"{_cased(match.group(0), 'you')} {stripped}"

    text = _USER_POSSESSIVE.sub(lambda m: _cased(m.group(0), "your"), text)
    text = _USER_PLUS_VERB.sub(_verb_repl, text)
    text = _AUX_PLUS_USER.sub(_aux_repl, text)
    text = _USER_PLUS_UNKNOWN_VERB.sub(_unknown_verb_repl, text)
    text = _BARE_USER.sub(lambda m: _cased(m.group(0), "you"), text)
    # Runs unconditionally, ahead of the broader they/their/them bailout
    # below -- see _POSSESSIVE_BEFORE_THIRD_PARTY_MARKER's own comment
    # for why this specific adjacency is always safe to rewrite even
    # though a bare they/their/them elsewhere in the same string isn't.
    text = _POSSESSIVE_BEFORE_THIRD_PARTY_MARKER.sub(lambda m: _cased(m.group(0), "your"), text)

    if not _THIRD_PARTY_MARKERS.search(text):
        text = _THEY.sub(lambda m: _cased(m.group(0), "you"), text)
        text = _THEIR.sub(lambda m: _cased(m.group(0), "your"), text)
        text = _THEM.sub(lambda m: _cased(m.group(0), "you"), text)

    return text
