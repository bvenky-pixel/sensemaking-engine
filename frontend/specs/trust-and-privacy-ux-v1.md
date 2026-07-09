# Confidant Trust & Privacy UX v1

Status: Depends on `frontend-philosophy-v1.md` and
`emotional-design-v1.md`. Where Emotional Design defines the felt
warmth and calm of the product, this document defines the *structural*
half of trust — what the interface shows, controls, and discloses about
how a person's private thinking is handled. Trust here is not a feeling
to be evoked; it is a set of concrete, checkable commitments the
interface must keep visible.

---

## Purpose

Confidant's entire premise depends on a person being willing to think
out loud about something they would not say to most people. That
willingness does not come from a privacy policy link in a footer — it
comes from the interface itself continuously demonstrating that it
respects the sensitivity of what's being shared. This document defines
what that demonstration looks like as an ongoing UX responsibility, not
a one-time consent screen.

## Scope

This document covers: what the interface discloses about data handling
and AI processing, what control the user has over their own history and
understanding, how transparency about the system's own confidence and
limitations is surfaced, and the UX patterns that build or destroy trust
over the course of repeated use. It does not cover the legal content of
a privacy policy, security implementation, or authentication mechanics —
those are policy and engineering concerns this document assumes exist,
but does not design.

---

## Guiding Principles

### 1. Trust Is Demonstrated Continuously, Not Declared Once

A single onboarding screen that says "your data is private" is a
declaration, not a demonstration, and it is forgotten within a session.
Trust must instead be legible at the moments it's actually being tested:
when a person is about to share something sensitive, when they return to
a previous conversation, when they're deciding whether to let Confidant
remember something across sessions. The interface's job is to make the
honest answer to "what happens to this" available exactly when someone
would naturally wonder it — not buried in settings they'd have to go
looking for.

### 2. The User Controls Their Own Memory

Because Confidant builds a shared, evolving understanding of a person's
situation (mirroring the backend's WorldState), the interface must give
the user real, visible control over that understanding — the ability to
see what Confidant currently believes about their situation, correct it,
and remove it. A shared understanding the user cannot see or correct is
not a partnership; it is surveillance with a friendly interface. This
principle is the frontend's obligation to the backend's own "the user
owns the conclusions" commitment (see `frontend-philosophy-v1.md`) —
it must extend to owning the *record* of those conclusions too.

### 3. Uncertainty Disclosure Is a Trust Feature, Not a Liability Disclaimer

When the backend's Judgment is genuinely uncertain (low confidence, open
unknowns, unresolved contradictions — see
`engine/specs/judgment-specification-v2.md`), the interface showing that
uncertainty plainly is one of the strongest trust signals available,
not a weakness to be hidden behind confident-sounding phrasing. A
product that only ever sounds certain is, over time, less trustworthy
than one that visibly knows the difference between what it's confident
about and what it isn't.

### 4. Nothing About Processing Should Feel Hidden or Surprising

If the system is doing something with what the user shares — storing
it, using it to inform a later conversation, treating a past decision as
still relevant — that should never be something the user discovers by
accident (Confidant unexpectedly referencing something they don't
remember telling it, in a way that reads as unsettling rather than
attentive). Continuity should always be introduced in a way the user
recognizes and can trace back to something they actually said.

### 5. Deletion and Forgetting Must Be Real, Not Cosmetic

If a person removes something from their shared understanding with
Confidant, the interface must never let it quietly persist and resurface
later — that specific failure (saying something is deleted while
behavior shows otherwise) is one of the fastest, most permanent ways to
destroy the trust this entire product depends on. This principle
constrains the frontend to only ever promise deletion behavior the
underlying system genuinely provides — it must not get ahead of the
actual guarantee.

---

## Design Rationale

### Why Trust Gets Its Own Document Instead of Living Inside Emotional Design

Emotional warmth and structural trust can point in different directions
under pressure. A warm, reassuring tone can just as easily be used to
paper over a genuine limitation ("don't worry, I've got this!") as a
cold, clinical one can undermine trust despite being perfectly accurate.
Trust needs its own document specifically so that warmth is never
allowed to substitute for honesty — the two must be independently
satisfied, not traded off against each other.

### Why Memory Control Is a Trust Concern and Not Only a Feature of
`memory-and-shared-understanding-v1.md`

The *existence* of visible, correctable memory is designed in the Memory
& Shared Understanding document. This document is concerned with the
*trust obligation* that existence creates — once Confidant remembers
things about a person, the product has taken on a continuous
responsibility to keep that memory legible and controllable, for as long
as the relationship continues. Memory & Shared Understanding designs the
mechanism; this document is the standing check that the mechanism
actually discharges the trust obligation, not just the functional
requirement.

### Why This Document Doesn't Try to Design Consent Screens or Legal Copy

Consent UI and privacy-policy content are downstream execution of the
principles here, and they change with legal requirements far more often
than the underlying trust principles do. Coupling this document to
specific consent-flow wireframes would make it fragile in exactly the
place it should be most stable.

---

## Future Considerations

- A concrete "Memory & Understanding" surface — where a user can browse,
  correct, or remove what Confidant currently understands about their
  situation — is implied here but formally specified in
  `memory-and-shared-understanding-v1.md`. That document should be
  checked against this one's control and legibility principles before
  being considered complete.
- As real conversations accumulate, this document should be revisited
  once there is evidence about which specific trust moments (first
  session, returning after a gap, being shown a remembered detail) carry
  the most weight — right now these principles are derived from the
  product's philosophy, not yet from observed user behavior.
- If Confidant ever introduces any cross-conversation learning at the
  System Architecture level (see `engine/specs/system-architecture-v2-
  specification.md`'s Learning process, currently a deliberately
  unimplemented reserved slot), this document will need a direct
  amendment addressing what that learning discloses to the user, since
  today it assumes memory is scoped to what a specific user can see and
  control about their own history alone.
