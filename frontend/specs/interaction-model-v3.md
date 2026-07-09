# Confidant Interaction Model v3

Status: **Revises `interaction-model-v2.md`.** v2 correctly established
that thinking, not conversation, is the product — that principle is kept
and elevated, not walked back. What v2 got wrong was turning its
metaphor into mechanics: pages, marginalia, chapters became literal
interaction elements a person would have to learn, rather than a quiet
inspiration behind an interaction that should feel obvious the first
time anyone uses it. This document corrects that specific overcorrection
without abandoning the underlying insight.

This document supersedes v2's notebook mechanics, its "genuine stillness"
treatment of the Considering beat, and its Thread-as-notebook framing. It
keeps and deepens v2's "handing the page over" gesture, and keeps
`frontend-philosophy-v1.md`, `emotional-design-v1.md`, and
`trust-and-privacy-ux-v1.md` untouched, as before. No screens are
designed here — same sequencing discipline as v2.

---

## The Foundational Principle, Unchanged and Elevated

**Thinking is the product. Conversation merely supports it.**

Nothing in this revision touches this. Every correction below exists to
serve this principle more completely — v2's error was assuming a strong
metaphor was the same thing as a strong principle. It isn't. The
metaphor is disposable. The principle is not.

---

## The Metaphor Correction: Borrow, Don't Imitate

v2 asked what interaction model Confidant should have and answered with
a notebook, then built the notebook literally — pages, marginalia,
chapters, an opening ritual modeled on opening a physical cover. The
review's Apple desktop analogy is the exact right correction: the
original Macintosh borrowed *folders* and a *trash can* from the desk
metaphor to make an abstract filesystem legible, but nobody using it
ever thought "I am moving paper across a wooden desk." The metaphor
made the system learnable in one glance and then got out of the way
completely.

**The durable idea underneath the notebook is Shared Thinking, not
notebook-ness.** Shared Thinking survives every future surface this
product might ever take (voice, mobile, multi-person, something not yet
invented); a notebook is just the current, easiest-to-picture expression
of it, useful for design conversations like this one, not for naming
interaction elements.

Concretely, this reverses v2's specific literalism:

- No "pages" as a UI concept. There is a continuous writing and reading
  surface, but it is never called or visually treated as a page someone
  turns.
- No "marginalia" as a placement mechanic. Confidant's responses are
  differentiated from the person's own words by restraint and
  proportion (see `visual-design-system-v1.md`'s typographic voice
  principles) — not by literally living in a margin.
- No "chapters," no "opening a cover." Returning to a Journey (see
  below) should feel familiar and low-friction the way returning to
  anything you were already doing does — not like a ritual with steps
  to learn.

**Journal, not notebook, as the tonal reference** — the review's
distinction is right: notebook implies information kept; journal implies
meaning made. Where a stylistic or tonal decision needs a one-word
anchor (warmth of voice, the reflective register of a section like
"here's what I've understood"), "journal" is the correct word to reach
for. But it remains a tonal anchor for people designing the product, not
a UI concept exposed to the person using it.

---

## Sessions Within Journeys

v1 had "Threads." v2 blurred this into "a notebook kept about a
situation," which was closer but still described a container, not a
relationship to time. The corrected structure, taken directly from the
review:

- A **Journey** is the long-running, evolving body of understanding
  about one situation in a person's life — the thing that genuinely
  deepens over weeks, months, or years. This replaces "Thread" as the
  governing unit.
- A **Session** is one sitting inside a Journey — the thing a person
  actually experiences moment to moment. Sessions begin and end
  constantly; a Journey does not end, it simply continues to be true
  that the person is still working something out.

This distinction matters beyond terminology: it means the interface's
job during any single Session is to feel complete and unhurried on its
own terms, while the Journey's accumulated understanding (not the
Session's) is what should visibly deepen and be referenced. A person
should never feel they're "in conversation #14" — they should feel
they're back in something ongoing, the way returning to a long-running
friendship doesn't reset just because time passed between visits.

---

## Rethinking the Considering Beat: Presence, Not Silence, Not Narration

v2's correction — drop the cycling reasoning-progress phrases — was
right; software narrating its own cognition is still software narrating
its own cognition, however softly worded. But the review is also right
that v2 overcorrected: pure, undifferentiated stillness is exactly what
a frozen or crashed interface also looks like. A real pause from a real
person and a stalled system produce the same visual: nothing changes.
The interaction model needs to make those two things distinguishable
without resorting to text.

**The corrected design: ambient presence, not narration, not silence.**
A single, very subtle, continuous signal — the kind of thing you'd only
consciously notice if you looked for it, but which reads instantly and
unmistakably as "something is here and attending" the moment you do.
Concretely, this should behave like a slow, even breath: a barely
perceptible pulse in something already on screen (weight, opacity, a
soft typographic shift) at a pace closer to a real, unhurried breath
than any UI convention's timing — nothing spinning, nothing counting,
nothing that could be mistaken for a progress indicator. The signal's
entire job is to answer one question the instant it's asked — "is this
still here?" — and nothing more. It should carry no information about
what stage of reasoning is happening, only that reasoning is happening.

This is a real, load-bearing distinction from both v1's cycling phrases
(which said too much) and v2's stillness (which said too little): a
single, continuous, wordless signal, present the entire time, saying
exactly one true thing.

