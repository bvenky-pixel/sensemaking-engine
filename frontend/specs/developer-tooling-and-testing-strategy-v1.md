# Confidant Developer Tooling & Testing Strategy v1

Status: Depends on `frontend-engineering-architecture-v1.md`, and
transitively on every document in `frontend/specs/`. This is the final
document in the frontend architecture set. Where every prior document
defines what the product must be, this one defines what it takes to
keep it that way for years, across many contributors, without the
principles quietly eroding the way `frontend-philosophy-v1.md` warns
they can.

---

## Purpose

A design philosophy that only lives in Markdown files is not durable —
it survives only as long as everyone who read these documents remains
on the team and remembers them clearly. This document exists to define
what tooling and testing practices are needed so that the principles in
every other document in this set are checked continuously, by the
team's ordinary working process, rather than depending on memory or
goodwill alone.

## Scope

This document covers: the philosophy behind what developer tooling must
make easy (and what it must make deliberately hard), and what testing
strategy is needed to keep the product honest to its own architecture
over time. It does not name specific tools, test frameworks, or CI
configuration — those are implementation choices made in service of the
principles here, the same relationship this document set has held
throughout between philosophy and execution.

---

## Guiding Principles

### 1. Tooling Should Make the Right Thing Easy and the Wrong Thing Effortful

Consistent with `design-tokens-and-component-philosophy-v1.md`'s "the
system enforces restraint by what it refuses to offer," developer
tooling should make it noticeably harder to bypass this document set's
principles than to follow them — a linting or review process that
flags an unvetted color value, a raw spacing number, or a new
component that doesn't trace to a stated principle, catches drift at
the moment it's introduced rather than after it's shipped and normalized.

### 2. Fast, Low-Friction Iteration Is a Prerequisite for Getting the Feel Right

Confidant's success depends on subtle, felt qualities — the exact pacing
of a "Considering" state, the precise warmth of a neutral background —
that cannot be correctly judged from a specification alone; they have to
be built, seen, and adjusted repeatedly. Developer tooling that makes
that iteration loop slow or high-friction directly threatens the
product's ability to actually achieve what `emotional-design-v1.md` and
`visual-design-system-v1.md` describe, regardless of how well those
documents are written.

### 3. Philosophy Conformance Is a Real Testing Category, Not a Vibe Check Left to Design Review

Alongside conventional functional correctness, Confidant's testing
strategy must treat conformance to this document set as directly
testable where it can be: does a given screen ever surface raw backend
vocabulary (`memory-and-shared-understanding-v1.md`'s "not a debug
view" principle)? Does an error state ever discard a stage's genuine
partial progress (`frontend-engineering-architecture-v1.md`'s
partial-completion honesty)? Wherever a principle can be expressed as a
checkable assertion, it should be — not left entirely to a human
reviewer's memory of a document they read once.

### 4. Partial-Completion and Failure States Deserve Explicit, First-Class Test Coverage

Because the backend's own architecture is explicitly designed around
honest partial completion (see `engine/specs/system-architecture-v2-
specification.md`'s Orchestrator), the frontend's handling of every
possible stopping point — a turn that got through Interpretation but
no further, one that completed everything but Response — must be
tested directly and individually, not assumed to be covered
incidentally by testing the fully-successful path. A testing strategy
that only exercises the happy path leaves this product's most important
trust behavior — honesty under failure — completely unverified.

### 5. State-Fidelity Must Be Testable, Not Just Believed

`frontend-engineering-architecture-v1.md`'s "reflection of backend
truth, never a second copy" principle is only meaningful if it can be
verified — tests should be able to assert that the frontend's
representation of a Thread's understanding can never diverge from what
the backend actually returned, and specifically that a person's
correction to shared understanding isn't treated as complete until the
backend has confirmed it. This is the frontend's testable discharge of
`trust-and-privacy-ux-v1.md`'s "deletion and forgetting must be real."

### 6. Accessibility and Reduced-Motion Behavior Are Tested, Not Assumed

Consistent with `accessibility-and-responsive-design-v1.md`'s
"accessibility is part of the product's core promise," automated
checks for the technical baseline (contrast, focus order, reduced-motion
alternatives) should run continuously as part of ordinary development,
not as a separate, periodic audit — while also being understood as a
floor, not a substitute for the qualitative check with real assistive-
technology users that document calls for.

---

## Design Rationale

### Why Philosophy Conformance Belongs in Testing Strategy at All

It would be easy to treat everything in this document set as "design
guidance" that lives outside the codebase and is enforced only through
review and taste. But taste and review attention are exactly the
resources `frontend-philosophy-v1.md` warns dilute fastest under
ordinary product pressure — a hundred individually-reasonable
decisions, each slightly off-philosophy, are how drift actually
happens. Wherever a principle can be turned into an automated check, it
should be, precisely because automated checks don't get tired, rushed,
or overruled by a deadline the way a reviewer's judgment can.

### Why This Document Prioritizes Iteration Speed as a Design Concern, Not Just a Developer-Experience Nicety

It's tempting to treat "developers can iterate quickly" as orthogonal to
the product's actual design quality — a nice-to-have for the team,
separate from what the person using Confidant experiences. This
document rejects that separation: the specific, subtle emotional
qualities this product depends on (see `emotional-design-v1.md`,
`motion-and-latency-philosophy-v1.md`) can only be tuned through
repeated, fast observation of the real thing — a slow, high-friction
build loop doesn't just frustrate developers, it directly limits how
well the product can actually achieve the feel this whole document set
describes.

### Why This Document Doesn't Name Specific Testing Tools or Frameworks

Naming a specific test runner, visual-regression tool, or CI platform
here would date this document the moment the team's tooling landscape
changes, without changing anything about what actually needs to be true
of the testing strategy. The principles above — conformance is testable,
partial completion is covered, state-fidelity is verifiable,
accessibility is continuously checked — should outlive several
generations of the specific tools used to satisfy them.

---

## Future Considerations

- As real philosophy-conformance checks are built, they should be
  tracked as a living inventory mapped back to the specific principle
  each one verifies — mirroring how `engine/decisions.md` keeps the
  backend's own decisions traceable and auditable over time.
- If the product ever needs performance regression testing specifically
  for the "frontend adds near-zero perceptible delay" principle in
  `frontend-engineering-architecture-v1.md`, that requires establishing
  a real, measured baseline first — this document only commits to the
  principle being tested, not yet to how that measurement should work.
- This document assumes a single frontend codebase and team. If the
  frontend is ever split across multiple surfaces or teams (see
  `information-architecture-v1.md`'s future consideration about a
  possible second product surface), tooling and testing strategy will
  need an explicit amendment addressing how philosophy conformance is
  kept consistent across them, since today it assumes one shared set of
  tooling enforcing one shared set of principles.
