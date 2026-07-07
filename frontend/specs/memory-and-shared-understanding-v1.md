# Confidant Memory & Shared Understanding v1

**Status: RETIRED, superseded by `interaction-model-v4.md`.** This
document treated shared understanding as a foldable panel alongside a
conversation. `interaction-model-v4.md`'s "Letting the Architecture Be
Felt" section is the authoritative replacement — understanding is now
the product's most structurally important, ever-present moment, not a
feature a person opens. The correction/deletion discipline (a person's
correction must change what the backend actually carries forward, not
just what's displayed) carries forward unchanged into the new document.
Kept in git history as the visible reasoning trail, not deleted.

---

Original status (no longer current): Depends on
`frontend-philosophy-v1.md`, `information-architecture-v1.md`, and
`interaction-architecture-v1.md`. This is the most Confidant-specific
document in the frontend architecture — it defines how the backend's
evolving understanding of a situation (built by Interpretation,
WorldState, and Judgment; see `engine/specs/system-architecture-v2-
specification.md`) becomes something a person can actually see, trust,
and correct, rather than an invisible mechanism working on their behalf.

---

## Purpose

The brand promise is "we can figure this out together" (see
`frontend-philosophy-v1.md`). The word doing the most work in that
sentence is *together* — and together is only true if the person can
see what Confidant currently understands, not just receive outputs
produced by an understanding they never got to inspect.

This document exists to design that visibility: what "shared
understanding" looks like as a real, navigable surface inside a Thread,
how it's summarized without flattening genuine nuance or uncertainty,
and how a person corrects it when it's wrong — because it will
sometimes be wrong, and how the product handles that is one of the
clearest tests of whether "together" is a real commitment or a slogan.

## Scope

This document covers: what a person sees when they look at "what
Confidant understands," how that understanding is summarized as it
grows, how corrections are handled, and how re-entering a Thread after
time away is supported by this surface. It does not cover the backend
mechanism that produces the understanding (Interpretation, WorldState,
Judgment — see `engine/specs/`), only how that mechanism's output is
translated into something legible and actionable for the person it's
about.

---

## Guiding Principles

### 1. The Understanding Surface Is Not a Debug View

The backend's internal representation of a situation is a structured
object with fields like facts, claims, inferences, unknowns, and
confidence scores (see `engine/specs/WorldState-spec-v1.md`). None of
that vocabulary belongs in the interface directly. A person should never
see the word "confidence: 0.6" or a label like "epistemic tier" — they
should see the *content* of that structure rendered as something a
thoughtful person would actually say out loud: "Here's what I've picked
up so far... and here's what I'm still genuinely unsure about." The
translation from structured backend state to plain, human language is
this document's central design problem, not an afterthought delegated
to copywriting.

### 2. Certainty Must Be Shown Honestly, Never Smoothed Over

When the backend's own assessment is genuinely uncertain — open
unknowns, moderate or low confidence, an unresolved tension between two
things the person has said — the understanding surface must reflect
that honestly rather than resolve it into a single clean narrative for
the sake of readability. A tidy paragraph that quietly picks one reading
over another, when the backend itself hasn't picked one, is a form of
the product overstating its own certainty (see `trust-and-privacy-ux-
v1.md`'s uncertainty-disclosure principle) — even if no single sentence
in it is technically false.

### 3. Understanding Is Always Correctable, in Place

A person must be able to look at any piece of Confidant's current
understanding and say, in effect, "that's not quite right" — and have
that correction actually change what Confidant carries forward, not
just be acknowledged and then quietly ignored by the underlying
understanding. This is the frontend's concrete discharge of the
philosophy's "the user owns the conclusions" commitment: ownership that
can't actually edit anything is not ownership, it's a comment box.

### 4. Summaries Compress Detail, They Never Discard It

As a Thread grows, showing every fact and claim ever surfaced becomes
unusable — so summarization is necessary. But summarizing must mean
*compressing forward* (showing the current, most relevant picture) while
still making the fuller history reachable for anyone who wants to see
how the current understanding was arrived at. A person should never
discover that something they said earlier has simply vanished from
Confidant's picture of their situation without a trace of why.

### 5. Re-Entry Is a Moment of Re-Orientation, Not Re-Reading

When a person returns to a Thread, the understanding surface is what
lets them pick back up without scrolling through a transcript. It should
answer, immediately and without effort: what's the situation, what does
Confidant currently think is true, and what's still open — the same
three questions a trusted friend would silently answer for themselves
before saying "so, where were we."

---

## What the Understanding Surface Contains

Translated from the backend's structure into what a person should
actually be shown, without ever naming the backend's own field names:

- **The situation, in plain language** — a short, current statement of
  what this Thread is about (drawn from the backend's surface
  complaint, but written as something a person would recognize as a
  fair summary of what they've been describing, not a clinical
  restatement).
- **What's been established** — the handful of things Confidant is
  treating as solid ground, stated plainly and without hedging language
  that isn't warranted.
- **What Confidant currently makes of it** — Confidant's own read on the
  situation, explicitly presented as a reading, not a fact — this is
  the one part of the surface where Confidant's own interpretation is
  visible as interpretation.
- **What's still open** — genuine unresolved questions, shown as
  questions, not as gaps to feel bad about. This is where a person can
  see exactly what Confidant doesn't yet know, and why it might ask
  about it.
- **Decisions in play** — anything the person is actively weighing,
  shown as theirs to make, never as something Confidant has a stake in
  resolving one way.

Every one of these should be able to visibly change as a Thread
develops — the surface represents the CURRENT state of shared
understanding, and its whole value is that it keeps up with the
conversation rather than freezing an early impression.

---

## Design Rationale

### Why This Needs Its Own Document Instead of Living Inside Interaction Architecture

Interaction Architecture defines the "Reflecting" turn — the moment
inside a live exchange where understanding is offered back. This
document defines the *standing surface* that exists whether or not a
reflecting turn is currently happening — something a person can consult
deliberately, not only receive when Confidant chooses to reflect. The
two are related but distinct: one is a conversational event, the other
is a persistent, inspectable state. Collapsing them would make the
understanding surface feel like a transient message rather than
something genuinely stable and trustworthy enough to build a
relationship on.

### Why Corrections Must Change the Underlying Understanding, Not Just the Display

A correction that only updates what's shown on screen, without actually
changing what the backend carries forward into its next reasoning pass,
is a UI-level lie — the person would reasonably believe they've fixed a
misunderstanding, while Confidant's actual reasoning continues to
operate on the old, wrong premise. This principle is a direct
frontend obligation created by `trust-and-privacy-ux-v1.md`'s "deletion
and forgetting must be real, not cosmetic" — the same standard applies
here to correction, not only removal.

### Why Not Simply Show the Full Conversation History as "Memory"

A raw transcript is not understanding — it's data understanding was
built from. Showing the transcript instead of a synthesized
understanding surface would put the burden of re-deriving the current
picture back on the person every time they return, exactly the "re-
reading" cost this document's fifth principle is designed to eliminate.
The transcript should remain reachable (nothing is secretly discarded —
see principle 4), but it is not the primary surface; the synthesized
understanding is.

---

## Future Considerations

- The exact interaction for making a correction (editing a shown
  statement directly vs. a lighter "this isn't quite right, here's what
  I meant" flow) is a genuine open design question this document
  intentionally leaves unresolved — it belongs to a future, more
  concrete interaction pass once this document's principles are agreed.
- If Confidant ever needs to show *how* an understanding changed over
  time (not just its current state), that's a legitimate but distinct
  feature — a history-of-understanding view — and should be designed
  as an explicit addition to this document, not assumed to already be
  covered by "summaries never discard detail."
- This document assumes understanding is scoped to a single Thread
  (see `information-architecture-v1.md`). If the backend's currently
  unimplemented Learning process (see `engine/specs/system-
  architecture-v2-specification.md`) is ever built out to produce
  durable, cross-Thread knowledge, this document will need a direct,
  deliberate amendment addressing what — if anything — surfaces to the
  person about knowledge that spans situations, since today's model
  assumes no such thing exists.
