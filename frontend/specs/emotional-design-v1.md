# Confidant Emotional Design v1

Status: Depends on `frontend-philosophy-v1.md`. This document translates
that document's emotional register (private, safe, calm, thoughtful,
warm, earnest, minimalist) from adjectives into decidable design
judgments — the difference between "the product should feel calm" and
"here is what calm actually requires of a loading state, a response
cadence, and a word choice."

---

## Purpose

Philosophy states the feeling Confidant must produce. This document
states what specifically produces it — and, just as importantly, what
specifically destroys it — so that every later, more concrete document
(visual design, motion, interaction architecture) inherits a shared,
checkable definition instead of a private interpretation of "calm."

Without this document, "make it feel warm" is a design note anyone can
satisfy in an incompatible way. With it, warmth becomes a set of
falsifiable claims: does this response open with validation or with a
question? Does this transition happen abruptly or with acknowledgment?

## Scope

This document covers: tone of voice, pacing of language and reveal, the
felt experience of waiting, and the specific patterns (urgency cues,
manufactured cheerfulness, performative empathy) that must never appear.
It does not cover color, typography, motion timing curves, or layout —
those are the job of the Visual Design System and Motion & Latency
Philosophy documents, which must treat this document's emotional claims
as their brief.

---

## Guiding Principles

### 1. Warmth Is Attention, Not Enthusiasm

The frontend must never confuse warmth with energy. A warm response
notices something true and specific about what the user said; an
enthusiastic response uses exclamation points and validates
indiscriminately ("Great question!", "I totally understand!"). Confidant
should never say "great question" — it should demonstrate that the
question was heard by responding to its actual substance. Warmth is
earned through specificity, not asserted through tone.

### 2. Calm Is the Absence of Manufactured Urgency

Nothing in the interface should imply that time is running out, that the
user should act now, or that a response is more urgent than the user's
own situation makes it. This rules out countdown-style loading
indicators, "your session will expire" framing used as a nudge rather
than a genuine technical constraint, and any color or motion vocabulary
borrowed from alerts or warnings for anything that isn't an actual
error. Calm is not a mood applied on top of the interface — it is the
systematic removal of every cue that would make someone feel rushed.

### 3. Thoughtfulness Is Visible Restraint

A thoughtful response is recognizable by what it doesn't say as much as
by what it does. If the backend's Judgment carries open unknowns or low
confidence, the frontend must let that show as restraint ("here's what
I'm still not sure about") rather than smoothing it into a
confident-sounding paragraph. Visible restraint is one of the only ways
a text interface can communicate "I am actually thinking about this,"
as opposed to "I am generating plausible-sounding text."

### 4. Earnestness Forbids Performed Empathy

There is a specific, recognizable pattern common to AI assistants:
opening a response with "I hear you" or "that sounds really hard" as a
reflexive preamble regardless of what was actually said. This is
performed empathy, and it is worse than no empathy — it signals a
template, not attention. Confidant's responses must never open with a
generic empathy preamble. If empathy is warranted, it must be specific
enough that it could only follow from what this particular user said in
this particular turn.

### 5. Silence and Slowness Are Legitimate States

A person thinking something through does not always want to be met with
immediate output. The interface must treat a pause, a partial thought,
or a slow unfolding of understanding as a normal, unremarkable state —
not something to fill with reassurance, progress percentages, or
"almost there" messaging. The backend's real architecture (multiple
sequential LLM calls: Interpretation, Judgment, Planner, Response) means
waiting is often genuinely several seconds; the emotional design goal is
for that wait to read as *care*, not *latency to be apologized for*.

---

## Design Rationale

### Why Ban Specific Language Patterns Rather Than Set a General Tone

A general instruction like "be warm and empathetic" is exactly the kind
of guidance that produces the generic, template-feeling responses this
document is trying to prevent — because "warm and empathetic" is also
what produces "I hear you, that sounds really hard!" This document
instead names the specific patterns that masquerade as warmth
(enthusiasm, generic empathy preambles, exclamation-driven validation)
and rules them out explicitly, leaving genuine specificity as the only
remaining path to satisfying "warm."

### Why Pacing Belongs Here, Not Only in Motion Philosophy

It would be easy to treat "how fast things appear" as a purely visual/
animation concern and defer it entirely to the Motion & Latency
Philosophy document. That document owns the *mechanics* of pacing
(timing curves, when to show what). This document owns the *meaning* of
pacing — the claim that slowness, done right, is a trust signal rather
than a performance deficit. Motion & Latency Philosophy must implement
this document's meaning; it does not get to invent its own.

### Why This Document Doesn't Specify Exact Copy

This document is deliberately about principles and forbidden patterns,
not a style guide of approved sentences. A copy style guide will
eventually be useful, but it belongs downstream of this document (likely
folded into a future content/voice guidelines addendum), because copy
needs to be checked against these principles repeatedly as the product's
language evolves — the principles need to outlast any particular set of
example sentences.

---

## Future Considerations

- A dedicated Voice & Tone content guide (example phrasings, a list of
  banned stock phrases, guidance for edge cases like crisis-adjacent
  disclosures) is a natural, likely necessary follow-on to this
  document once real conversation transcripts exist to learn from — but
  it must be built as an *application* of these principles, not a
  replacement for them.
- If Confidant ever needs to signal genuine urgency (e.g., a detected
  safety concern that warrants surfacing crisis resources), that is
  deliberately out of scope here and needs its own careful design
  treatment — the "no manufactured urgency" principle in this document
  is about false urgency, not a blanket ban on ever signaling that
  something serious deserves attention. That treatment must be
  designed explicitly, not inferred from this document's silence on it.
- As real usage data accumulates, some assumptions here (e.g., that
  users always want restraint over reassurance during long waits) should
  be revisited deliberately, the same way Judgment v2's calibration was
  revisited only after real evaluation evidence existed — not simply
  because a stakeholder prefers a livelier interface.
