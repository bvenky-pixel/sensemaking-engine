# Confidant Interaction Architecture v1

Status: Depends on `frontend-philosophy-v1.md`, `emotional-design-v1.md`,
and `information-architecture-v1.md`. Where Information Architecture
defines the *rooms* (Home, Thread, Settings), this document defines what
actually happens inside a Thread — the lifecycle of a conversation, the
states it moves through, and what each state should feel like from the
person's side of the exchange.

---

## Purpose

Confidant's backend is a real, multi-stage reasoning process — a message
is interpreted, folded into an evolving understanding, judged, planned
over, and only then responded to (see
`engine/specs/system-architecture-v2-specification.md`'s description of
the Sensemaking Engine). None of that mechanism should be visible by
name, but its *shape* has direct consequences for what the interaction
should feel like: this is not a system that returns an answer the
instant you finish typing, and the interaction architecture has to be
honest about that rather than disguise it as instant chat.

This document exists to define the emotional and functional shape of a
Thread's lifecycle so that every screen state, transition, and waiting
moment can be checked against a single coherent model of what a
conversation with Confidant actually is.

## Scope

This document covers: the lifecycle states a Thread moves through (from
first opening to a considered pause), what distinguishes Confidant
asking a clarifying question from Confidant offering a reflection, and
how returning to a Thread after time away should be handled. It does not
cover visual treatment, motion timing, or the technical mechanics of
the wait itself — see `visual-design-system-v1.md` and
`motion-and-latency-philosophy-v1.md` for those.

---

## The Lifecycle of a Thread

### Opening

A new Thread opens with an invitation, not a form. There is no "describe
your issue in the box below," no category picker ("career / relationship
/ decision"), no required structure imposed before a person is allowed
to start talking. The opening moment should feel like sitting down
across from someone who is ready to listen, not like filling out an
intake questionnaire — the categorization the backend eventually needs
(the epistemic tiers, the urgency read) is entirely its own job to
infer, never the person's job to pre-sort.

### The Exchange

Once a Thread is underway, each turn moves through a small number of
felt states, regardless of how many backend stages actually run behind
them:

- **Sharing** — the person is expressing something: a situation, a
  reaction, a new detail. This state belongs entirely to the person;
  the interface should not intrude on it.
- **Considering** — Confidant is working. This is the state that
  corresponds to the backend's real multi-stage reasoning, and it is
  the state most vulnerable to feeling like generic "loading." It must
  be designed deliberately (see `motion-and-latency-philosophy-v1.md`)
  rather than inherited from a generic spinner pattern.
- **Responding** — Confidant offers something back. Critically, a
  response in Confidant is not always advice or even a statement — it
  is frequently a question, sometimes a tentative reading offered for
  correction, occasionally a plain admission that something is still
  unclear. All three must feel like equally complete, well-formed
  responses, never like an assistant that "couldn't help" when it asks
  rather than answers (see `emotional-design-v1.md`'s principle that
  uncertainty is a legitimate, well-formed output).

### Clarifying vs. Reflecting

Two distinct kinds of Confidant turn deserve to be told apart, because a
person should be able to tell, at a glance, which one they're in:

- A **clarifying** turn is Confidant admitting it doesn't yet understand
  enough to say something meaningful, and asking for exactly the
  missing piece — not a generic "tell me more," but a specific question
  traceable to a specific gap (the backend's Judgment output surfaces
  these as open unknowns; the interface's job is to ask about the real
  gap, not a templated one).
- A **reflecting** turn is Confidant offering back a synthesis of what
  it currently understands — a moment where the person can see their
  own situation described back to them and correct it if it's wrong.
  This is where `memory-and-shared-understanding-v1.md`'s surfaces
  become directly relevant inside the live exchange, not only in a
  separate understanding view.

Neither of these should ever be dressed up as, or mistaken for, a
confident final answer. The interaction architecture's job is to make
the *kind* of turn legible without requiring a label that names it.

### Pausing

