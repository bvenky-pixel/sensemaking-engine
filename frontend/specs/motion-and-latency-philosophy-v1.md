# Confidant Motion & Latency Philosophy v1

Status: Depends on `frontend-philosophy-v1.md`, `emotional-design-v1.md`,
and `visual-design-system-v1.md`. This document exists because Confidant
has a problem most interfaces don't: the backend genuinely takes real,
multi-second time to reason across several sequential stages (see
`interaction-architecture-v1.md`'s "Considering" state), and how that
time is experienced is one of the highest-leverage design decisions in
the entire product.

---

## Purpose

Every other AI product treats latency as a problem to be minimized or
hidden — a spinner, a skeleton screen, an "AI is typing" indicator
borrowed wholesale from chat products optimized for speed. Confidant
cannot borrow that playbook, because its actual latency is not a
technical inconvenience to apologize for; it is a direct, honest
byproduct of doing real, multi-stage reasoning before responding (see
`engine/specs/system-architecture-v2-specification.md`). This document
exists to design that waiting time as something coherent with the
product's values, and to define what motion is and isn't allowed to do
anywhere else in the product.

## Scope

This document covers: the philosophy of how waiting should feel, what
motion is permitted to communicate throughout the product, and the
boundary between motion that supports the experience and motion that
performs liveliness for its own sake. It does not specify exact
animation curves, durations in milliseconds, or easing functions — those
are `design-tokens-and-component-philosophy-v1.md`'s job, once this
document's philosophy is settled.

---

## Guiding Principles

### 1. Waiting Should Read as Care, Not Delay

The core reframe this document depends on: the interval between a
person sharing something and Confidant responding is not dead time to
be filled or disguised — it is the visible shape of consideration
happening. The design goal is for a person to feel, without being told,
that something real is happening during that interval — not "the app is
loading," but closer to "it's thinking about what I just said." This
does not mean manufacturing a false sense of effort where none exists;
it means not hiding or apologizing for real effort that does.

### 2. Motion Must Never Imply Urgency

No animation anywhere in the product should communicate speed, urgency,
or excitement — no fast, snappy micro-interactions borrowed from
consumer apps designed to feel responsive and energetic. Every motion
in Confidant should move at a pace consistent with a calm, unhurried
conversation: neither so slow it frustrates, nor so fast it feels like
the interface is rushing the person along (see `emotional-design-v1.md`'s
"calm is the absence of manufactured urgency" — this principle is that
document's direct consequence for motion specifically).

### 3. Motion Explains, It Doesn't Decorate

Every animation in the product must exist to help someone understand
what just happened or what's about to happen (a new piece of
understanding appearing, a Thread transitioning between states) — never
purely to make the interface feel more alive, modern, or polished.
Motion used as embellishment (bouncy entrances, playful transitions,
animated illustrations) fails the earnestness principle directly (see
`frontend-philosophy-v1.md`) — it signals "look how delightful this is"
rather than "here is what's actually happening."

### 4. The "Considering" State Must Be Distinct From Generic Loading

A generic spinner or progress bar communicates "the system is busy" —
an operational, mechanical message. Confidant's waiting state must
instead communicate something closer to unhurried attention: still,
quiet, without the anxious connotations a spinning indicator or ticking
progress bar carries. It should never imply a countable, measurable
task with a completion percentage, because the backend's actual
reasoning process doesn't have one, and implying otherwise would be
dishonest about what's actually happening (see
`trust-and-privacy-ux-v1.md`'s standing commitment against surprising or
hidden processing).

### 5. Nothing Should Move Without a Reason a Person Would Recognize

Before any motion is added anywhere in the product, it must be possible
to state, in plain language, what it's helping the person understand.
"It looks nice" or "it adds polish" are not valid justifications on
their own — every motion decision must trace to a specific
comprehension or emotional goal already established in
`emotional-design-v1.md` or `interaction-architecture-v1.md`.

---

## Design Rationale

### Why Latency Gets Its Own Document Instead of a Section in Motion

It would be tempting to treat "how long things take" as purely a
technical/performance concern, addressed later in `frontend-engineering-
architecture-v1.md`'s performance strategy. But Confidant's latency is
not primarily a performance problem to be optimized away — it is a
structural, permanent feature of doing real sequential reasoning, and
the correct response is largely a design response (how does waiting
feel), not only an engineering one (how do we make it faster). Pairing
latency with motion in one document keeps the *design* answer to
latency from being crowded out by a purely technical framing of "reduce
the number of seconds."

### Why This Document Refuses to Prescribe a Specific "Thinking" Animation

Naming a specific visual treatment (a pulsing dot, a breathing shape, a
progressive reveal of words) here would lock in a solution before the
principles that solution needs to satisfy have been agreed. This
document's job is to make the bar any proposed treatment must clear
explicit — reads as attention, not urgency; explains rather than
decorates; never implies a false completion percentage — so that
whichever concrete treatment is eventually chosen can be evaluated
against a real standard rather than aesthetic preference alone.

### Why Fast Isn't Automatically Better Here

In most software, reducing latency is an unqualified good. Confidant's
situation is more specific: reducing latency is good only insofar as it
doesn't come at the cost of the actual reasoning quality the backend's
multi-stage architecture exists to produce (see `engine/specs/system-
architecture-v2-specification.md`'s deliberate multi-stage design).
This document takes the position that the frontend's job is to make
the actual time honestly bearable and well-explained, not to create
pressure toward speeding up the reasoning itself for the sake of a
snappier-feeling interface.

---

## Future Considerations

- Real usage will surface whether people's tolerance for the
  "Considering" state holds up in practice, especially on longer or more
  complex Threads — this should be revisited with real timing and
  real reactions once available, the same way Judgment v2's calibration
  was only revisited once real evaluation data existed.
- If a future architectural change (e.g., streaming partial output from
  a stage as it becomes available) becomes possible on the backend, this
  document will need a direct amendment — today it assumes a turn
  either hasn't started responding or has fully finished, with nothing
  meaningful in between to show progressively.
- This document doesn't address motion for celebratory or milestone
  moments (e.g., acknowledging a decision the person has reached) — if
  such moments are ever designed, they should be treated as a deliberate,
  rare exception requiring its own justification against these
  principles, not as a precedent that loosens the restraint described
  here.
