# Confidant Interaction Model v2

Status: **First-principles rethink, prompted by design review.** The v1
prototype (`frontend/prototype/confidant.html`) and its accompanying
`product-experience-v1.md` were reviewed and correctly identified as
"an excellent AI chat application" — quiet, well-typeset, free of
gimmicks, but still structurally a chat product: message, wait,
response, message, wait, response. Removing bubbles and adding a serif
typeface changed the costume, not the interaction.

This document supersedes the interaction model in
`interaction-architecture-v1.md`, the "Thread" container concept in
`information-architecture-v1.md`, the panel treatment of shared
understanding in `memory-and-shared-understanding-v1.md`, and the
cycling-phrase waiting device in `motion-and-latency-philosophy-v1.md`.
It does not touch `frontend-philosophy-v1.md`, `emotional-design-v1.md`,
or `trust-and-privacy-ux-v1.md` — those documents' principles (safety,
simplicity, earnestness, honesty over certainty, the user owns the
conclusions) are exactly right and are what this rethink is trying to
honor more completely, not replace. No screens are designed here, per
explicit instruction: this document commits only to the interaction
model. Visual design resumes only after this is agreed.

---

## The Reframe

The v1 documents were built on a claim that felt obviously true and
turns out to be the whole problem: *conversation is the product.*
Everything else — no bubbles, no sidebar, generous whitespace — was
decoration applied on top of that claim. But if conversation is the
product, the interaction is inescapably a dialogue between two parties
taking turns, and a dialogue between two parties taking turns is a
chat, no matter what it's wearing.

The corrected claim: **thinking is the product. Conversation merely
supports it.** A person doesn't come to Confidant to talk to something.
They come to think something through, and talking happens to be how
humans do that — sometimes out loud to another person, sometimes on a
page, sometimes both at once. Confidant's job is to be the page and the
person at the same time, without ever making either of those roles feel
like "a system responding to input."

Every decision below is a consequence of that one correction.

---

## The Governing Metaphor: A Shared Notebook

Of the reference experiences named in the review — a library, a study,
a meditation room, a therapist's office, a long walk, a private
notebook — one was chosen to actually govern structural decisions,
rather than leaving all of them as equally-valid mood references that
would pull the design in different directions at once. Coherence
requires committing to one.

**Confidant is a notebook a person keeps about one situation in their
life — one they happen to share with someone who sometimes writes back
in the margin.**

This was chosen over the others for specific, structural reasons, not
just atmosphere:

- A notebook has no turn-taking convention built into its physical
  form. You can write half a page or ten before anyone responds to
  anything. A therapist's office or a walk both *imply* spoken
  back-and-forth, which quietly re-imports dialogue-as-the-unit even
  when you try to slow it down.
- A notebook supports **marginalia** — a response that sits alongside
  what prompted it, at whatever length it actually deserves, rather
  than a same-sized reply matched to a same-sized message. This is the
  single structural feature that makes "conversation merely supports
  thinking" concrete instead of aspirational.
- A notebook has a real, physical **ritual of opening and closing** —
  which gives the product an actual arrival and departure moment to
  design, rather than a screen that's simply "loaded."
- A notebook is the one metaphor on the list that makes the five-year
  loss genuinely concrete. Losing a library card is an inconvenience.
  Losing a notebook you've kept for five years with someone who wrote
  back in it is a real, specific grief — which is exactly the weight
  the review asked this product to earn.

The other reference experiences (a quiet study, a walk, a therapist's
listening) remain real and useful — but as *texture* for how the
notebook metaphor should feel (unhurried, private, taken seriously),
not as competing structures for how it should work.

---

## The Emotional Journey

Not screens — the sequence of feeling a person should move through,
which the interface's job is to make true.

1. **Arrival.** Before anything else, a brief, consistent threshold —
   the felt equivalent of sitting down and opening the cover. Not a
   loading state to get through, a deliberate pause that signals: the
   outside world's pace doesn't apply in here anymore. This moment is
   identical every time, on purpose — familiarity is part of what makes
   a threshold feel safe rather than like friction.
2. **Settling.** The person begins writing. Nothing in the interface is
   waiting on them, timing them, or visibly anticipating a reply. There
   is no sent/delivered/read status to notice, because none of that
   exists in a notebook. They can write one line or two pages.
3. **The pause that means something.** At some point, the person
   reaches a natural stopping point — not because a message was "sent,"
   but because they've said what they were sitting down to say for now.
   This is a real, felt moment, and the interaction model must give it
   a real, deliberate gesture (see Pacing, below) rather than
   auto-triggering a reply the instant text stops appearing.
4. **Being heard.** Confidant reads. This is silence, not narration
   (see The Considering Beat, below) — the felt experience of someone
   who has actually stopped to take in what you wrote, not a system
   executing steps.
5. **The mark in the margin.** A response arrives, sized to what it
   actually is — sometimes a single line, sometimes a real paragraph,
   occasionally just a question with nothing else attached. It appears
   beside or beneath what prompted it, part of the same continuous
   page, never as a new bubble in a new row.
6. **Continuing, or not.** The person may write again immediately, sit
   with what was said, or simply close the notebook. All three are
   complete, ordinary endings — there is no unanswered-message feeling,
   because nothing was ever "sent" awaiting a "reply" in the first
   place.
