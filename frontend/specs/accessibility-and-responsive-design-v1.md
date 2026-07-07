# Confidant Accessibility & Responsive Design v1

Status: Depends on `frontend-philosophy-v1.md` and
`visual-design-system-v1.md`. This document treats accessibility and
responsive behavior as one concern — ensuring the calm, safe experience
this product depends on holds up across different people, devices, and
circumstances, not just under ideal conditions.

---

## Purpose

A product built on trust and psychological safety has a specific
obligation: those qualities cannot be reserved for people using a large
screen, a mouse, full vision, and complete attention. If Confidant only
feels calm and safe under ideal conditions, it has not actually achieved
calm and safety — it has achieved them for a subset of the people who
might need it most. This document exists to make that obligation
concrete rather than aspirational.

## Scope

This document covers: the principles governing accessible interaction
(for people using assistive technology, differing vision, motor, or
cognitive needs) and adaptive behavior (for different screen sizes,
input methods, and contexts of use). It does not specify a compliance
checklist or exact technical implementation — those belong to
engineering execution once these principles are agreed, and to
`developer-tooling-and-testing-strategy-v1.md`'s testing commitments.

---

## Guiding Principles

### 1. Accessibility Is Part of the Product's Core Promise, Not a Compliance Layer

Confidant's brand promise is "we can figure this out together" — that
promise cannot be conditional on how someone perceives or navigates an
interface. Treating accessibility as a checklist applied after design is
"done" produces exactly the kind of bolted-on, second-class experience
this principle rejects. Accessibility considerations belong in the same
design conversation as color, spacing, and motion — not a separate
audit that happens afterward.

### 2. Calm and Safety Must Survive Assistive Technology

Someone using a screen reader, voice control, or switch access should
experience the same fundamental qualities — private, unhurried, earnest
— as someone using the product visually. This means, concretely, that
information conveyed visually (the distinction between a Clarifying and
Reflecting turn, for instance — see `interaction-architecture-v1.md`)
must have an equivalent, equally legible non-visual expression, not a
degraded fallback that merely exposes raw content without its meaning.

### 3. Motion and Pacing Must Be Adjustable Without Losing Meaning

Because `motion-and-latency-philosophy-v1.md` treats motion as
meaningful rather than decorative, a person who needs reduced motion
must still receive the *meaning* that motion was carrying (that
something is being considered, that a new understanding has appeared) —
just delivered through a non-motion channel, never simply removed and
left unexplained. Reduced motion is a presentation preference, not a
license to drop the information the motion was conveying.

### 4. Responsive Behavior Follows Attention, Not Just Screen Size

Adapting to a smaller screen is not only a layout problem (things fit)
but an attention problem (what deserves focus changes as available
space shrinks). On a small screen, the live exchange in a Journey should
take priority over simultaneous visibility of the full understanding
surface (see `interaction-model-v4.md`) — accessible on
demand, not competing for the same limited space. Responsive design
here means asking what a person's attention can actually hold in a
given context, not just what technically fits.

### 5. Text Must Remain Comfortable to Read at Every Supported Size

Because sustained, comfortable reading is a stated priority of the
visual design system (see `visual-design-system-v1.md`), text resizing
(for people who need larger text) must never break the layout or force
truncation of a person's own words or Confidant's understanding of
their situation — both are exactly the content this product cannot
afford to clip or hide.

### 6. Input Method Should Never Gate Participation

A person should be able to share something thoughtful and receive a
considered response whether they're typing on a keyboard, using voice
input, or navigating entirely without a pointing device. No interaction
essential to a Journey's core lifecycle (see
`interaction-model-v4.md`) may depend on a single input modality
that excludes another.

---

## Design Rationale

### Why Accessibility and Responsive Design Share One Document

Both are, at root, the same underlying design question: does this
experience hold up outside of the one ideal condition it was probably
first designed for? Separating them tends to produce two different
compliance exercises rather than one coherent design stance. Treating
them together keeps the underlying question — "for whom, and under what
conditions, does this still feel calm and safe" — visible as a single,
continuous responsibility rather than two separate checklists that can
each be satisfied narrowly without the other.

### Why This Document Doesn't Cite Specific Technical Standards

Formal accessibility standards exist and should absolutely inform
implementation, but citing a specific standard's clause numbers here
would make this document read as compliance documentation rather than
design philosophy — and would risk the team treating "meets the
standard" as equivalent to "actually accessible," when a technically
compliant experience can still fail principle 2 above (equivalent
non-visual expression of meaning, not just of raw content). The
technical compliance target belongs in engineering execution and
testing strategy; this document's job is to state what a compliant
implementation is actually in service of.

---

## Future Considerations

- Once real screens and components exist, this document should be
  checked directly against them with people who actually use assistive
  technology, not only against automated compliance tooling — automated
  tools can confirm technical compliance but cannot confirm that
  principle 2's "equivalent meaning" claim is actually true.
- Internationalization and localization are closely related to
  responsive behavior (text length varies significantly across
  languages, affecting the same layouts this document discusses) but
  are deliberately out of scope here — they deserve their own explicit
  treatment once localization is a real product priority, not a
  retrofit assumed to be covered by this document's silence.
- If Confidant is ever used in genuinely low-connectivity or
  low-power-device contexts, that introduces adaptive requirements
  beyond screen size alone, and should be treated as a deliberate
  extension of this document rather than assumed to already be handled.
