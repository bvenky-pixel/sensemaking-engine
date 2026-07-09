# Confidant Frontend Philosophy v1

Status: FOUNDATIONAL. Every other frontend architecture document in
`frontend/specs/` traces back to this one. If a later document proposes
something this document doesn't support, the later document is wrong,
not this one — the fix is to revisit this document deliberately, the
same discipline `engine/decisions.md` applies to the backend.

---

## Purpose

This document exists to answer one question, permanently: *what is the
frontend FOR?*

Not what it looks like. Not what framework renders it. What it is for —
the reason a person opens it, the feeling it should leave them with, and
the promises it is not allowed to break in pursuit of any other goal
(growth, engagement, delight-as-decoration, competitive parity with
other AI products).

Every subsequent frontend document — emotional design, information
architecture, visual design, engineering architecture, all of it —
is a downstream consequence of this one. None of them are allowed to
introduce a goal that isn't traceable to this document, the same
constraint the backend's System Architecture places on itself relative
to the Sensemaking Engine.

## Scope

This document covers: what Confidant's frontend is, what it is
explicitly not, the brand promise, the three governing design
principles, and the anti-goals the whole product is built to resist.

It does not cover: visual language, interaction mechanics, component
architecture, or any implementation detail. Those are the job of the
documents that depend on this one.

---

## What Confidant Is

Confidant is a sensemaking companion.

Its job is to help a person think through something difficult — a
decision, a conflict, a pattern they can't quite name — by building a
*shared, accurate understanding* of the situation before anything
resembling advice enters the room. This is not a stylistic choice; it is
the same "understanding before reasoning, reasoning before response"
discipline the backend's Sensemaking Engine is built on
(Interpretation → WorldState → Judgment → Planner → Response Generator).
The frontend's entire job is to make that discipline *visible and
trustworthy* to the person living through it, not to route around it for
the sake of a faster or flashier experience.

## What Confidant Is Not

Confidant is not a chatbot. It is not a productivity tool. It is not
positioned against, or measured by the same instincts as, ChatGPT,
Copilot, or any general-purpose AI assistant. Those products are built
to be fast, capable, and endlessly available for any task. Confidant is
built to be slow where slowness is honest, narrow where narrowness is
respectful, and quiet where quietness is what trust actually requires.

Concretely, this means the frontend must resist every reflex borrowed
from productivity and consumer-engagement products:

- It should never feel like it is trying to be used *more*.
- It should never feel like it is trying to be used *faster*.
- It should never perform confidence it hasn't earned in that
  conversation.

## The Emotional Register

The frontend should feel like:

- a private place
- psychologically safe
- calm
- thoughtful
- warm
- earnest
- minimalist

The experience it should resemble is thinking out loud with someone you
deeply trust — not consulting an assistant, not operating a tool, not
querying a system. Every document downstream of this one exists to
protect that specific feeling against the thousand small decisions
(a loading spinner, a notification, a progress bar, a streak counter)
that would quietly erode it.

---

## Core Product Philosophy

**The frontend exists to protect the relationship between the user and
their own thinking.**

This is the single sentence every design decision in every downstream
document must be checked against. Not "does this look good," not "does
this feel modern," not "does this increase engagement" — does this
protect the user's relationship with their own thinking, or does it
quietly substitute Confidant's thinking for theirs?

Everything in the frontend should reinforce:

- **Understanding before advice.** The interface should never let a
  response arrive before the situation has genuinely been understood.
  If the backend hasn't earned the right to respond with confidence yet
  (low confidence scores, open unknowns, unresolved contradictions —
  see the backend's Judgment output), the frontend must not paper over
  that with a confident-sounding UI.
- **Reflection before action.** The product's job is to slow a person
  down enough to see their situation clearly, not to accelerate them
  toward a decision.
- **Partnership rather than authority.** Confidant proposes
  understanding; it does not issue verdicts. The interface should never
  visually imply that Confidant's read on a situation outranks the
  user's own.
- **Honesty over confidence.** An honest "I'm not sure yet, here's what
  I don't know" must be allowed to look and feel *complete* in the UI —
  not like a degraded or unfinished state. Uncertainty is a legitimate,
  well-formed output, not an error state to be hidden or rushed past.
- **Trust over engagement.** No design decision is justified by "it
  will bring people back more often" alone. It must also be justified by
  "it deepens trust in what Confidant says." If those two ever conflict,
  trust wins, unconditionally.

### Who Owns What

The user owns:

- their thoughts
- their decisions
- their reflections

**Confidant never owns the conclusions.** This is not a legal disclaimer
or a hedge — it is a structural design constraint. The frontend must
never present Confidant's output (a Judgment, a Planner's chosen
direction, a Response) in a visual register that implies finality or
authority the backend itself hasn't claimed. If the backend's own
Judgment carries a confidence of 0.4, the interface has no license to
present that content with the visual certainty of a confidence of 0.9.

---

## Brand Promise

> **"We can figure this out together."**

Read this promise carefully, because every principle below is just this
sentence unpacked:

- **"We"** — partnership, not a tool being operated. The frontend
  should never read as one-directional (person asks, system answers).
  It should read as two parties working on the same problem.
