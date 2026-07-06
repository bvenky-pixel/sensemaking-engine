# Confidant Design Tokens & Component Philosophy v1

Status: Depends on `visual-design-system-v1.md`,
`motion-and-latency-philosophy-v1.md`, and
`accessibility-and-responsive-design-v1.md`. This document is the
conceptual bridge between the design language those three documents
establish and an implementable system — it stays at the level of
*what the system's contract is and why*, deliberately stopping short of
naming specific components, props, or literal token values.

---

## Purpose

Every principle in the Visual Design System, Motion & Latency
Philosophy, and Accessibility documents needs to eventually become
something consistent and reusable, or it will drift — a slightly
different shade of warm neutral on every screen, a slightly different
spacing rhythm in every new feature, each individually reasonable and
collectively a slow erosion of the coherence those documents describe.
This document exists to state *why* a token-and-component system is the
right way to prevent that drift, and what such a system is obligated to
preserve, without prescribing its literal implementation.

## Scope

This document covers: what a design token is for in this product, what
a component's job is (and isn't), and the boundary between "the system
enforces this" and "a screen is free to decide this." It does not
specify actual token names, values, or a component library's API
surface — those are engineering execution, informed by this document
but not decided by it.

---

## Guiding Principles

### 1. Tokens Exist to Make Drift Impossible, Not to Make Customization Easy

A design token (a named, reusable value standing in for a raw color,
spacing amount, or duration) is not primarily a developer-convenience
feature. Its actual job in this product is to make it structurally
difficult to introduce a value that hasn't been checked against
`visual-design-system-v1.md`'s philosophy. If a token system makes it
just as easy to reach for an arbitrary, un-vetted value as to use the
sanctioned one, it has failed at its actual purpose, regardless of how
convenient it is.

### 2. A Component's Job Is to Encode a Decision, Not Just Render One

A component in this system should represent a specific, already-made
design decision (how a Reflecting turn is presented, how the
understanding surface renders an open question) — not a generic,
infinitely configurable primitive that leaves the actual decision to
whoever uses it. A component library full of flexible, unopinionated
primitives quietly pushes every one of this document set's hard-won
decisions back onto individual screens to re-decide, which is exactly
the drift this system exists to prevent.

### 3. Restraint Is Enforced by What the System Refuses to Offer

The strongest way to keep the product from drifting toward the
gamified, cluttered, or performative patterns ruled out in
`frontend-philosophy-v1.md` is to simply not build the components that
would encourage them — no badge component, no streak-counter primitive,
no confetti or celebratory-animation component (see
`motion-and-latency-philosophy-v1.md`'s restraint principles). A
component system enforces philosophy as much by what it withholds as by
what it provides.

### 4. Every Token and Component Must Trace to a Principle, Not a Preference

If a proposed token or component can't be traced back to a specific
principle in `visual-design-system-v1.md`, `motion-and-latency-
philosophy-v1.md`, or `accessibility-and-responsive-design-v1.md`, it
doesn't belong in the system yet — it's a preference looking for a
justification after the fact. This keeps the system's growth
deliberate rather than opportunistic.

### 5. Accessibility Requirements Are Built Into the Token Layer, Not Layered On Top

Contrast ratios, minimum touch target sizing, and reduced-motion
alternatives (see `accessibility-and-responsive-design-v1.md`) must be
properties of the tokens and components themselves — satisfied by
construction — rather than a constraint every individual screen has to
remember to check separately. A component that can be misused into an
inaccessible state is an incomplete component, not a correctly-used one
whose caller made a mistake.

---

## Design Rationale

### Why This Document Stops Short of Naming Actual Values or Components

Naming a specific token (e.g., a literal color value) or a specific
component (e.g., a literal "ReflectionCard" with a defined prop
signature) here would make this document an implementation
specification wearing an architecture document's title — and,
critically, it would freeze decisions that should be made once real
screens are being built and iterated on with actual content, not
decided in the abstract. This document's job is to make sure that,
whenever those concrete decisions are made, they're made against a
clear, agreed contract rather than improvised per-component.

### Why Opinionated Components Are Preferred Over Flexible Primitives

A flexible, generic component system is usually considered a virtue in
software design because it maximizes reuse and reduces duplication.
Confidant's situation inverts that calculus: the risk here isn't
insufficient reuse, it's that flexibility becomes a backdoor for
re-litigating decisions this entire document set already made
carefully. An opinionated component that's harder to misuse into
something off-philosophy is worth more here than a flexible one that's
easier to compose but easier to drift with.

### Why Withheld Components Matter as Much as Provided Ones

Teams under normal product pressure will eventually be asked to build
something this document set rules out (a streak indicator, a
celebratory badge). The strongest, most durable defense against that
pressure is a system that simply doesn't have the building blocks for
it readily available — making the off-philosophy request meaningfully
more expensive than reaching for an existing, on-philosophy component,
rather than relying on someone remembering to say no in the moment.

---

## Future Considerations

- Once real components exist, this document should be used as the
  standing test for any new one proposed: what principle does it trace
  to, and what does it refuse to allow — the same audit discipline
  `engine/decisions.md` applies to backend schema changes.
- A living component inventory (what exists, what it encodes, what
  principle it traces to) is a natural, concrete follow-on artifact once
  implementation begins — but it documents decisions already made under
  this philosophy, it does not replace this document as the place those
  decisions get justified.
- If real usage reveals a genuine need this system currently refuses to
  support (principle 3's withheld components), that need should be
  argued explicitly against `frontend-philosophy-v1.md` before a new
  component is added — not quietly built as a one-off exception that
  bypasses the system.
