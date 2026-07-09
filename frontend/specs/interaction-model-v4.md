# Confidant Interaction Model v4 (Final)

> **Thinking is the product. Conversation merely supports it.**

If a person remembers exactly one sentence about how Confidant works,
it should be this one. It is the frontend's equivalent of the backend's
own governing discipline — the same weight `engine/decisions.md`'s
Constitution of Confidant's Thinking Method carries for the Sensemaking
Engine, now held on the frontend side. Every section below exists to
derive from it, not to stand beside it.

---

Status: **This is the definitive Interaction Model for Confidant v1.**
It supersedes `interaction-model-v2.md` and `interaction-model-v3.md`
(kept in git history as the visible reasoning trail, not deleted) and
formally retires `interaction-architecture-v1.md` and
`memory-and-shared-understanding-v1.md`, whose responsibilities now live
here in full. `information-architecture-v1.md`,
`frontend-engineering-architecture-v1.md`,
`accessibility-and-responsive-design-v1.md`,
`visual-design-system-v1.md`,
`developer-tooling-and-testing-strategy-v1.md`, and
`motion-and-latency-philosophy-v1.md` have each had their
"Thread" terminology updated to "Journey" to match this document; their
principles were already sound and needed no other change.
`information-architecture-v1.md` additionally had its former "Core Unit:
The Thread" definition removed, since that concept is now defined here
instead. `product-experience-v1.md` is separately marked superseded in
part, pending a visual redesign against this document.
`frontend-philosophy-v1.md`, `emotional-design-v1.md`, and
`trust-and-privacy-ux-v1.md` remain untouched, as at every prior
revision — this document exists to honor their principles more
completely, never to replace them. No screens are designed here.

---

## Shared Thinking: Bigger Than the Frontend

Shared Thinking is no longer just this document's organizing metaphor —
it is one of Confidant's intellectual foundations, alongside the
backend's own commitment to understanding before reasoning. Every
interaction in this model is required to trace back to it directly, not
merely to "supporting a good conversation." Where those two things ever
conflict, **Shared Thinking wins.** A more convenient conversational
pattern that weakens shared thinking is the wrong choice, every time.

The earlier notebook language was the right instinct pointed at the
wrong altitude — useful for explaining the model to designers, wrong as
something a person would ever consciously notice while using the
product. The correction follows the same discipline the original
Macintosh applied to its own desk metaphor: borrow structure, never
require the person to think in the metaphor's terms. Confidant should
never make someone think "I am using a notebook." It should make them
think nothing about the interface at all — only about what they're
working out.

---

## Sessions Within an Evolving Journey

A **Journey** is not a container that holds Sessions. It is an evolving
shared understanding of one meaningful part of a person's life — a
relationship that continues, not an archive that gets reopened.
Returning to a Journey after time away should feel like picking up an
ongoing relationship, not retrieving a saved file. That distinction is
not a mood to aim for; it is the concrete test any design decision
touching Journeys must pass.

A **Session** is one sitting inside that ongoing relationship. Sessions
begin and end constantly and are allowed to feel complete on their own
terms; the Journey itself never ends just because a Session did.

---

## Ambient Presence, Not Narration, Not Silence

The system should feel **present**. Never busy. Never processing. Never
performing. Just attentively present — the whole distinction the
Considering beat exists to carry.

A single, continuous, wordless signal — paced like a slow, unhurried
breath — answers the one question that matters the instant it's asked:
*is this still here?* It carries no report of what stage of reasoning
is happening, because a person who is genuinely present with you never
narrates their own listening. It is also never pure, undifferentiated
stillness, because a real pause and a frozen application look identical
without some continuous, living signal to tell them apart.

---

## Handing the Page Over

Writing and indicating readiness to be heard are two separate,
deliberately distinct actions — not one action that does both at once,
the way a chat Send button does. This is the model's most original
interaction and the one most worth protecting: the entry point into it
must be immediately obvious to a first-time person, exactly as familiar
as any ordinary "I'm done, hear this" action. The novelty belongs
entirely to what the gesture *means* — a real, felt transition from
thinking to being heard — never to how unusual or hard to find it is.

