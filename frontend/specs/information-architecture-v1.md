# Confidant Information Architecture v1

Status: Depends on `frontend-philosophy-v1.md`. This document defines
what spaces exist in Confidant, and the navigation philosophy that
connects them. It is deliberately short — the same "Simplicity" principle
that governs every other design decision in this product also governs
how much structure the product is allowed to have.

---

## Purpose

Before anything can be designed — a screen, a transition, a component —
someone has to decide what *exists*. This document is that decision. It
names the minimum set of spaces Confidant needs to do its job, and
explicitly rules out every space a conventional product in this category
would add by default (a dashboard, a feed, a discovery surface, a
settings menu with more than a handful of items).

## Scope

This document covers: the top-level spaces in the product, what each one
is for, how a person moves between them, and what determines whether a
new space is ever justified. It does not cover what happens *inside* a
conversation turn by turn (see `interaction-architecture-v1.md`) or how
understanding is presented once you're looking at it (see
`memory-and-shared-understanding-v1.md`) — this document only answers
"what are the rooms in this house, and how do you get from one to
another."

---

## The Core Unit: The Thread

Before naming spaces, one modeling decision has to be made explicit,
because everything else follows from it: **a "conversation" in Confidant
is not a single sitting.** It is a persistent thread of understanding
about one situation in a person's life — a job transition, a specific
relationship, a decision they're circling — that can be returned to over
days or months, the same way the backend's WorldState is a per-situation
artifact that accumulates understanding turn by turn, not a disposable
chat log (see `engine/specs/WorldState-spec-v1.md`).

This matters architecturally because it means Confidant is not organized
around "conversations" the way a chat product is (a flat, chronological
list of sessions). It is organized around **threads** — one per
situation the person is actively making sense of — each of which the
person can step into and out of without ever "starting over."

---

## The Three Spaces

### 1. Home

The entry point. A calm, quiet list of the person's active threads —
what they're currently thinking through — and a single, unforced way to
begin a new one. This is explicitly **not a dashboard**: no counts, no
metrics, no "insights," no activity feed. If a person has one thread,
Home should feel like walking into a nearly-empty, welcoming room, not
like arriving at an empty analytics panel.

For a first-time user, Home is simply an invitation to start — closer to
a blank page than an onboarding wizard.

### 2. Thread

The primary space, where the actual work of the product happens. A
Thread contains two things, always available to each other, never
force-separated into different screens a person has to navigate between
mid-thought:

- the **live exchange** — the actual back-and-forth of thinking
  something through (see `interaction-architecture-v1.md`)
- the **accumulated understanding** for that specific situation — what
  Confidant currently understands, and what remains open (see
  `memory-and-shared-understanding-v1.md`)

Both facets belong to the same Thread and never to a separate global
space, because understanding is only ever meaningful in the context of
the specific situation it's about. A "career transition" thread's
understanding must never visually or structurally blend with a
"relationship" thread's — these are different situations, and treating
them as entries in one global "memory" feed would violate the
scoped, coherent sensemaking this entire product exists to protect.

### 3. Settings

Privacy controls, account basics, and data management (see
`trust-and-privacy-ux-v1.md`) — kept deliberately small. Settings is
where a person goes to exercise control they already know they have,
not a space they need to explore to discover what the product does.

**That's all.** No separate "history" browser, no "insights" surface, no
"community," no notification center. If a fourth space is ever proposed,
it needs to justify itself against the test below before it's allowed to
exist.

---

## Guiding Principles

### 1. Structure Should Be Invisible When It's Working

A person using Confidant should rarely think about "which space am I
in" — Home hands you to a Thread, and a Thread holds everything you need
while you're in it. Navigation should recede from awareness the moment
someone starts actually thinking about their situation, the same way
picking up a phone to call a trusted friend doesn't feel like navigating
a menu system.

### 2. One Thread, One Situation, One Understanding

Every space and transition in this architecture exists to preserve the
integrity of a single principle: understanding is scoped to a situation,
never pooled globally. This is why there is no cross-thread "memory"
view, no global search that blends situations, no single timeline that
merges everything a person has ever discussed with Confidant into one
feed.

### 3. New Spaces Are Expensive, Not Free

Every additional top-level space is a permanent tax on Simplicity — it's
one more thing a person has to learn exists, one more place their
attention can fragment across. A new space is justified only if it
answers a genuinely distinct question that Home, a Thread, or Settings
cannot answer without compromising what they're already for — the same
discipline the backend's System Architecture applies to adding a fifth
cognitive process (see `engine/specs/system-architecture-v2-
specification.md`'s Governing Test). Until that bar is cleared, new
concepts get folded into one of the three existing spaces or held back
entirely.

---

## Navigation Philosophy

Movement between spaces should be minimal, always reversible, and never
lossy — leaving a Thread and returning to it later must restore exactly
where a person left off, with no re-orientation cost beyond what's
genuinely useful (see `memory-and-shared-understanding-v1.md` for how
re-entry should feel). There is no concept of "closing" a Thread the way
one closes a browser tab or ends a chat session; a Thread is simply
paused until the person returns to it, because a real ongoing situation
in someone's life doesn't have a close button either.

Navigation should never interrupt an in-progress moment of thinking.
Concretely: a person should never be pulled out of a live exchange by a
navigation prompt, a notification, or an unrelated piece of interface —
if something needs their attention outside the current Thread, it waits
until they've naturally reached a pause, not the other way around.

---

## Design Rationale

### Why Three Spaces, Not More

Every additional space considered during this document's drafting
(a "history" browser separate from Threads, a global "understanding"
view, a "reflections" journal) turned out, on inspection, to be either a
duplicate of what a Thread already provides, or a violation of the
"understanding is scoped to a situation" principle. Naming exactly three
spaces isn't an arbitrary constraint — it's the result of applying that
principle until nothing further survived it.

### Why "Thread" Instead of "Conversation"

"Conversation" implies something that starts and ends in one sitting,
which is precisely the wrong mental model for a product meant to
support someone through an ongoing situation across weeks or months.
"Thread" was chosen because it survives the test of time the way a real
situation does — it can be picked up, set down, and picked back up
without contradiction.

### Why Settings Is Small By Design

A large, feature-rich settings area is usually a sign that a product has
accumulated configuration options faster than it has resolved product
decisions. Confidant's philosophy already resolves nearly every question
a settings screen would otherwise need a toggle for (no notification
preferences to configure, because there are close to no notifications;
no personalization dials, because personalization itself is treated
with suspicion — see `frontend-philosophy-v1.md`'s anti-goals). What
remains in Settings should stay genuinely minimal for as long as the
philosophy holds.

---

## Future Considerations

- If Confidant ever supports multiple people collaboratively examining
  a shared situation (e.g., a couple working through something together
  with mutual consent), that is a genuinely new information-architecture
  question — not an extension of the single-person Thread model — and
  would need its own deliberate design pass, not a quiet addition to
  this one.
- If the product ever needs a way to archive or retire a Thread that's
  no longer active (a resolved situation, a decision already made), that
  should be designed as a state a Thread can be in, not a new space —
  consistent with "new spaces are expensive."
- This document assumes a single primary surface (a web or app
  experience a person deliberately opens). If Confidant is ever
  reachable through an ambient or messaging-embedded surface, that
  requires its own information architecture, explicitly reconciled with
  this one rather than assumed to inherit it.