- **"can"** — capability without overpromising. Confident enough to be
  useful, never confident enough to override the user's own judgment.
- **"figure this out"** — the work is sensemaking, not verdict-issuing.
  The promise is clarity, not answers.
- **"together"** — the entire reason understanding must be built and
  shown, not just used invisibly behind a response. If the user can't
  see the understanding being built, "together" is a lie the interface
  is telling.

---

## Design Principles

Three principles govern every design decision in this document set, in
this priority order when they conflict:

### 1. Safety

Psychological safety is the precondition for the entire product working
at all — a person will not think out loud about something difficult in
an interface that feels like it might judge them, expose them, rush
them, or misrepresent them. Safety is not a feature (like an encryption
badge); it is the baseline every interaction is judged against. When
safety and any other consideration conflict, safety wins.

### 2. Simplicity

Simplicity here means *reductive*, not *minimal-looking*. A screen can
be visually spare and still be complex if it asks the user to hold too
many things in mind at once, or if it surfaces backend internals
(confidence scores, epistemic tier labels, provider names) that serve
engineering debugging rather than the user's actual thinking process.
Simplicity is a discipline about what NOT to show, applied as rigorously
to information architecture as to visual design.

### 3. Earnestness

Earnestness means the product never winks at the user, never performs
personality it hasn't earned, and never uses charm as a substitute for
genuine understanding. No AI-assistant quirkiness, no forced levity, no
gimmicks that exist to make the product feel clever. If a design
decision would make a thoughtful person wonder "is this trying to seem
smart, or is it actually being useful to me right now" — it fails this
principle.

When these three principles conflict, resolve in this order: **Safety
first, Simplicity second, Earnestness third.** A design that is earnest
but unsafe is wrong. A design that is simple but earns distrust by
hiding something the user needed to see is wrong. Only once safety and
simplicity are both satisfied does earnestness get to arbitrate the
remaining choice.

---

## Things Confidant Should Never Become

These are not omissions to revisit later. They are permanent
constraints, load-bearing in the same way the backend's System
Architecture treats its own Non-Goals (see
`engine/specs/system-architecture-v2-specification.md`) — a future
proposal to add one of these requires deliberately overturning this
document, not just shipping a feature.

Confidant must never adopt features that optimize for engagement rather
than thinking:

- **Daily streaks.** A person's difficult situation doesn't run on a
  calendar cadence, and implying it should is a trust violation, not a
  motivational nudge.
- **Gamification, badges, leaderboards.** These frame sensemaking as
  performance. Sensemaking is not a performance.
- **Social features.** A private place stops being private the moment
  it has an audience, real or implied.
- **AI gimmicks.** Novelty for its own sake (avatars, personas,
  playful error messages) undercuts earnestness directly.
- **Unnecessary notifications.** Every notification is a claim that
  Confidant's schedule matters more than the user's. It rarely does.
- **Excessive personalization.** Personalization that exists to
  increase stickiness (streak reminders, "come back and see what's
  new") is engagement optimization wearing a UX costume.
- **Cluttered dashboards.** A dashboard's job is usually to make you
  feel busy. Confidant's job is to help you feel clear.

The test for any proposed feature, forever: *does this help someone
think more clearly about something that matters to them, or does it
help the product get used more often?* If the honest answer is the
second one, the feature does not belong in Confidant, regardless of how
common it is elsewhere.

---

## Design Rationale

Why root the entire frontend in a single philosophy document rather than
starting from user flows or a component library, as most frontend
projects do?

Because Confidant's core risk is not "the interface is confusing" — it's
"the interface accidentally teaches the wrong relationship between the
user and the AI." A subtly wrong loading spinner, a subtly overconfident
response card, a subtly gamified streak counter — none of these are
bugs in the conventional sense. They are philosophy violations that will
look, in isolation, like completely reasonable, industry-standard UX
decisions. The only defense against death by a thousand reasonable
decisions is a single, explicit, load-bearing document that every one of
those decisions can be checked against before it ships.

This mirrors exactly why the backend needed
`engine/specs/system-architecture-v2-specification.md`'s Governing Test
before a fifth component could be considered: without a standing,
written principle to check against, each individual addition looks
justified on its own terms, and only in aggregate does the drift become
visible — usually too late.

## Future Considerations

- As real usage accumulates, some of these principles may need
  calibration (e.g., what "earnest" tolerance for warmth-without-levity
  actually looks like to real users) — but recalibration must happen by
  deliberately revisiting this document and logging why, the same
  discipline `engine/decisions.md` requires for backend changes. It must
  never happen by accretion of individual feature decisions that quietly
  reinterpret a principle.
- If Confidant ever needs a second product surface (e.g., a
  lightweight check-in mode, or an admin/observability view for the team
  operating the System Architecture layer), that surface needs its own
  philosophy document, explicitly scoped as either inheriting or
  deliberately diverging from this one — it must not silently borrow this
  document's promises for a product experience this document didn't
  anticipate.
- This document deliberately does not attempt to anticipate every
  future feature request. Its job is to make future feature decisions
  easy to evaluate, not to enumerate every feature Confidant will ever
  have.
