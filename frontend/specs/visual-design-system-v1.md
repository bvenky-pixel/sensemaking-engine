# Confidant Visual Design System v1

Status: Depends on `frontend-philosophy-v1.md` and
`emotional-design-v1.md`. This document is the visual expression of
those two documents' claims — color, typography, and spacing are treated
as one design language here, not three independent systems, because a
person experiences them simultaneously as a single felt impression of
the product, not as separable channels.

---

## Purpose

Emotional Design defines what calm, warmth, and earnestness must mean
functionally (pacing, tone, restraint). This document defines what they
must look like — the visual vocabulary that makes a screen feel like a
private, safe place to think, rather than a productivity tool or a
generic AI chat interface, before a single word of copy is read.

## Scope

This document covers: the philosophy behind color choice, typographic
character, and spatial rhythm as one coherent visual language. It does
not specify literal hex values, a type scale in points, or spacing
values in pixels — those are implementation decisions that belong to
`design-tokens-and-component-philosophy-v1.md` once this document's
philosophy is agreed. This document answers "what is this system trying
to feel like," not "what are its exact values."

---

## Color Philosophy

### Color Communicates Restraint, Not Brand

Most products use color to express energy, brand personality, or to
draw the eye toward action (a bright call-to-action button, a saturated
accent used everywhere for emphasis). Confidant's color language must do
the opposite: express restraint. A limited, quiet palette signals that
the product isn't competing for attention — it's holding space. Loud,
saturated colors, gradients used for visual excitement, or a large
palette of accent colors are all disqualified on this basis alone, not
because they're unattractive, but because they contradict the emotional
register this product depends on.

### Warmth Comes From Undertone, Not Saturation

"Warm" does not mean orange, or saturated, or bright. It means the
neutral palette (the backgrounds, the surfaces, the vast majority of
what's on screen) should carry a soft, warm undertone rather than a
cold, clinical one — the difference between a room lit by a lamp and a
room lit by an overhead fluorescent light. Most of Confidant's visual
warmth should come from this quiet undertone across large neutral
surfaces, not from bright accent colors used sparingly on top of them.

### Color Signals Meaning Sparingly and Honestly

Where color is used to signal something (an open question, a moment of
reflection, an error), it must do so honestly and rarely — never
borrowing the vocabulary of alerts or warnings for something that isn't
actually urgent (see `emotional-design-v1.md`'s "calm is the absence of
manufactured urgency"). A palette with only a small number of
purposeful, distinguishable meanings will always read as more
trustworthy than one with many decorative variations that dilute what
color is actually communicating.

### Dark and Light Are Both Home, Not Modes to Tolerate

Whichever appearance mode a person is in, the product should feel
equally considered — not a primary light design with a dark mode
retrofitted afterward, or vice versa. Both should independently satisfy
"private, safe, calm, warm" on their own terms, since a person doesn't
choose their preferred appearance based on what the design team found
easier to finish first.

---

## Typography

### One Voice, Not a Performance of Personality

Confidant's typography should read as a single, calm, legible voice
throughout — not a display face for moments the product wants to seem
clever, paired with a "safe" body face for everything else. A typeface
choice that calls attention to itself (unusual letterforms, quirky
display type for headlines) directly contradicts earnestness. The type
choice's job is to disappear into readability, not to be noticed as a
design decision.

### Hierarchy Through Restraint, Not Contrast

Most interfaces build visual hierarchy through aggressive size and
weight contrast — huge bold headlines against tiny thin body text. This
reads as urgency and performance. Confidant's hierarchy should be built
from a narrower, quieter range of sizes and weights, relying more on
spacing and sequence than dramatic scale jumps, so that a screen never
shouts even when it needs to communicate what matters most.

### Long-Form Reading Comfort Is a Priority, Not an Edge Case

Because a person may write, and read back, genuinely long, thoughtful
passages about a difficult situation, typography must be optimized for
sustained reading comfort (generous line height, a measured line
length, legible weight at body size) as a primary use case — not a
secondary consideration behind short chat-bubble snippets, which is
the wrong mental model for this product's actual content (see
`interaction-architecture-v1.md`).

---

## Spacing

### Space Is Where Safety Is Felt

Generous, unhurried whitespace is not a decorative choice — it is one of
the most direct ways an interface communicates "there is no pressure
here, take the room you need." A cramped, dense layout will undercut
calm and safety regardless of what the copy says. Spacing in Confidant
should consistently err toward more room, not less, especially around
the person's own words.

### Rhythm Should Mirror Conversation, Not a Form

Spacing between elements inside a Thread should reflect the natural
pacing of a real exchange — clear separation between distinct turns,
tighter grouping within a single continuous thought — rather than the
uniform grid spacing of a form or a settings page. Different spaces in
the product (a Thread's live exchange vs. Settings' simple list) are
allowed, and expected, to use spacing differently because they serve
different kinds of attention.

### Consistency of Rhythm, Not Identical Values Everywhere

The goal is a spacing system that feels like it has one consistent
underlying rhythm (a shared unit that everything else is a multiple of)
applied contextually — not literally identical gaps used indiscriminately
in every context regardless of whether that context is a dense list or
an open, reflective reading surface.

---

## Design Rationale

### Why Color, Typography, and Spacing Are One Document

Splitting these into three separate documents would suggest they can be
designed independently and reconciled afterward. In practice they are
one continuous decision — a warm neutral background only reads as warm
in combination with a typeface that doesn't fight it and spacing that
gives it room to be felt. Treating them as a single design language,
with each element's rationale checked against the same underlying
emotional claims from `emotional-design-v1.md`, prevents them from being
optimized in isolation and drifting apart.

### Why This Document Refuses to Specify Exact Values

Exact color values, a numeric type scale, and pixel-based spacing units
are implementation decisions, not philosophy — and philosophy needs to
outlive several rounds of exact-value tuning as the product is actually
built and tested with real people. `design-tokens-and-component-
philosophy-v1.md` is where those decisions get made, explicitly bound by
the principles established here, so that a future retuning of an exact
shade or spacing unit doesn't require re-litigating whether warmth
should come from undertone rather than saturation.

---

## Future Considerations

- Once real screens exist, this document should be checked against them
  directly — does the actual palette read as warm-through-undertone, or
  has it drifted toward decoration — the same discipline `engine/
  decisions.md` applies to checking backend implementation against
  written specs.
- If Confidant ever needs a distinct visual treatment for a
  qualitatively different moment (e.g., a serious safety-resource
  disclosure), that should be designed as a deliberate, rare exception
  to this system's restraint principle, not as a precedent that expands
  the everyday palette.
- Accessibility contrast requirements are assumed here but formally
  specified in `accessibility-and-responsive-design-v1.md` — any
  tension between "warm, restrained color" and meeting contrast
  requirements must be resolved in that document's favor, not this
  one's.