There is no "end conversation" action, because a Thread is never
conceptually over the way a single chat session is (see
`information-architecture-v1.md`). A person simply stops, at any point,
mid-exchange or after a reflection — and the interface's only job at
that moment is to not demand closure it doesn't need (no "wrap up your
session," no forced summary screen before leaving).

### Returning

When a person comes back to a Thread — minutes, days, or months later —
the interface must re-orient them without overwhelming them. This means
surfacing enough of the accumulated understanding to remind, not
enough to require re-reading a transcript. The exact shape of that
re-entry surface belongs to
`memory-and-shared-understanding-v1.md`; this document's obligation is
only that re-entry is treated as a first-class lifecycle moment, not an
afterthought bolted onto "just show the last few messages."

---

## Guiding Principles

### 1. The Interaction Model Must Be Honest About Latency

Because the backend genuinely takes real time to reason across multiple
stages, the interaction architecture must never pretend this is
instantaneous chat. A "Considering" state that's treated as a bug to be
minimized (rather than a feature to be designed) will always look like
the product apologizing for its own thoughtfulness. The interaction
architecture instead treats duration as informative — the felt sense
that longer consideration corresponds to a harder or more layered
situation is not something to eliminate, but not something to be
manufactured falsely either, if it doesn't correspond to what's
actually happening.

### 2. A Question Is a Complete Turn

Product conventions elsewhere treat a clarifying question as a
consolation prize for failing to answer. Confidant's interaction
architecture rejects that framing entirely: a well-placed question,
grounded in a real, specific gap, is one of the best possible outcomes
of a turn, and must be designed to feel that way — never apologetic,
never hedged with "sorry, I need more information before I can help."

### 3. Nothing Should Feel Final Unless the Person Made It Final

Confidant's own outputs (a reflection, a reading of the situation, a
plan) are never the end of the matter — the person can always push back,
correct, or redirect. The interaction architecture must never present a
Confidant turn in a visual or structural register that implies the
conversation has reached a concluding verdict, because the actual
verdict — the decision, the interpretation, the next step — belongs to
the person, not to Confidant (see `frontend-philosophy-v1.md`'s "the
user owns the conclusions").

---

## Design Rationale

### Why Not Model This as a Standard Chat Interface

A standard chat interface (alternating bubbles, instant response
affordance, a persistent input box demanding the next message) imports
an entire set of unstated expectations: that faster is better, that
every message deserves an immediate reply, that the conversation is the
whole product. Confidant's actual mechanism — slow, multi-stage,
understanding-first reasoning that sometimes produces a question instead
of an answer — is fundamentally incompatible with those expectations. If
the interaction architecture borrowed the chat convention wholesale, the
emotional design and trust principles in the other documents would be
undermined by the interaction shape itself, regardless of how careful
the copy or visuals were.

### Why Clarifying and Reflecting Need to Be Distinguishable

Without a way to tell a clarifying turn from a reflecting turn, both
collapse into "Confidant said something back," which erases exactly the
epistemic honesty (see `trust-and-privacy-ux-v1.md`'s uncertainty
disclosure principle) this whole product depends on. A person needs to
be able to tell, without reading closely, whether they're being asked
for more information or being shown back an understanding they can
correct — these require different responses from the person, and
conflating them creates confusion at precisely the moment clarity
matters most.

---

## Future Considerations

- If real usage shows that people frequently want to interrupt a
  "Considering" state (to add a detail before Confidant responds, or to
  redirect entirely), that's a genuine interaction-architecture question
  this document doesn't yet resolve, and should be revisited with real
  evidence once available — not speculated on in advance.
- This document assumes a single-threaded exchange, one turn at a time.
  If Confidant ever needs to hold multiple open questions
  simultaneously within one Thread, that would require an explicit
  extension to the Clarifying/Reflecting model above.
- The exact visual and motion treatment of "Considering" is deliberately
  left to `motion-and-latency-philosophy-v1.md` — this document commits
  only to what that state must accomplish emotionally, not how it's
  rendered.
