# Confidant Information Architecture v2

**Status: This supersedes `information-architecture-v1.md`** (kept in
git history as the visible reasoning trail, not deleted — same
precedent `interaction-model-v4.md` set when it superseded v2/v3).
Written 2026-07-21 after the founder confirmed, directly (see
`information-architecture-v2-tab-nav-proposal.md`'s discussion draft
and `engine/decisions.md`'s "Frontend IA v2" entry), that Activity and
You both clear v1's own "genuinely distinct question" bar for a new
space — an explicit, deliberate departure from v1's "exactly three
spaces" count, not a quiet erosion of it. Everything in v1 not
contradicted below still holds: the Journey-scoped-understanding
principle, the "new spaces are expensive" test itself (now applied
twice more, in the open, in the proposal doc this supersedes-note
points to), Settings' own minimalism, and the general navigation
philosophy.

---

## Purpose

Same as v1's own: name the minimum set of spaces Confidant needs, and
rule out anything a conventional product in this category would add by
default that doesn't clear the bar. v1 named three spaces and stopped;
this document names five, having applied the identical test to two more
candidates and found both defensible — see "Why Five, Not Three" below
for why this isn't a reversal of v1's discipline, but a second
application of it.

## The Five Spaces

### 1. Home

Narrower than v1's own Home. With Activity now owning "the list of
active Journeys" (below), Home is purely the entry/welcome moment: the
BreathingOrb hero, the opening-prompt invitation, a single unforced way
to begin a new Journey. A first-time visitor and a long-time one see
the same warm, quiet landing — Home no longer needs to also carry the
weight of "and here's your list," which is exactly what made deciding
"what remains of Home" (backlog #265) a real question worth asking
rather than an afterthought.

### 2. Activity

The person's list of active (and, per Journey's own no-archive-yet
stance, all) Journeys — literally `Home.svelte`'s own journey-list
markup, time-period/mode filtering and bookmark star included,
relocated wholesale, not rebuilt. This is NOT the "history browser
separate from Journeys" v1 explicitly rejected: that hypothetical was a
global feed of what was SAID inside Journeys, blending situations —
forbidden regardless of which tab it lives on, by "One Journey, One
Situation, One Understanding" below, which still holds without
exception. Activity is the same "which Journey do I open" list Home
always had; only its screen changed.

### 3. Journey

Unchanged from v1 — still the primary space, still holding the live
exchange and the accumulated understanding together, never
force-separated. Reached from Home's own opening invitation, from
tapping any row in Activity, or from the center navigation action
(below) — never a persistent tab-bar destination itself, since a
Journey is entered contextually (a specific situation), not browsed to
as an undifferentiated bucket.

### 4. You

Person-level self-understanding: the Personal Operating Model
(`PersonalOperatingModel.svelte`) and Behavioral Patterns
(`BehavioralPatterns.svelte`), both already-shipped, already
self-contained components, promoted out of Settings into their own
top-level space rather than a section a person has to remember exists
inside configuration. The distinct question this answers, per the
founder's own confirmation: "who am I becoming / what patterns do I
have" is genuinely different from "change my settings" — POM/Learning
output is something a person returns to and reflects on, not a control
they set once and forget, which is the opposite usage pattern Settings
is designed around.

### 5. Settings

Smaller than v1's own Settings, not larger — with You's content gone,
this is purely Privacy and Account, more aligned with v1's "kept
deliberately small" goal than before, not less.

**That's all — five, not more.** The same closing test v1 applied
still applies to anything proposed beyond these five: it must answer a
genuinely distinct question none of the five already can without
compromising what they're for.

## The center navigation action (not a sixth space)

The tab bar's center position (backlog #264) starts a new Journey via
the existing Mentor mode-select flow — it is deliberately NOT a space
with its own browsable content, and is not counted among the five
above. It's the same "Home hands you to a Journey" action v1 already
described, made reachable from anywhere via the tab bar itself rather
than requiring a trip through Home first — closer to a persistent "+"
affordance than a destination. Whether it's actively highlighted while
already inside a Journey is a `#261` tab-bar-shell implementation
question, not an information-architecture one.

---

## Guiding Principles (unchanged from v1, restated)

### 1. Structure Should Be Invisible When It's Working

Still holds. A five-space structure is a real increase in what exists,
which makes this principle MORE load-bearing than before, not less —
the tab bar itself must stay quiet furniture, not a thing a person has
to think about navigating.

### 2. One Journey, One Situation, One Understanding

Unchanged, unconditional. Nothing about Activity or You may ever blend
separate Journeys' understanding into one view — Activity lists
Journeys, it doesn't summarize or merge their content; You is about the
PERSON across Journeys (which is what POM/Learning were always
designed to be, per their own specs), never a per-Journey view leaking
into the wrong scope.

### 3. New Spaces Are Expensive, Not Free

Unchanged as a standing test. Applied explicitly, in the open, to
Activity and You in `information-architecture-v2-tab-nav-proposal.md`
— both accepted deliberately, not by default. The bar itself doesn't
lower just because this document names more spaces than v1 did.

---

## Navigation Philosophy (unchanged from v1)

Movement between spaces stays minimal, reversible, and never lossy;
navigation still never interrupts a live exchange. The tab bar itself
(backlog #261: bottom on mobile, top on desktop) is the concrete
mechanism for moving between the four persistent destinations (Home,
Activity, You, Settings) plus the center action — its own responsive
shape is that backlog item's scope, not renegotiated here.

---

## Design Rationale

### Why Five, Not Three

v1's "why three, not more" section described applying the New-Spaces-
Are-Expensive test until nothing further survived it, at the time. That
test was applied again here, explicitly, to two new candidates — see
`information-architecture-v2-tab-nav-proposal.md` for the full working:

- **Activity** survives because it doesn't add new CONTENT (it's Home's
  own existing list, relocated) — the tax is real (one more place to
  learn exists) but the benefit (Home freed to be a pure welcome
  moment, per backlog #265) was judged worth it.
- **You** survives on a genuine distinct-question argument (self-
  understanding vs. configuration) that the founder confirmed directly
  rather than this document assuming.
- The center action was judged NOT to be a new space at all (see above)
  — it carries none of the tax a real destination does.

This is not a reversal of v1's discipline; it's the same discipline,
run again, with a different, founder-confirmed answer this time.

### Everything else

v1's "Why This Document Doesn't Define Journey Itself" and "Why
Settings Is Small By Design" sections still apply verbatim and aren't
repeated here.

---

## Future Considerations (unchanged from v1, carried forward)

Same three (multi-person collaboration, archiving a resolved Journey,
a non-primary-surface reachability question) — none of the five-space
change above touches any of them.