---

## Letting the Architecture Be Felt, as Human Understanding

The backend continuously builds understanding, tracks what's still
uncertain, and occasionally notices something new. None of that should
ever read as a system reporting its own behavior — only as a person's
own clarity growing. Five moments carry this, each checked against what
the backend can actually support today, because a moment the product
can't honestly back up is worse than not having it at all:

- **Growing understanding** — "here's what I've understood" — a
  faithful expression of what WorldState and Judgment already hold,
  real today, and the single most structurally important moment in the
  product.
- **Deepening clarity** — "something has become clearer" — a
  previously open question resolving, or genuine confidence rising,
  drawn honestly from how a Journey's own understanding changes between
  Sessions.
- **Named uncertainty** — "I'm still uncertain about one important
  piece" — a direct, honest surface of what the backend's own
  assessment hasn't yet resolved.
- **Quiet discovery** — a gentle noticing of something the person said
  but hadn't yet put together themselves — a recurring thread across
  Sessions within one Journey, surfaced as reflection revealing
  something, never as the system announcing a finding. The felt
  difference matters entirely: *"I hadn't seen it that way before,"*
  never *"the AI found something."* Buildable honestly today from one
  Journey's own accumulated understanding — no cross-Journey memory
  required.
- **Something noticed across Journeys** — the version of quiet
  discovery that spans separate situations in someone's life, not just
  one — genuinely compelling, and explicitly not yet honest to build:
  it depends on the backend's Learning process, a deliberately
  unimplemented reserved slot today (see `engine/specs/system-
  architecture-v2-specification.md`). It belongs in Future
  Considerations, not in this product, until that changes.

---

## The Language of Confidant

Vocabulary is part of the interaction model, not an afterthought for
copywriting. The product never speaks in its own technical terms —
*processing, generating, loading, memory updated, context, inference,
reasoning complete* — because every one of those describes a system to
itself. It speaks instead in the register of a person's own thinking:
*understanding, considering, reflecting, clarifying, remembering,
revisiting, becoming clearer, exploring.* The exact words matter less
than never mixing the two registers — one coherent language, everywhere,
is what makes the vocabulary invisible.

---

## Two Permanent Guardrails

**Novelty is not the goal. Clarity is.** Confidant should never be
unusual to distinguish itself from other AI products. Every unfamiliar
interaction has to earn its place by making the thinking experience
better — a person should always know exactly how to begin, with zero
instruction. Where this document introduces something genuinely new
(the handing-over gesture, ambient presence), it does so because Shared
Thinking required it, never because familiarity felt insufficiently
distinctive.

**The Ten-Year Test.** For any interaction this document commits to,
ask: would it still feel correct if Confidant existed ten years from
now — through voice, through multimodal interfaces, through models that
don't exist yet? If an idea only holds because of what's technically
convenient today, it's too implementation-specific for this document
and belongs one level down, in a future engineering document instead.
Apply this test to anything proposed for addition here, going forward,
the same way the backend's own Governing Test decides whether a new
System Architecture process is justified.

---

## Candidate Moments Someone Would Remember Years Later

1. **Handing the page over** — the felt shift from writing to being
   heard.
2. **Deepening clarity** — a specific, named uncertainty visibly
   resolving.
3. **Quiet discovery** — recognizing something about your own situation
   you hadn't put together yourself.
4. **Returning to a Journey** after real time away and finding the
   relationship simply continues, already caught up.

All four are proposed as the flagship moments for the next design pass
specifically because each is honestly buildable against today's real
architecture.

---

## Future Considerations

- **Cross-Journey quiet discovery** ("something noticed across
  separate situations you've brought to me") stays explicitly deferred
  until Learning is deliberately built from real accumulated history —
  designing for it now would be designing ahead of evidence, the
  discipline this project has held everywhere else.
- The exact form of the handing-over gesture and the ambient presence
  signal are intentionally left to the next, concrete design pass — this
  document commits to their intent and behavior, not their final
  execution.
- Voice and multimodal surfaces are not designed here, but every
  principle above was checked against the Ten-Year Test specifically so
  it would still apply when those surfaces arrive.
