# Confidant Screen Design v1

Status: **DISCUSSION DRAFT.** This is the "next, concrete design pass"
`interaction-model-v4.md` itself calls for and explicitly declines to
do ("No screens are designed here"; the handing-over gesture and the
ambient presence signal are "intentionally left to the next, concrete
design pass"). Nothing here changes v4, `frontend-philosophy-v1.md`,
`emotional-design-v1.md`, `information-architecture-v1.md`, or
`trust-and-privacy-ux-v1.md` — this document only makes the specific,
concrete choices those documents deliberately left open, so the three
sanctioned screens (Home, Journey, Settings) become buildable.

Reuses `product-experience-v1.md`'s visual tokens (color, type,
spacing, motion timing, iconography restraint) wherever they don't
conflict with v4 — those are unaffected by that document's own
superseded-in-part status, per its own note. Two of that document's
concrete patterns are explicitly NOT carried forward, because they
directly contradict v4:
- The cycling stage-narration text in "Thoughtful Waiting" ("Understanding
  your situation… Preparing a response…") — violates Ambient Presence's
  "no report of what stage of reasoning is happening."
- The foldable "Shared Understanding" panel as a separate surface — v4
  wants understanding felt as an ever-present moment, not opened.

Pending your sign-off before implementation begins.

---

## Stack

**Svelte**, no other framework. Rationale: its compiler-based approach
means component state is a thin, direct reflection of whatever variable
it's bound to — no virtual-DOM diffing layer sitting between "what the
backend returned" and "what's rendered." That fits Principle 1 of
`frontend-engineering-architecture-v1.md` ("Reflection of Backend Truth,
Never a Second Copy") more directly than a framework built around
reconciling an independent render tree. Small runtime, no server-side
rendering needed (the existing FastAPI `StaticFiles` mount stays exactly
as-is — Svelte compiles to static JS/CSS, same deployment story as
today's placeholder).

---

## Screen 1: Home

A single, calm list. Each row is one Journey: its name (or, before a
person has named it, the `surface_complaint` of its most recent Session,
truncated) and nothing else by default — no timestamp, no message count,
no "last active" badge (Information Architecture's "not a dashboard: no
counts, no metrics" rule, applied literally).

One affordance below the list: a plain-language way to start something
new (e.g. a single line of placeholder-style text acting as its own
entry point, the same pattern `product-experience-v1.md`'s Welcome
screen used for its composer-as-CTA — that specific pattern doesn't
conflict with v4 and is worth keeping). No category picker, no required
intake form (Information Architecture: "an invitation, not a form").

First-time state: the list is simply empty, and that one entry point is
the only thing on the screen — closer to a blank page than an onboarding
wizard, per Information Architecture's own description.

**API mapping:** the list is `GET`-derived from whatever session-listing
capability exists (today's API has no multi-session-per-user listing
endpoint yet — see Out of Scope below). Starting a new Journey calls
`POST /sessions`.

---

## Screen 2: Journey

One screen, two regions, always both visible — never a foldable panel,
never a separate route. On narrow screens (per
`accessibility-and-responsive-design-v1.md` Principle 4), the live
exchange takes priority and the understanding region becomes reachable
on demand (a single tap/scroll away, not hidden behind a fold-and-lose
toggle) rather than fighting the exchange for the same space.

### 2a. The live exchange

Renders the transcript from `GET /sessions/{id}/messages`. No chat
bubbles, no alternating background colors. Attribution between the
person's own words and Confidant's comes from typography alone, reusing
`product-experience-v1.md`'s already-validated pattern: the person's own
words in the regular serif body voice; Confidant's reflecting turns set
in the italic "section voice" already defined there. This gives the
required at-a-glance distinction (Interaction Architecture's "a person
needs to be able to tell... without reading closely") without needing
bubble chrome.

**Handing the page over** (the concrete form of v4's most protected
interaction): an always-present, always-open text field — writing is
never blocked or gated. Beneath it, one small, plainly-worded action
(not styled or labeled as a "Send" button — plain text like "Share
this") that must be deliberately activated; bare Enter never submits.
This is structurally the same two-action shape the current placeholder
already uses (textarea + explicit button) — what changes is tone and
framing, not the underlying mechanic, which was already sound.

**Ambient Presence** (the concrete form of the wordless signal): a
single soft shape — a circle at ~40% opacity, expanding and contracting
on a slow ~5-second cycle (paced like a breath, per v4's own words) —
appearing where Confidant's next words will land the moment the page is
handed over, and dissolving the instant a response (or an honest
failure message) arrives. No percentage, no stage labels, no text of any
kind on or near it. This is honest to the backend as it exists today,
which only ever reports two moments — start-of-turn and end-of-turn/
failure — never intermediate stage progress
(`motion-and-latency-philosophy-v1.md`'s own observation), so this
design asks for nothing the backend can't back up.

**On honest partial failure:** `failed_stage` from
`POST /sessions/{id}/messages` maps to plain language already written
and shipped in `frontend/mvp/index.html`'s `honestFailureMessage`
function — reused verbatim, since it already satisfies both the
vocabulary rules and Principle 2 (partial completion shown honestly, not
a generic error).

### 2b. The accumulated understanding

Realizes v4's "Growing understanding" moment — "the single most
structurally important moment in the product" — directly from
`GET /sessions/{id}/clarity-brief`. Rendered as continuous prose/short
sections, not a data table and not a collapsible panel: Situation and
Current Direction as short prose paragraphs; Remaining Unknowns and
Decisions as short plain lists. No field is ever labeled with its
backend name (no "Judgment," no "confidence: 0.7") — the Clarity Brief
endpoint's output is already vocabulary-clean, so this is a direct
render, not a translation layer that needs building.

Two more of v4's five moments layer onto this same region, inline, not
as separate widgets:
- **Named uncertainty** — when `remaining_unknowns` is non-empty, phrase
  it as direct, honest surfacing ("still uncertain about...") rather
  than a bare bullet list of database rows.
- **Deepening clarity** — when a re-fetched Clarity Brief shows a
  previously-listed unknown has dropped off, or a decision has moved
  from open to resolved/deferred, that specific change gets a one-line
  callout the next time the understanding region renders — "something
  has become clearer" in v4's own words — rather than silently updating
  with no acknowledgment.

**Quiet discovery** (the fourth buildable moment) surfaces from
Judgment's `secondary_issues` and `stagnation_notes` — both already
designed, per their own specs, to hold back anything not genuinely
significant. When either is non-empty, render it as a soft, reflective
aside near the understanding region ("I hadn't seen it that way before"
framing, never "the AI found something") — never as an alert, never
colored as a warning.

**Explicitly not built this round:** "Something noticed across
Journeys" — the fifth moment — stays out of scope; it depends on the
backend's Learning process, a deliberately unimplemented reserved slot.

---

## Screen 3: Settings

Small, per Information Architecture's own description: privacy
controls, account basics, data management. No screen-level design
beyond a plain list of these three sections is needed for a first
build — genuinely nothing else belongs here.

---

## Out of scope this round

- Multi-session-per-user Journey listing on Home — today's API has no
  "list my sessions" endpoint (only per-session operations); this needs
  a small backend addition before Home can show more than one Journey.
  Flagging now so it isn't a build-time surprise.
- Any editing/correction UI for the Clarity Brief's content — Trust &
  Memory principles require a correction to be real (backend-confirmed),
  not cosmetic; no such write path exists in the API yet, so no edit
  affordance is designed here either.
- Returning-after-a-week re-entry treatment, mobile-specific layout
  beyond the narrow-screen priority rule above, and the Foundations
  token-showcase page from `product-experience-v1.md` — all deferred to
  a follow-up pass once the core three screens exist and can be judged
  against real use.
- Exact color/type/spacing VALUES: reuse `product-experience-v1.md`'s
  token table directly (hex codes, type scale, spacing rhythm, 260ms
  ease-out motion default) rather than re-deriving them here.

---

## Verification, once approved

1. Build against `src/api/server.py`'s real endpoints, no mock backend.
2. Confirm every banned-vocabulary/banned-pattern rule from v4 and
   `emotional-design-v1.md` against actual rendered copy, not just the
   design intent above.
3. Exercise all four `failed_stage` cases live (interpretation/judgment/
   planner/response) and confirm each renders its correct honest message,
   not a generic fallback.
4. Real multi-turn session in a browser: confirm the understanding
   region updates only via re-fetching `/clarity-brief` (never an
   optimistic local edit), and that a "Deepening clarity" callout fires
   correctly when a resolved unknown/decision actually changes between
   two real turns.
