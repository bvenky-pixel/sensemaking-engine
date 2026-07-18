# Confidant Product Experience v1

**Status: SUPERSEDED IN PART, pending a new visual pass.** This
document and its live prototype (`frontend/prototype/confidant.html`)
realized the pre-review interaction model — chat turns inside a
"Thread," a foldable Shared Understanding panel, cycling reasoning-
progress text during the wait. Design review correctly identified that
model as still an AI chat application, and `interaction-model-v4.md`
now supersedes it (Journeys/Sessions, ambient presence, "handing the
page over," understanding as an ever-present moment rather than a
panel). The concrete color/type/spacing values below and the general
visual-restraint principles they encode are not invalidated by that
review and remain the working visual language — only the screens
themselves, built against the old interaction model, need to be
redrawn against `interaction-model-v4.md` before this document can be
current again. That redesign has not been done yet; do not treat the
live prototype as accurate until it is.

**Further update (2026-07-18): the token table below is ALSO now
superseded**, on top of the screens. The founder directed a full visual-
language pivot ("dull and boring... more dynamic and modern yet
calming, think headspace") — see `frontend/decisions.md` "Warm & Alive
redesign" for the complete list of which specific restraint principles
below were deliberately overridden (accent-color restriction, radius
restriction, motion restriction, serif typography) versus which were
kept (no chat bubbles, no dashboard chrome, dark mode as its own
world). The actual current tokens live in
`frontend/app/src/lib/tokens.css`, not in this document — treat every
concrete value below as historical record of what v1 chose, not as
current truth.

---

Original status (concrete values below still apply): The concrete
realization of `visual-design-system-v1.md`,
`motion-and-latency-philosophy-v1.md`,
`design-tokens-and-component-philosophy-v1.md`, and
`accessibility-and-responsive-design-v1.md` — those documents
deliberately withheld exact values so that philosophy could be agreed
before implementation was decided. This document is where that
deferral resolves: real hex values, a real type scale, and a real,
high-fidelity reference implementation.

**Live reference**: every screen described below exists as a working,
themeable HTML/CSS prototype — Welcome, Home, Conversation, Thoughtful
Waiting, Shared Understanding, Returning After a Week, Mobile, and a
Foundations page showing the raw design tokens. Treat it as the visual
source of truth this document explains, not a separate deliverable.

---

## Purpose

Twelve prior documents established what Confidant must be and feel
like, in principle. None of them committed to a single hex value, a
single typeface, or a single pixel of spacing — that restraint was
deliberate, so the philosophy could be argued about and agreed
independently of any one visual execution. This document is the
opposite kind of artifact: it makes every one of those calls, concretely,
and explains why each specific choice is the correct realization of the
philosophy that precedes it — not a generic "premium AI product" default.

## Scope

This document covers: the concrete visual language (color, type, space,
motion, elevation, radius, iconography, illustration, dark mode,
accessibility), the interaction philosophy behind each signature moment
in the product, and the end-to-end screen flow a person moves through
from first launch to long-term use. It does not repeat the reasoning
already established in the twelve documents it depends on — it cites
them and moves directly to the concrete decision.

---

## Visual Language

### Color

Two roles only: a warm neutral ground, and one considered accent — not
a palette of many colors doing many jobs.

| Token | Light | Dark | Role |
|---|---|---|---|
| `paper` | `#E9E3D8` | `#1E1A16` | The ground everything sits on — warm stone/linen in light, a quiet room at dusk in dark. Neither is a pure neutral; both carry the same warm undertone described in `visual-design-system-v1.md`. |
| `paper-raised` | `#DFD8C8` | `#27221C` | The one surface allowed to sit slightly apart from the ground — used only for the Shared Understanding panel. |
| `ink` | `#2A2620` | `#ECE5D6` | Primary text. Warm near-black / warm off-white — never pure black or pure white, evoking dried ink on paper rather than a screen. |
| `ink-muted` | `#6E6656` | `#A89E89` | Secondary text: glimpses, subheads, the composer's placeholder voice. |
| `accent` | `#3D4B64` | `#93A3BE` | The single considered color in the entire product — a deep, muted slate-ink blue, like fountain-pen ink or dusk. Used only for the thread of reasoning itself: focus states, correction affordances, the marks inside "here's what I've understood." Never used decoratively. |
| `line` | `#D2C9B6` | `#362F26` | Hairline dividers between turns and sections — never a heavy rule. |

Deliberately avoided: a bright, saturated accent used for calls-to-action
(nothing in this product is a call to action in the growth-product
sense); a second or third accent color for "variety"; pure black or
pure white as either theme's ground.

### Typography

One serif carries every word a person actually reads or writes — the
user's own words, Confidant's words, the Shared Understanding
reflections, headlines. A separate, unbranded system font carries
interface chrome only (labels, timestamps, section headers of the UI
itself, never content).

- **Reading/content face**: Charter — a warm, literary serif built for
  screen reading comfort, not a display face borrowed for decoration.
  Regular weight for body and headlines; italic used specifically to
  signal *voice* (Confidant's own reading of a situation, a section
  introducing a synthesis) rather than emphasis.
- **Interface face**: the viewer's native system font
  (`-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto`) — used at
  small sizes, generous letter-spacing, always in the muted ink color,
  never competing with the reading face for attention.

| Role | Face | Size / Line-height | Where |
|---|---|---|---|
| Display | Charter, 500 | 32px / 1.3 | The Welcome headline only — the single largest moment of type in the whole product. |
| Section voice | Charter, italic | 19px / 1.4 | "Here's what I've understood," a Thread's title — moments where Confidant's own voice or framing is present. |
| Body | Charter, 400 | 17px / 1.68 | Every turn, every reflection — optimized for sustained reading, not chat-bubble brevity. |
| UI label | system-ui | 12px / 1.4, +0.04em tracking, uppercase | "Still open," "In play," timestamps, section eyebrows. |

Line length is held to roughly 55–60 characters for body text (turns and
reflections both), consistent with `visual-design-system-v1.md`'s
long-form reading priority, even though most individual turns are
shorter than that in practice.

### Spacing

A single underlying rhythm (roughly 8/16/24/34/48px), applied
contextually rather than as one uniform grid: tight grouping within a
single thought, generous separation between distinct turns (34–48px),
and the most generous space of all reserved for the Welcome and
Returning screens, where a person is meant to arrive slowly rather than
land in the middle of density.

### Motion

One duration, one easing curve, used everywhere motion appears: 260ms,
`ease-out`. There is no second, faster "micro-interaction" timing —
consistency of pace is itself part of what reads as unhurried.

The one animated moment with real duration is Thoughtful Waiting's
cycling phrase (see below), which moves far slower than any UI
transition — roughly 2.4 seconds per phrase — because it represents
genuine elapsed reasoning time, not a UI acknowledgment. All motion
respects `prefers-reduced-motion`: the cycling phrase becomes a single
static line, and the breathing indicator becomes a fixed, dim dot.

### Elevation & Corner Radius

Confidant is flat by default — pages, not floating cards. Elevation
(a barely-there 1px hairline shadow) is used exactly once, on the
Shared Understanding panel, to mark it as something a person can pick
up and inspect, distinct from the ambient page beneath it. Corner
radius is a single, nearly imperceptible 3px, applied only to that same
panel and to focus rings — never a "rounded-everything" signature
applied indiscriminately to buttons, fields, and containers.

### Iconography & Illustration

Almost none. The two icons that exist in the entire product (a small
arrow on "Begin"/"Continue," a plus mark on "start something new") are
simple, hand-drawn-feeling line strokes, not a borrowed icon set — every
other affordance is a text label. There is no illustration style,
mascot, or empty-state graphic anywhere: an empty Home is a single
quiet sentence and generous whitespace, never a friendly drawing filling
the gap. A barely-perceptible paper-grain texture (roughly 2% opacity)
sits under the entire interface as the one textural signature the
product allows itself — a quiet nod to "a beautiful notebook" that
never rises to the level of decoration.

### Dark Mode

Dark mode is not light mode inverted — it's designed as its own
complete, considered world ("a quiet room at dusk," not "the same room
with the lights off"). Both themes independently satisfy every
principle in `visual-design-system-v1.md`; the accent shifts from a
deep ink-blue on paper to a lightened, softened version of the same
hue on dark ground, preserving the same emotional identity rather than
simply raising contrast.

### Accessibility

Every principle in `accessibility-and-responsive-design-v1.md` is
satisfied structurally here, not layered on after: focus states are
visible and consistent; reduced motion removes the cycling animation's
motion while preserving its informational content (the phrase itself);
color is never the only carrier of meaning (the "?" and "·" marks in
Shared Understanding, not just an accent-colored dot, distinguish open
questions from decisions in play).

---

## Interaction Philosophy

### Welcome: the Invitation Is the Composer, Not a Button Beside It

There is no "Get Started" button separate from where a person actually
begins. The text field a person will use to think out loud *is* the
welcome screen's primary object — because the moment of arriving and
the moment of beginning to think should be the same moment, not two
sequential steps separated by a decorative landing page.

### Conversation: No Bubbles

Turns are not contained in colored bubbles. They sit directly on the
page, distinguished only by a small quiet label ("You" / "Confidant"),
alignment, and the rhythm of spacing between them — closer to how
dialogue reads in a well-set book than how messages read in a chat app.
This is a direct, load-bearing consequence of `interaction-architecture-
v1.md`'s rejection of the standard chat interface: bubbles imply
back-and-forth speed and symmetry between two equally-weighted
parties; Confidant's actual relationship to the person is neither
symmetric nor fast, and the visual form should not pretend otherwise.

### Clarifying vs. Reflecting: Italic as Voice, Not Decoration

A clarifying turn is set in italic — not as a stylistic flourish, but
because italics in this system are reserved specifically for moments
where Confidant's own interpretive voice is present, as opposed to a
plain restatement. A clarifying question is Confidant speaking as
itself, admitting a gap; that deserves the same typographic signal as
"here's how I'm reading this" in the Shared Understanding panel — both
are Confidant's voice, not neutral information.

### Thoughtful Waiting: A Sentence, Not a Percentage

The cycling phrase ("Understanding your situation… Updating our shared
understanding… Looking for what matters… Preparing a response…") is
paced at roughly 2.4 seconds per phrase — long enough to be read, not
glanced past — and never implies a completion percentage, because the
backend's actual reasoning process doesn't have one (see
`motion-and-latency-philosophy-v1.md`'s "never imply a false completion
percentage"). The small breathing dot beside it is the only literal
"loading" affordance in the product, and even it moves at the pace of
a slow breath, not a spinner's mechanical rotation.

### Shared Understanding: Correction Lives Next to the Claim, Not in a Menu

Each item under "what seems established" carries its own quiet
"not quite right" text directly beside it — not a settings menu, not an
edit icon requiring a mode switch, not a separate "manage your data"
screen. Correction has to be as immediate and low-friction as the
claim it's correcting, or people won't use it, and an understanding
surface nobody corrects is worse than useless — it's confidently wrong
(see `memory-and-shared-understanding-v1.md`'s correctability
principle).

### Returning After a Week: A Bridge, Not a Recap

The returning screen doesn't summarize the whole prior conversation —
it states the one thing a person needs to pick back up (what they were
waiting on) and the one thing that's genuinely new since then. This is
deliberately proportioned to feel like "so, where were we" from a
person who remembers, not a system generating a complete changelog of
everything that happened, which would read as surveillance rather than
memory.

### Mobile: Understanding Is a Strip, Not a Second Screen

On mobile, Shared Understanding collapses to a single quiet strip above
the conversation rather than disappearing into a separate tab or
requiring navigation away from the live exchange — consistent with
`accessibility-and-responsive-design-v1.md`'s "live exchange takes
priority; understanding accessible on demand, not competing for the
same limited space."

---

## Screen Flow: The End-to-End Journey

1. **First launch** → Welcome. A person arrives to an invitation, not a
   form. They begin typing directly into the composer that opens the
   product.
2. **First conversation** → The moment they send their first message,
   they're inside a Thread (see `information-architecture-v1.md`) —
   there is no separate "conversation created" transition; Welcome
   simply becomes the first turn of the Thread itself.
3. **Thinking** → After any message, Thoughtful Waiting's cycling
   phrase appears in place of where Confidant's next turn will land —
   never a separate loading screen, never a modal.
4. **Clarification** → When the backend doesn't yet know enough,
   Confidant's response is an italicized question, visually
   indistinguishable in weight from a statement — a complete, valid
   turn, not an apology.
5. **Shared understanding** → Reachable at any point via a quiet
   fold/unfold control at the top of the Thread — never forced on the
   person, never appearing as an interruption mid-exchange.
6. **Follow-up conversation** → The person continues in the same
   Thread; nothing about the interface changes structurally as a
   Thread grows, only the content within it.
7. **Returning after a week** → Opening a Thread from Home after time
   away replaces the ordinary Thread header with the Returning bridge
   for that first re-entry moment, then settles into the ordinary
   Conversation view once the person responds.
8. **Long-term use** → Home accumulates Threads, each with its own
   scoped understanding, never merging into a single global feed (see
   `information-architecture-v1.md`'s "one Thread, one situation, one
   understanding"). Nothing in the product changes shape as usage grows
   — there is no dashboard state waiting to be unlocked by continued use.

---

## Design Rationale

### Why a Single Live Artifact Instead of Per-Screen Descriptions

A design system described only in prose invites optimistic
interpretation — "warm neutral" can mean many things until it's an
actual `#E9E3D8` sitting behind actual Charter type at an actual 17px.
Building one cohesive, themeable prototype instead of a series of
disconnected mockup images makes every claim in this document checkable
against the same real tokens, the same real type, in both themes — the
same discipline the rest of this project applies to backend specs
(traceable, falsifiable claims, not adjectives).

### Why Charter, Specifically

Charter was chosen — over a generic system serif, a trendy display
serif, or a "safe" geometric sans like Inter — because it was
purpose-built for sustained on-screen reading comfort while retaining
real, warm character, which is exactly the tension this product's
typography has to resolve: content that's read closely and often, in a
voice that never feels manufactured or generic.

---

## Future Considerations

- This document and its live reference represent v1 of the concrete
  visual language — the same versioning discipline as every other
  spec in this set. A v2 should only happen after real usage reveals
  something this document got wrong, not from aesthetic preference
  alone.
- The live artifact currently demonstrates 8 screens at high fidelity;
  it does not yet cover every edge case (a Thread with many turns
  requiring scroll behavior, an error/partial-completion state per
  `frontend-engineering-architecture-v1.md`, or Settings) — those
  should be added to the same reference as they're designed, not
  described in a new, disconnected document.
- If real testing reveals the paper-grain texture, the italic-as-voice
  convention, or the no-bubbles conversation layout don't hold up with
  real people, revisit this document deliberately and record why —
  the same discipline `engine/decisions.md` applies to every backend
  revision.
