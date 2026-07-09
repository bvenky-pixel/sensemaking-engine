# Confidant Frontend Engineering Architecture v1

Status: Depends on `information-architecture-v1.md`,
`interaction-architecture-v1.md`,
`memory-and-shared-understanding-v1.md`, and
`design-tokens-and-component-philosophy-v1.md`. This document defines
how the frontend is technically organized to serve everything those
documents establish — as architectural decisions (what the frontend
must be true to, what it must never do), not as a choice of framework,
library, or literal code structure.

---

## Purpose

Every document so far has described what the product must feel like and
look like. None of them, on their own, constrain how the frontend
actually stays honest to a real backend that reasons in multiple
sequential stages, can partially fail mid-turn, and produces an evolving
understanding that must never silently diverge between what the backend
believes and what the interface shows. This document exists to state
those constraints explicitly, so that engineering decisions made later —
in any framework, using any state library — can be checked against a
shared architectural contract rather than reinvented ad hoc.

## Scope

This document covers: the philosophy of how frontend state relates to
backend truth, how the frontend should behave when the backend's
real pipeline (Interpretation → WorldState → Judgment → Planner →
Response — see `engine/specs/system-architecture-v2-specification.md`)
completes partially or fails at some stage, and what "performance"
means for a product whose backend has genuine, expected latency. It
does not name a specific framework, state management library, or API
protocol — those are implementation choices this document constrains
but does not make.

---

## Guiding Principles

### 1. The Frontend Holds a Reflection of Backend Truth, Never a Second Copy of It

The backend maintains the real, authoritative understanding of a
situation — WorldState, Judgment's assessment, Planner's chosen
direction. The frontend's state must be modeled as a *reflection* of
that truth, re-derived from what the backend actually returns, never as
an independently-maintained parallel model that could quietly drift out
of sync. Concretely: if a person corrects something in the understanding
surface (see `memory-and-shared-understanding-v1.md`), the frontend does
not consider that correction "done" until the backend confirms it has
actually changed what it carries forward — the frontend never treats its
own optimistic local edit as equivalent to the backend's authoritative
state.

### 2. Partial Completion Must Be Represented Honestly, Not Papered Over

The backend's own Orchestrator is explicitly designed to report exactly
how far a turn got before something failed, rather than either
succeeding completely or raising an opaque error (see
`engine/specs/system-architecture-v2-specification.md`'s Orchestrator
section — a stage-level failure returns a result carrying everything
that succeeded up to that point). The frontend's architecture must
honor that same honesty: if Interpretation succeeded but Judgment
failed, the interface should reflect that a person's message was
genuinely heard and understood, without ever implying a complete,
considered response was produced when it wasn't. A generic "something
went wrong, try again" that discards a stage's real, successful partial
progress is a regression relative to what the backend already provides.

### 3. The Frontend's Own Latency Budget Is Separate From, and Subordinate to, the Backend's

`motion-and-latency-philosophy-v1.md` establishes that backend reasoning
time is honest and should be designed for, not hidden. That principle
only holds if the frontend adds negligible latency of its own on top of
it — a slow-to-respond interface layered on top of an honestly-paced
backend produces the worst of both: unhurried reasoning time plus
avoidable technical sluggishness, indistinguishable to the person
experiencing it. The frontend's performance goal is therefore not
"be as fast as possible" in the abstract, but specifically: make sure
every perceptible delay is attributable to genuine backend reasoning,
never to frontend inefficiency.

### 4. State Should Be Scoped to a Journey, Never Pooled Globally

Consistent with `information-architecture-v1.md`'s "one Journey, one
situation, one understanding," the frontend's state architecture must
enforce that a Journey's understanding cannot leak into, or be confused
with, another Journey's — architecturally, not just visually. This
matters specifically because a state layer that pools everything
globally for convenience (a single global cache of "all understanding")
makes the scoping violation this whole product depends on avoiding
trivially easy to introduce by accident later.

### 5. Every Network Interaction Has an Honest, Designed Waiting and Failure State

Because the backend's real pipeline can genuinely fail at any stage
(a provider outage, a schema validation failure downstream — see
`src/llm/providers.py`'s fallback chain and
`src/instrumentation/usage.py`'s recorded outcome types), every point
where the frontend calls into the backend must have a deliberately
designed waiting state (see `motion-and-latency-philosophy-v1.md`) and
a deliberately designed, honest failure state — never a default
technical error message that breaks the emotional register the rest of
this document set has established.

---

## Design Rationale

### Why "Reflection of Backend Truth" Instead of a More Conventional Client-State Model

Many products benefit from an optimistic, independently-maintained
client state layer for responsiveness — assume the edit succeeded,
update the UI immediately, reconcile later. Confidant cannot adopt that
pattern uncritically for anything touching shared understanding,
because `trust-and-privacy-ux-v1.md`'s "deletion and forgetting must be
real, not cosmetic" principle means a frontend that shows a correction
as accepted before the backend has actually incorporated it is making a
promise it doesn't yet know it can keep. Optimistic UI is still
permissible for genuinely low-stakes, easily-reversible interactions —
but never for anything representing the state of shared understanding
itself.

### Why Partial-Completion Handling Is an Architectural Principle, Not Just Error Handling

Treating "the backend partially completed a turn" as a special case of
generic error handling would bury one of this product's most important
trust behaviors inside ordinary failure-recovery code, where it's easy
to simplify away under time pressure ("let's just show one generic error
state for everything"). Elevating it to an explicit architectural
principle here is meant to make that simplification a visible violation
of this document, not an invisible shortcut.

### Why Performance Is Framed Relative to the Backend, Not as an Absolute Target

An absolute performance target ("under 200ms for every interaction")
would be either trivially satisfiable in ways that don't matter (a
button press animates instantly) or impossible to meet in ways that
don't matter either (the backend's real reasoning takes several
seconds, no frontend optimization changes that). Framing performance
relative to the backend's own latency — the frontend's job is to add as
close to zero perceptible delay as possible on top of it — gives
engineering a target that's actually meaningful for this specific
product, rather than a generic number borrowed from products with a
completely different latency profile.

---

## Future Considerations

- If the backend ever exposes intermediate progress during a turn
  (e.g., which stage is currently running), the frontend architecture
  should be revisited to decide whether and how that becomes part of
  the "Considering" experience (see `motion-and-latency-philosophy-
  v1.md`) — today's principles assume only start-of-turn and
  end-of-turn (or failure) as observable moments.
- This document assumes a single active Journey's state is what a
  person is interacting with at any moment. If simultaneous multi-Journey
  interaction ever becomes a real requirement, principle 4's
  Journey-scoping must be explicitly re-examined for how it should behave
  under true concurrency, not assumed to already handle it.
- A concrete technology selection (framework, state library, API
  transport) should be made only after this document is agreed, and
  should be evaluated primarily against how naturally it can satisfy
  principles 1, 2, and 4 above — ease of use or popularity are secondary
  criteria relative to whether the technology makes violating these
  principles easy or hard.
