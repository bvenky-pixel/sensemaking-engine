# Confidant Information Architecture v1

**Superseded 2026-07-21 by `information-architecture-v2.md`** (backlog
#260-267) — the founder confirmed a deliberate, explicit departure from
this document's own "exactly three spaces" count (Activity and You both
judged to clear this document's own "genuinely distinct question" test
for a new space, applying that test again rather than lowering its
bar). Kept here in full, unedited below, as the visible reasoning
trail — the same treatment `interaction-model-v4.md` gave
`interaction-model-v2.md`/`v3.md`.

Status: Depends on `frontend-philosophy-v1.md`. Terminology updated —
every prior use of "Thread" below now reads "Journey," matching
`interaction-model-v4.md`, which is also now the authoritative source for
what a Journey (and a Session within one) actually is. This document no
longer defines that concept itself; it only names the top-level spaces
and the navigation philosophy connecting them. It is deliberately short —
the same "Simplicity" principle that governs every other design decision
in this product also governs how much structure the product is allowed
to have.

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
new space is ever justified. It does not cover what a Journey or Session
*is*, or what happens inside one turn by turn (see
`interaction-model-v4.md`) — this document only answers "what are the
rooms in this house, and how do you get from one to another."

---

## The Three Spaces

### 1. Home

The entry point. A calm, quiet list of the person's active Journeys —
what they're currently thinking through — and a single, unforced way to
begin a new one. This is explicitly **not a dashboard**: no counts, no
metrics, no "insights," no activity feed. If a person has one Journey,
Home should feel like walking into a nearly-empty, welcoming room, not
like arriving at an empty analytics panel.

For a first-time user, Home is simply an invitation to start — closer to
a blank page than an onboarding wizard.

### 2. Journey

The primary space, where the actual work of the product happens. A
Journey is not defined here — see `interaction-model-v4.md` for what a
Journey and a Session within it actually are — but architecturally, a
Journey always holds two things together, never force-separated into
different screens a person has to navigate between mid-thought:

- the **live exchange** — the current Session's actual back-and-forth of
  thinking something through
- the **accumulated understanding** for that specific situation — what
  Confidant currently understands, and what remains open (see
  `interaction-model-v4.md`'s "Letting the Architecture Be Felt")

Both facets belong to the same Journey and never to a separate global
space, because understanding is only ever meaningful in the context of
the specific situation it's about. A "career transition" Journey's
understanding must never visually or structurally blend with a
"relationship" Journey's — these are different situations, and treating
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
in" — Home hands you to a Journey, and a Journey holds everything you
need while you're in it. Navigation should recede from awareness the
moment someone starts actually thinking about their situation, the same
way picking up a phone to call a trusted friend doesn't feel like
navigating a menu system.

### 2. One Journey, One Situation, One Understanding

Every space and transition in this architecture exists to preserve the
integrity of a single principle: understanding is scoped to a situation,
never pooled globally. This is why there is no cross-Journey "memory"
view, no global search that blends situations, no single timeline that
merges everything a person has ever discussed with Confidant into one
feed — the one deliberate exception being the "something noticed across
Journeys" moment `interaction-model-v4.md` explicitly defers until the
backend's Learning process actually exists.

### 3. New Spaces Are Expensive, Not Free

Every additional top-level space is a permanent tax on Simplicity — it's
one more thing a person has to learn exists, one more place their
attention can fragment across. A new space is justified only if it
answers a genuinely distinct question that Home, a Journey, or Settings
cannot answer without compromising what they're already for — the same
discipline the backend's System Architecture applies to adding a fifth
cognitive process (see `engine/specs/system-architecture-v2-
specification.md`'s Governing Test). Until that bar is cleared, new
concepts get folded into one of the three existing spaces or held back
entirely.

---

## Navigation Philosophy

Movement between spaces should be minimal, always reversible, and never
lossy — leaving a Journey and returning to it later must restore exactly
where a person left off, with no re-orientation cost beyond what's
genuinely useful (see `interaction-model-v4.md` for how returning to a
Journey should feel). There is no concept of "closing" a Journey the way
one closes a browser tab or ends a chat session; a Session simply ends,
and the Journey itself is paused until the person returns, because a
real ongoing situation in someone's life doesn't have a close button
either.

Navigation should never interrupt an in-progress moment of thinking.
Concretely: a person should never be pulled out of a live exchange by a
navigation prompt, a notification, or an unrelated piece of interface —
if something needs their attention outside the current Journey, it waits
until they've naturally reached a pause, not the other way around.

---

## Design Rationale

### Why Three Spaces, Not More

Every additional space considered during this document's drafting
(a "history" browser separate from Journeys, a global "understanding"
view, a "reflections" journal) turned out, on inspection, to be either a
duplicate of what a Journey already provides, or a violation of the
"understanding is scoped to a situation" principle. Naming exactly three
spaces isn't an arbitrary constraint — it's the result of applying that
principle until nothing further survived it.

### Why This Document Doesn't Define "Journey" Itself

An earlier version of this document defined the core unit directly (it
called it a "Thread" and argued for that name over "conversation"). That
definition and its naming rationale now live in `interaction-model-v4.md`,
which frames the concept emotionally — a relationship that continues, not
an archive — rather than structurally. Keeping two definitions of the
same concept in two documents is exactly the kind of duplication this
document's own "New Spaces Are Expensive" principle warns against, so
this document now only names the space and cross-references the
concept.

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
  question — not an extension of the single-person Journey model — and
  would need its own deliberate design pass, not a quiet addition to
  this one.
- If the product ever needs a way to archive or retire a Journey that's
  no longer active (a resolved situation, a decision already made), that
  should be designed as a state a Journey can be in, not a new space —
  consistent with "new spaces are expensive."
- This document assumes a single primary surface (a web or app
  experience a person deliberately opens). If Confidant is ever
  reachable through an ambient or messaging-embedded surface, that
  requires its own information architecture, explicitly reconciled with
  this one rather than assumed to inherit it.
