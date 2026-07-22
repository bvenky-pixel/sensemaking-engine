# Information Architecture v2 — 5-Tab Navigation Reconciliation

**Status: DISCUSSION DRAFT (2026-07-21, backlog #260).** Written before
any of #261-265 (the tab-bar shell, Activity tab, You tab, center
Share/Journey tab, and what remains of Home) are built — those are all
explicitly downstream of this document resolving first. This is a
design document, not a schema or code change. No implementation is
implied until the founder confirms the reconciliation below.

---

## The conflict, stated plainly

`information-architecture-v1.md` does not name "exactly three spaces"
as an arbitrary starting point — it presents that count as the RESULT
of applying its own "New Spaces Are Expensive" test until nothing
further survived it, and it explicitly walks through and REJECTS two
of the very things the pending "5-tab" backlog cluster now asks for:

- Its own worked example of a rejected 4th space: **"a 'history'
  browser separate from Journeys."** Backlog #262 asks for an
  **"Activity tab"** that extracts the past-Journeys list out of Home
  into its own screen.
- Its own stated goal: **"Settings is... kept deliberately small"** and
  should "stay genuinely minimal for as long as the philosophy holds."
  Backlog #263 asks to **extract "You" (POM + Behavioral Patterns) out
  of Settings into its own top-level tab** — not just trimming
  Settings, but promoting what's currently one of Settings' own
  sections into a fifth top-level space.

This document exists because the honest answer is that the "5-tab nav"
backlog cluster, taken at face value, asks for a genuine departure from
v1's own reasoning — not a small extension of it. Papering over that
with clever reframing would be dishonest about what's actually being
asked for. The right move is to say so plainly and let the founder
decide, the same discipline this session has applied to every other
real architectural fork (see e.g. the orchestrator skip-logic
proposal).

---

## Working through each proposed tab against v1's own test

v1's test for a new space: does it "answer a genuinely distinct
question that Home, a Journey, or Settings cannot answer without
compromising what they're already for"?

### Home + Activity (backlog #262, #265)

Home's ORIGINAL definition already includes "a calm, quiet list of the
person's active Journeys" — Activity, as described, doesn't introduce
new information; it relocates information Home already shows today to
its own screen. That's meaningfully different from v1's rejected
"history browser," which was envisioned as a separate view of PAST
CONTENT inside Journeys (a global feed blending situations) — the exact
thing "One Journey, One Situation, One Understanding" forbids. A tab
that's just "the list of Journeys, on its own screen" is not that; it's
the same list, moved.

The real question is what's LEFT of Home once the list moves out
(backlog #265's own open question) — if Home becomes a pure "start
something new" landing moment (the BreathingOrb/opening-prompt hero,
already built) with Activity as the literal list, that reads as
**splitting one space into two along an existing seam**, not inventing
new content. But it IS still one more top-level thing to learn exists,
which v1's "New Spaces Are Expensive" tax applies to regardless of
where the content came from.

### You (backlog #263)

Unlike Activity, this one doesn't have a "just relocating existing
content losslessly" defense available in the same way — POM/Behavioral
Patterns already live in Settings today, and moving them out doesn't
reduce what a person has to learn exists; it makes that content a
first-class destination instead of a scroll-past section. The
plausible, NOT-yet-founder-confirmed argument for why this clears v1's
bar: "who am I becoming / what patterns do I have" is arguably a
genuinely different question from "change my settings" or "manage my
privacy" — the same kind of distinct-question test v1's own Settings
section describes it wanting an answer to. This document does not
unilaterally decide that argument succeeds; it's exactly the kind of
call v1 itself says needs to be made deliberately, not by default.

### Center Share/Journey tab (backlog #264)

This one plausibly ISN'T a new space at all under v1's own vocabulary —
it's described as an action (start a new Journey via Mentor mode-
select), not a place with its own content to browse. Home already
"hands you to a Journey" the same way; this just makes that same
action reachable from anywhere via the tab bar itself, the way a "+"
button in a tab bar commonly works elsewhere. No new content, no new
"what am I looking at" moment — closer to a navigation affordance than
a fourth (or fifth) space.

### Settings, once You is extracted

Removing You leaves Settings with just Privacy + Account — SMALLER than
today, more aligned with v1's own "kept deliberately small" goal, not
less. No tension here.

---

## What this document is NOT proposing

- No specific final visual/interaction design for the tab bar itself
  (backlog #261's own scope).
- No claim that the 5-tab shape is definitely right or definitely
  wrong — that's the founder's call, informed by the analysis above,
  not something this document settles unilaterally.
- No implementation of any of #261-265 -- all remain blocked on this
  document's own resolution.

## Recommendation

**Two of the five tabs (Home-split-into-Activity, and the center
Share/Journey action) read as consistent extensions of v1's own
reasoning, not violations of it.** The one item that's a genuine,
first-class departure from v1's explicit goals is **You** getting its
own top-level space — defensible on a "genuinely distinct question"
argument, but that argument needs the founder's own sign-off, not an
assumed yes, before `information-architecture-v1.md` gets superseded by
a v2 that names five spaces instead of three.