7. **Returning.** Days, weeks, or months later, opening back to this
   notebook feels like opening back to a page you were in the middle
   of — not resuming a chat thread, not being shown a changelog. What's
   understood so far is already sitting at the top of the page, quietly
   updated, the way a good notebook's running preface would be.

---

## Pacing: No Forced Alternation

The chat convention — one message, one reply, repeat — is replaced with
a **user-paced writing surface** with an explicit, deliberate signal for
"I'm ready to hear something back," distinct from the act of writing
itself. Concretely: writing and "handing the page over" are two
different, separately-felt actions, not one action (pressing Send) that
does both at once. This single change is what dissolves the chat
rhythm — a person is never implicitly being timed between keystrokes and
a reply, because the interface never assumes a reply is due just because
text stopped appearing.

Confidant's own contribution, once it comes, is never a same-length
answer to match the same-length question. Some of what a real listener
offers is a single sentence. Some of it is a longer passage. The
variability itself is part of what signals "a person actually
responding to what's in front of them," not "a system producing a
standard-shaped reply."

---

## The Considering Beat: Silence, Not Narration

The v1 prototype's waiting state cycled through phrases like
"Understanding your situation… Looking for what matters… Preparing a
response…" It was designed to avoid a generic spinner — and it did —
but on reflection it is still a system narrating its own internal
process to you, just in softer language. No person who is actually
listening carefully narrates their own listening. A trusted listener,
a therapist, a mentor on a walk: they simply go quiet for a moment,
then speak. The quiet itself is the signal.

**The corrected design: the Considering beat is stillness, not text.**
Nothing announces that thinking is happening — the absence of a reply,
held for a real, honest duration, is the entire experience. If anything
marks the moment at all, it should be barely perceptible — the way a
room feels different when someone nearby has gone quiet to actually
think about what you just said, rather than a labelled loading state
of any kind, however gently worded.

This is a direct, structural correction, not a smaller version of the
old idea: the old device explained cognition; the new one simply
withholds text and lets the withholding carry meaning, exactly the way
a real pause does.

---

## Answering the Review's Specific Questions

**Do messages need to look like chat bubbles?** No — and more than
that, they should not be discrete "messages" at all. The page is
continuous prose. What a person writes and what Confidant writes back
both live on the same page, differentiated only the way marginalia is
differentiated from a main entry — not as rows in a list.

**Does there need to be a traditional message list?** No. There is a
page — one continuous, scrollable document per situation — not a list
of exchanged items. Scrolling up doesn't page through "messages," it
turns back through what's already been written, the way flipping back
through a real notebook works.

**Should responses appear differently?** Yes — as marginalia, set
apart typographically (not in a colored container) from the person's
own writing, and variable in length rather than uniformly reply-shaped.

**Can reflection become more visually important than dialogue?** Yes,
and it should be structural, not a panel someone opens. What Confidant
currently understands lives as the notebook's own running preface —
present at the top of the page by default, the first thing visible
on arrival, quietly rewritten as understanding deepens. It is not a
feature alongside the conversation; per the review, it is the defining
interaction, so it gets the page's most prominent position, not a fold
control.

**Can the interface encourage longer thoughts rather than short
exchanges?** Yes — by removing the mechanism that currently discourages
them. A small chat input box with a Send button in easy reach invites
short, frequent exchanges by its very shape. A proper, generous writing
surface with no visible pressure to finish and hand off invites the
opposite. The interaction model's refusal to auto-reply on every pause
is itself the strongest lever here: nothing is lost by writing at
length, because nothing is waiting on a shorter turn.

---

## The Long-Term Relationship

There is no "conversation history" in this model — there are chapters
of one ongoing notebook kept about a given situation, accumulating over
months or years, never flattened into a log to be searched or scrolled
through as data. The running preface at the top is the felt sense of
"how far we've come," not an analytics summary; the pages beneath it
are the actual record, always reachable, never the primary way the
relationship is experienced day to day.

This is what makes the five-year loss scenario land the way the review
wants it to: what would be lost is not a chat history export. It's a
notebook, written over years, with someone else's handwriting in the
margins of your own thinking. Every decision in this document is in
service of that being the true, honest description of what's actually
being built — not a metaphor applied after the fact to dress up a chat
log.

---

## What This Document Does Not Decide

Deliberately, per the review's own sequencing instruction: no colors,
no typefaces, no exact spacing, no literal screens. Those come next,
and only once this interaction model itself is agreed — the same
discipline `visual-design-system-v1.md` and the rest of the v1 visual
set already followed relative to their own principles, now applied one
level upstream, to the interaction model those documents will need to
be re-derived from.

## Open Questions for the Next Pass

- The exact form of the "I'm ready to hear something back" gesture
  (separate from writing itself) needs a concrete design once visual
  work resumes — this document commits to it existing and being
  distinct from Send, not to its exact shape.
- How marginalia should behave on a narrow (mobile) page, where true
  margins don't physically exist, is an open problem this document
  doesn't resolve — likely marginalia becomes interleaved rather than
  beside, but that needs real design attention, not an assumption.
- How long a "Considering" silence should honestly last, and whether
  it should ever be interrupted by the person deciding to keep writing
  instead of waiting, is a real interaction question for the next pass.