---

## Handing the Page Over: Keep and Deepen

The review singled this out as genuinely original, and it's the clearest
candidate so far for a moment someone would remember. The correction
needed is about accessibility to a first-time user, given the review's
own caution against optimizing for difference: the gesture must be
instantly learnable, not a puzzle to discover.

Concretely, this means the action needs an obvious, visible, ordinary
affordance as its entry point (something as immediately graspable as
any familiar "done, share this" action) — the novelty is in what that
action *means* structurally (a deliberate, separate step from writing
itself, distinct from a chat Send), not in how strange or hidden it is
to find. A person's very first attempt at using Confidant should
succeed without instruction; the meaningful difference this gesture
creates should be felt in the pacing and relationship it establishes
over a Session, not in how clever or unfamiliar the control itself
looks.

This deserves real prototyping attention in the next design pass, as
its own named interaction, not a footnote inside a larger flow.

---

## Making the Architecture Felt

The review's strongest new idea: the backend's real cognitive work
(building understanding, tracking what's still uncertain, noticing when
something resolves) should be *experienced*, not reported — through
specific, recognizable moments, never a dashboard. Four candidate
moments, each checked here against what the backend can actually support
today, because a moment Confidant can't honestly back up is worse than
not having it:

- **"Here's what I've understood."** Fully real today — this is a
  direct, honest expression of WorldState and Judgment's assessment
  (see `engine/specs/WorldState-spec-v1.md`,
  `engine/specs/judgment-specification-v2.md`), already the subject of
  `memory-and-shared-understanding-v1.md`. This is the anchor moment
  and should remain the most structurally prominent thing in the
  product, exactly as the review asks.
- **"Something has become clearer."** Also real today, buildable from
  comparing a Journey's understanding across Sessions — a previously
  open unknown that's resolved, or confidence that's genuinely risen,
  are both things the backend's own state already contains turn to
  turn. This is a strong, honest candidate for a memorable, recurring
  beat.
- **"I'm still uncertain about one important piece."** Real today —
  a direct, honest surface of Judgment's own open unknowns and
  confidence, already core to this product's epistemic honesty
  commitments (see `trust-and-privacy-ux-v1.md`).
- **"I've noticed a pattern across our conversations."** This one needs
  an honest caveat: as stated, a pattern *across* Sessions or Journeys
  is exactly the backend's Learning process — and Learning is a
  deliberately unimplemented reserved slot today (see
  `engine/specs/system-architecture-v2-specification.md` and
  `engine/decisions.md`'s standing decision not to build pattern
  detection before real accumulated history exists to learn from).
  Committing to this moment now would be designing a promise the
  product can't yet keep — precisely the mistake this whole project has
  corrected for repeatedly elsewhere. The honest version available
  today is narrower: **"I've noticed a pattern within this Journey"** —
  a recurring theme surfacing across Sessions inside one ongoing
  situation, which only requires the understanding already accumulated
  in that Journey, not cross-Journey Learning. The cross-Journey
  version the review is really reaching for is a real, exciting future
  moment — it belongs in Future Considerations below, explicitly gated
  on Learning actually being built, not designed into v1 as if it
  already works.

---

## The Guardrail: Familiar Where It Should Be, Different Only Where It Earns It

The review's caution is now a standing principle for every future
design pass: the goal is never to look unlike existing AI products for
its own sake. A person should be able to begin using Confidant with zero
instruction — a plain, obvious writing surface, an ordinary way to
indicate they're done for now. The product's real novelty should live
in a small number of deliberately-designed moments (the handing-over
gesture, the ambient Considering presence, the architecture-felt
moments above) — not spread thin across unfamiliar controls everywhere,
which is what actually produces friction, not distinction.

---

## Candidate Moments Someone Would Remember Years Later

Answering the review's actual charge directly, as the target for the
next design pass to build toward:

1. **Handing the page over** — the felt shift from writing to being
   heard, as its own deliberate act.
2. **"Something has become clearer"** — the moment a specific,
   previously-open uncertainty visibly resolves, named plainly rather
   than folded anonymously into a bigger update.
3. **Returning to a Journey after real time away** and finding the
   understanding at the top already reflects everything that's
   happened — without having to re-read or re-explain anything.

These three are proposed as the flagship moments to prototype next,
specifically because all three are honestly buildable against today's
actual backend, not aspirational promises the architecture can't yet
keep.

---

## Future Considerations

- **Cross-Journey pattern-noticing** ("I've noticed this across
  several situations you've brought to me") is a genuinely compelling
  future moment, explicitly deferred until the backend's Learning
  process is deliberately built out from real accumulated history — see
  `engine/specs/system-architecture-v2-specification.md`'s Learning
  section and its current reserved-slot status. Designing for it now
  would be designing ahead of evidence, the exact discipline this
  project has held everywhere else.
- The exact visual/motion treatment of the ambient Considering presence
  needs real prototyping and testing against real reasoning latencies —
  this document commits to its behavior and intent, not its final
  execution.
- The handing-over gesture's concrete form (what the "obvious,
  ordinary affordance" actually is) is intentionally left open for the
  next design pass, per the review's request to prototype it carefully
  rather than settle it here in prose.
