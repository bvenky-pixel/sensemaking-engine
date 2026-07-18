Every major product insight gets one entry. For example:
Why thinking is the product and conversation merely supports it.
Why Shared Thinking is bigger than the frontend.
Why understanding is felt, not opened.
Why the frontend never optimizes for difference.

---

**2026-07-07 — Interaction model rewritten from first principles, frontend documentation frozen**

Three sequential design reviews rejected the frontend's first two
interaction models and converged on a third. The first full design pass
(12 architecture documents plus a high-fidelity prototype,
`frontend/prototype/confidant.html`) was judged an excellent AI chat
application -- exactly what `frontend-philosophy-v1.md` already ruled
out -- and was deliberately not iterated on; the interaction model was
rebuilt from scratch instead (`interaction-model-v2.md`, a notebook
metaphor). The second review found the metaphor doing too much literal
work -- borrowing structure but demanding the person think in its terms,
the mistake the Macintosh's own desk metaphor avoided -- and corrected it
toward a durable idea, Shared Thinking, with the metaphor kept only as
inspiration (`interaction-model-v3.md`). The third review treated v3 as
sound but unfinished: elevate the foundational principle, state Shared
Thinking's arbitration rule explicitly, tighten ambient presence's
language, define a Journey emotionally rather than structurally, make
the backend's architecture felt as human understanding rather than
system behavior, add the Quiet Discovery moment, add an explicit
vocabulary section, make "never optimize for difference" a permanent
guardrail, and add the Ten-Year Test as a standing evaluation method --
producing `interaction-model-v4.md`, declared the definitive Interaction
Model for Confidant v1.

Every one of v4's "architecture made felt" moments was checked against
what the backend can actually support today, not what would be
compelling to design: Growing understanding, Deepening clarity, and
Named uncertainty are real, drawn directly from WorldState and Judgment;
Quiet Discovery is real within one Journey's own accumulated
understanding; "something noticed across Journeys" is explicitly not
built, because it depends on the backend's Learning process, a
deliberately unimplemented reserved slot (`engine/specs/system-
architecture-v2-specification.md`). This mirrors the same discipline the
Sensemaking Engine itself applies to Learning -- a compelling idea stays
in Future Considerations until the architecture underneath it is real.

v4 formally retired `interaction-architecture-v1.md` and
`memory-and-shared-understanding-v1.md` (both kept in git history, not
deleted, per this project's standing discipline of never erasing a
superseded decision) and absorbed their responsibilities in full.
`product-experience-v1.md` is marked superseded in part: its concrete
visual language (color, type, spacing) still holds, but its screens were
drawn against the old chat-shaped interaction model and are stale until
redrawn against v4 -- that redesign is deliberately not part of this
freeze. `information-architecture-v1.md`,
`frontend-engineering-architecture-v1.md`,
`accessibility-and-responsive-design-v1.md`,
`visual-design-system-v1.md`,
`developer-tooling-and-testing-strategy-v1.md`, and
`motion-and-latency-philosophy-v1.md` had their "Thread" terminology
mechanically updated to "Journey" to match; `information-architecture-
v1.md` additionally had its "Core Unit: The Thread" definition removed
outright, since `interaction-model-v4.md` now owns that concept and the
duplicate definition violated the same document's own "new spaces are
expensive" discipline. `frontend-philosophy-v1.md`, `emotional-design-
v1.md`, and `trust-and-privacy-ux-v1.md` needed no change at any point
across all three reviews -- every correction was to how faithfully the
interaction model honored them, never to the principles themselves.

**Status: Confidant frontend documentation is FROZEN as of this entry.**
Every document in `frontend/specs/` is internally consistent with
`interaction-model-v4.md` as of this commit: terminology matches, no
live document re-defines a concept v4 now owns, and every retired or
superseded document says so in its own status block rather than being
silently out of date. The one deliberately open item is the visual
redesign of the actual screens against v4 -- `product-experience-v1.md`
names this explicitly and it is not blocked by this freeze, only
sequenced after it. Reopening this freeze to change v4 itself, or any
document it now owns, requires the same discipline applied here: treat
it as a real design review, check every principle against Shared
Thinking and the Ten-Year Test, and update this log with what changed
and why -- not a quiet edit to a frozen document.

---

**2026-07-10 — `frontend/mvp/index.html` added: a throwaway placeholder UI, NOT a reopening of the freeze**

The backend gained its first real HTTP API this session
(`src/api/server.py`, see engine/decisions.md), and the user asked to
move toward a functional MVP -- explicitly a minimal end-to-end proof
first, not the v4-aligned redesign (still sequenced, still not started).
`frontend/mvp/index.html` is a single static HTML/JS file, no framework,
no build step, served directly by the API server via `StaticFiles` --
built solely to prove a real person can have a persistent, multi-turn
conversation with Confidant over HTTP. It does **not** implement
Journeys, Sessions, Home, or Settings (`information-architecture-v1.md`'s
three spaces), does not attempt ambient presence, Quiet Discovery, or any
other v4 experiential goal, and is explicitly disposable -- it exists
outside `frontend/specs/` and `frontend/prototype/` on purpose, so it's
unambiguous this isn't a second design direction competing with v4.

It still honors the two cheapest, hardest-to-retrofit constraints already
on record, since ignoring them would cost nothing to avoid and would mean
redoing this page's copy/interaction later rather than just its visuals:
- **No technical vocabulary** (`interaction-model-v4.md`'s explicit ban
  on "processing"/"generating"/"memory updated" etc.) -- waiting and
  failure states use plain human phrasing ("Confidant is considering what
  you shared…").
- **Writing and sending are distinct actions** (v4's "most protected
  interaction") -- a textarea plus an explicit "Share" button, never bare
  Enter-to-send.

It also honors `frontend-engineering-architecture-v1.md` principle 2
(partial completion represented honestly): a failed `failed_stage` from
the API produces a message describing what actually happened at that
stage, never a generic technical error.

A handful of CSS custom properties (paper/ink color tokens, serif/sans
font stack) were lifted from `frontend/prototype/confidant.html`'s
`:root` block for non-embarrassing baseline styling -- its rejected
chat-shaped structure and copy were not reused.

**This does not touch the freeze.** No document in `frontend/specs/` was
read as settled-and-then-changed by this addition; the v4 screen redesign
remains exactly as open and exactly as sequenced as the freeze entry
above already states.

---

**2026-07-10 — Executor's Clarity Brief wired into the placeholder UI**

Following the deployed prototype being judged output-quality-equivalent
to a generic LLM (see the corresponding `engine/decisions.md` entry), the
user chose a small, low-risk win before starting the bigger reasoning-
depth design push: expose the already-built-but-never-wired Executor
Clarity Brief (`src/executor/engine.py`, built 2026-07-05 but never
called from any live path per its own decisions-log entry).

Unlike Judgment/Planner, a Clarity Brief IS meant to be user-facing --
it's Executor's fixed-template synthesis of a completed turn (Situation/
Key Insights/Current Direction/Remaining Unknowns/Decisions), not raw
internal cognition -- so this isn't a violation of "Judgment/Planner stay
internal" (see `src/api/schema.py`'s `SendMessageResponse` docstring for
that separate, still-intact rule).

Added a plain-language toggle, **"See where things stand"** -- avoiding
both "summary" (mildly technical/report-like) and any synonym for
"analysis," consistent with the same no-technical-vocabulary constraint
honored everywhere else in this file. New `GET
/sessions/{id}/clarity-brief` endpoint (`src/api/server.py`) 404s with
"Nothing to summarize yet" until at least one turn has completed
Judgment and Planner -- reconstructs `WorldState`/`Judgment`/`Planner`
from the same `debug_json` blob `/debug` already reads, calls
`build_clarity_brief`/`render_clarity_brief` unchanged, returns both the
structured fields and a pre-rendered markdown string.

Frontend renders the structured fields directly via `textContent`-based
DOM construction (never `innerHTML` on request-derived content) rather
than parsing the markdown string, since the toggle panel needs simple
section/list styling, not a full markdown renderer -- one more thing this
throwaway placeholder deliberately doesn't need. Verified live: a
Playwright drive of the real page confirmed the pre-completion empty
state renders correctly and that submitting a message (hitting the
honest-failure path locally, no `OPENROUTER_API_KEY` set) leaves the
toggle showing the same graceful "nothing to summarize yet" message
rather than crashing -- exactly the behavior the 404 path is meant to
produce. Screenshot confirmed visual styling matches the rest of the
page.

---

**2026-07-10/11 — Build the real Confidant frontend (Svelte, per `frontend/specs/screen-design-v1.md`)**

`frontend/mvp/index.html` proved the pipeline works over real HTTP; it
was never meant to be the v4-aligned experience, and the freeze entry
above left that redesign explicitly open, sequenced after the reasoning-
depth work. With `screen-design-v1.md` drafted and approved as the
missing translation from v4's principles to actual screens, this entry
records that redesign actually getting built.

**Stack**: Svelte 5 (runes API) + Vite, scaffolded fresh in
`frontend/app/`. No CSS framework -- `tokens.css` carries the exact
visual values `screen-design-v1.md` said to reuse from
`product-experience-v1.md` (color pairs, Charter serif for read/written
content with italic as Confidant's own voice, system-ui for chrome only,
8/16/24/34/48 spacing rhythm, 260ms ease-out motion, the single hairline+
3px-radius raised surface). No router library -- three screens, local
component state (`App.svelte` holds `{screen, sessionId}`), no deep-
linking requirement yet. `frontend/mvp/` is kept, untouched, as historical
record (same treatment `frontend/prototype/` already got);
`src/api/server.py`'s `_FRONTEND_DIR` now points at `frontend/app/dist`.

**Backend addition**: `GET /sessions` (`src/api/db.py::list_sessions`,
`SessionSummary` in `src/api/schema.py`) -- Home needed a way to list a
person's Journeys, which no endpoint supported before (every prior one
is scoped to an already-known session id). No schema migration; reads
the same `world_state_json` blob every other endpoint already reads.
Also extended `ClarityBriefResponse` with `secondary_issues`/
`stagnation_notes`, passed through directly from Judgment in the
`/clarity-brief` endpoint -- Executor's own `build_clarity_brief`
template is unchanged; these two fields support the Understanding
region's "Quiet Discovery" moment, and both are already curated by
Judgment (held back unless genuinely significant), not raw internal
cognition surfaced for the first time here.

**Screens**: Home (Journey list via `listSessions`, one plain-text
"Begin something new" entry), Journey (Transcript + Composer +
AmbientPresence + Understanding), Settings (three static sections).
"Handing the page over" is a plain-worded "Share this" button; a
`<textarea>` naturally inserts a newline on bare Enter, so simply never
wiring a submit-on-Enter handler is the complete, correct implementation
of that rule, not a partial one. Ambient presence is a breathing circle
on a ~5s cycle, honest to the backend's two observable moments (start/
end of turn) -- no percentage, no progress bar.

**A real bug caught by writing the philosophy-conformance tests, not by
a user report**: the Understanding region's "Deepening Clarity" callout
was specified to fire on either an unknown resolving or a decision
moving forward, compared by count. Writing
`deepeningClarity.test.js`'s decision case surfaced that the second half
of that check cannot ever fire correctly: `build_clarity_brief`
(`src/executor/engine.py`) maps `decisions=[d.content for d in
state.decisions]` -- every decision regardless of status, not filtered
to open ones -- so a decision resolving never changes that list's
length. The buggy code also gated on `next.decisions.length` truthy
first, meaning it couldn't fire at all once the list emptied out, which
is the common case right after a resolution. Removed the decision-count
branch entirely rather than ship a heuristic proven not to fire for its
intended case; `noteDeepeningClarity` now only checks
`remaining_unknowns` shrinking, which is the one signal the current
Clarity Brief shape actually supports. Revisit if the brief ever exposes
decision status directly.

**Testing**: `vitest` + `@testing-library/svelte` + `jsdom`, scoped to
`developer-tooling-and-testing-strategy-v1.md`'s "philosophy conformance"
category rather than exhaustive UI coverage -- the composer never
submits on bare Enter (only the explicit action fires `onSend`), each
`failed_stage` value (via `honestFailureMessage`) renders a distinct
message with no technical vocabulary, the Understanding region never
renders raw backend field names, and the deepening-clarity callout fires
exactly once on the signal it can actually observe. Needed one config fix
beyond the initial scaffold: Vitest resolves the `svelte` package to its
server-side build by default, which throws `lifecycle_function_unavailable`
on `mount()` inside test render calls -- fixed by forcing
`resolve.conditions: ['browser']` under `process.env.VITEST` in
`vite.config.js`, plus a `src/tests/setup.js` importing
`@testing-library/jest-dom/vitest` for the DOM matchers. Also found and
fixed an unrelated repo-hygiene issue while staging this directory: the
root `.gitignore`'s Python-boilerplate `lib/` line was silently
swallowing `frontend/app/src/lib/` (a legitimate source directory, not a
build artifact) -- added a `!frontend/app/src/lib/` negation.

**Verified live**: real `uvicorn` server, real browser (Playwright,
Chromium), not a mock backend. Confirmed Home lists real sessions from
`GET /sessions`; confirmed bare Enter inserts a newline without
submitting and the explicit "Share this" click does submit; confirmed
the honest-failure path (no `OPENROUTER_API_KEY` set locally) renders
its plain-language message with no raw backend vocabulary, matching the
same behavior already screenshotted before this round's bug fix (the
fix only touched an unexercised branch, so no regression risk to the
earlier six screenshots). `npm run build` and the full `pytest` suite
(166 tests) both green.

**Explicitly out of scope this round**, per `screen-design-v1.md`
itself: multi-person/collaborative Journeys, archiving, mobile-specific
layout beyond the narrow-screen priority rule, the Foundations token-
showcase page, any Clarity Brief editing UI (no backend write path
exists), URL/hash-based routing, and "something noticed across
Journeys" (still gated on the backend's unimplemented Learning process).

---

**2026-07-11 — Real frontend deployed to `confidantsense.fly.dev`**

`src/api/server.py`'s `_FRONTEND_DIR` already pointed at
`frontend/app/dist`, but the Dockerfile still assumed the old
no-build-step placeholder -- it had no stage to actually produce
`dist/`, which is gitignored and not committed. Added a `node:22-slim`
build stage (`npm ci && npm run build`) ahead of the existing
`python:3.11-slim` stage; only the compiled `dist/` output is copied
into the final image, so the runtime image never carries
`node_modules`.

Deployed via the existing manual `deploy.yml` GitHub Actions workflow
(`flyctl deploy --remote-only`) rather than from this environment
directly -- the sandbox's own network policy blocks outbound requests
to both `fly.io` and `fly.dev`, so a GitHub-hosted runner with full
internet access is the only path to a real deploy here. Confirmed from
the run's own logs, not just a green checkmark: the frontend-build stage
really ran (`npm ci` installed 128 packages, `vite build` produced the
identical `dist/index.html` / `assets/index-*.css` / `assets/index-*.js`
output already verified locally), the final image copied that output in
(59 MB total), the machine rolled over and reached a healthy state,
Fly's own smoke checks and machine health checks both passed, and DNS
for `confidantsense.fly.dev` was verified. Could not additionally curl
the live URL from this session for the same network-policy reason the
deploy itself couldn't run here -- treating Fly's own passing health/
smoke checks as sufficient verification for this entry, consistent with
this project's practice of trusting the actual tool's own pass/fail
signal when a redundant check isn't reachable.

---

**2026-07-11 — `interaction-model-v4.md`'s "Novelty is not the goal" guardrail relaxed**

Following feedback that the real build (once actually used, not just
described) reads as uninspiring -- plain list rows, one undifferentiated
raised block for every kind of understanding regardless of whether it
was settled or still open, an unused `.display` typographic moment --
the user explicitly authorized relaxing v4's "novelty is not the goal"
guardrail: distinctiveness is now an acceptable design goal in its own
right, not only a permitted side effect of serving Shared Thinking.
Recorded directly in `interaction-model-v4.md` itself (see that
document's "One Permanent Guardrail, One Relaxed" section) rather than
left as an implicit understanding from this conversation -- the same
discipline already applied when Judgment's `Trajectory` field was marked
SUPERSEDED instead of silently reinterpreted. What did NOT change:
`frontend-philosophy-v1.md`'s "Things Confidant Should Never Become"
list (streaks, gamification, social features, AI gimmicks) was never
part of this guardrail and stays fully in force; the user explicitly
pushed back on streaks specifically when this came up. The Ten-Year Test
also stays unchanged and still applies to anything built under the
relaxed guardrail.

Apple Journal was the agreed form reference for what "more considered"
actually means here -- not its function (journaling suggestions,
streaks, wearable-derived prompts), which was separately discussed and
explicitly excluded except where independently scoped (bookmarking,
filtering, a stagnation-based "worth returning to" surface -- all queued
for the Home increment, not yet built). The lesson taken from Journal's
form: entries render as distinct cards on softly-colored backgrounds,
not plain list rows -- translated for Confidant into distinct *kinds* of
content getting distinct surfaces, not literal per-entry color variation
(which would have been a different, not-yet-authorized departure from
"every Journey card looks the same").

---

**2026-07-11 — Frontend redesign increment 1: Understanding region cards**

First concrete build under the relaxed guardrail above, sequenced
back-to-front as agreed (Understanding first, then Journey/Composer,
then Home). `Understanding.svelte` previously rendered every field --
situation, current_direction, remaining_unknowns, decisions,
secondary_issues, stagnation_notes -- as consecutive `<p>`/`<ul>` inside
one undifferentiated `--paper-raised` block, distinguished only by an
uppercase label. Restructured into three visually distinct surfaces by
*kind*, plus the asides staying exactly as they were:

- **"Where things stand"** (situation + current_direction): a card,
  `--paper-raised` background + the existing hairline shadow -- the
  settled, anchored surface.
- **"Still uncertain"** (remaining_unknowns): a card with the base
  `--paper` background and only a hairline border, no shadow --
  deliberately less visually anchored than the settled cards, matching
  that this content is open, not resolved. No new color tokens needed --
  reuses the existing paper/paper-raised distinction rather than
  inventing a third tint.
- **"In play"** (decisions): a card, same settled treatment as "Where
  things stand" but visually secondary (smaller top margin).
- **Quiet Discovery** (secondary_issues/stagnation_notes): unchanged --
  stays outside every card, unbordered `.voice.aside` text. Deliberate,
  not an oversight: v4 requires this read as a passing notice, never
  promoted to the same visual weight as settled content.

No new components, no prop changes, no backend changes -- purely a
markup/CSS restructuring within the existing component. Verified:
`npm run build` succeeded; the existing `Understanding.test.js` suite
(philosophy-conformance -- vocabulary, empty-state, deepening-clarity
callout) passed completely unmodified, confirming the redesign didn't
change any rendered content, only its visual structure; full `npm test`
(11 tests) green. Live-verified with a real `uvicorn` server and a
seeded session carrying a populated Clarity Brief (situation, an open
unknown, a decision, and both aside types all present at once) --
Playwright screenshots in both light and dark mode confirm the three
kinds are now genuinely distinguishable at a glance, and the "still
uncertain" card reads correctly as less settled than the other two in
both color schemes.

---

**2026-07-11 — Frontend redesign increment 2: Composer weight + scroll-edge fade**

Second increment under the relaxed guardrail, sequenced back-to-front
(Understanding done, this covers the rest of the Journey screen; Home is
still its own later increment). Two changes, both `Composer.svelte`/
`Journey.svelte` only -- no prop, behavior, or backend changes.

**Composer's "Share this"** previously inherited `tokens.css`'s global
`button` rule verbatim -- no background, no padding, same visual weight
as "Settings" or "← Home". v4 calls "handing the page over" its most
protected interaction; a plain text link undersold that. Added a `share`
class scoped to this one button (`--accent` fill, `--paper` text,
`var(--radius)` corner -- the same corner value already used for the
raised surface elsewhere, deliberately not a new pill shape, so this
doesn't introduce an unrelated shape vocabulary). Bare-Enter-never-submits
and the disabled-until-non-empty logic are both untouched.

**Scroll-edge fade**, the harder of the two: the whole app turned out to
have no fixed-height inner scroll panes anywhere -- Journey is one
continuously scrolling flow, `tokens.css`'s `body` has no `overflow`
rule. A `mask-image` on `.transcript` directly would only have baked a
static fade into the first/last message, not a live "dissolves as it
scrolls past" effect, and restructuring Journey into fixed scroll panes
(transcript bounded, Composer pinned) was judged too big a layout change
for this increment. Used a `position: sticky; top: 0` gradient overlay
instead (`pointer-events: none`, background reading `var(--paper)`
directly so light/dark both work with zero extra values) -- real content
genuinely scrolls underneath a fixed-position fade this way, with no
layout restructuring at all. Confirmed live rather than assumed: a
Playwright screenshot scrolled partway down a real seeded transcript
shows the top line of the previous message actually dissolving into the
background, not just present-but-dim.

Verified: `npm run build` and full `npm test` (11) green, no test
changes needed (purely visual, matching increment 1's pattern); full
`pytest` (183) unaffected, confirmed rather than assumed since no
backend files changed; live Playwright pass in both light and dark mode
covering the button at rest, enabled, and the scrolled fade.

---

**2026-07-11 — Frontend redesign increment 3 (final): Home**

Closes out the three-increment back-to-front redesign started with
Understanding, continued with Journey/Composer. The largest of the
three, since bookmarking and stagnation-signal surfacing didn't exist
anywhere in the backend yet (see the matching `engine/decisions.md`
entry for the additive `sessions.bookmarked` column and
`has_stagnation_signal`).

- **The reserved `.display` moment finally gets used.** Home's existing
  empty-state copy ("A quiet place to think something through.") moved
  out of its empty-only conditional and became Home's own persistent,
  always-shown greeting at 32px serif -- `product-experience-v1.md`'s
  own words for this token were "the Welcome headline only, the single
  largest moment of type in the whole product," and Home's greeting is
  exactly that. Reused existing, already-approved copy rather than
  writing anything new.
- **Journey rows became cards** -- the same settled-card recipe
  established in `Understanding.svelte` (`--paper-raised` + hairline
  shadow), kept as a local scoped duplicate rather than extracted into
  a shared class, consistent with how `Understanding.svelte` didn't
  extract one either.
- **Bookmarking**: a plain Unicode star (★ filled / ☆ outline,
  `aria-label`'d, no icon font/SVG dependency) inside each card. Had to
  be a `<span role="button">`, not a nested `<button>` -- the card
  itself is a button, and buttons can't nest in valid HTML;
  `event.stopPropagation()` on the star keeps a bookmark click from
  also opening the Journey. Verified live, not just via the API:
  toggling a star, reloading the page fully, and confirming the filled
  state survived the round trip -- not just that the request succeeded.
- **All/Bookmarked filter**: a plain-text `.ui-label` toggle pair above
  the list, calling the new `bookmarked_only` query param.
- **Stagnation-based "worth returning to"**: one `.voice.aside` line
  ("There's more to think through here.") inside a card, shown only
  when the backend's new `has_stagnation_signal` flag is true --
  deliberately the same muted, unboxed treatment Quiet Discovery already
  uses in `Understanding.svelte`, not promoted to its own visual weight.
  Fixed, generic phrasing this round, not Judgment's own worded
  `stagnation_notes` -- see the matching `engine/decisions.md` entry for
  why that's a deliberate scope-down, not an oversight.

Verified: `npm run build` and full `npm test` (11) green (no existing
test file for Home to break); full `pytest` (188, including 7 new
backend tests for bookmark/stagnation) green. Live Playwright pass with
three seeded sessions (bookmarked/plain, stagnant/not) in both light and
dark mode: cards render correctly, the filter actually filters, the
stagnation aside appears only on the one session that should show it,
and -- the one behavior that genuinely needed a real browser, not just
an API check -- the bookmark star's state survives a full page reload.

**Status: the three-increment frontend redesign (Understanding, Journey/
Composer, Home) is complete.** Everything scoped in this conversation
under the relaxed guardrail has shipped, tested, and been live-verified
in both color schemes. Remaining, explicitly deferred items from this
arc: the exact frontend surfacing shape for Learning's cross-Journey
patterns (needs its own design pass per `interaction-model-v4.md`),
richer stagnation wording sourced from Judgment's own `stagnation_notes`
instead of the fixed phrase, and live verification of the Learning Phase
1 walkthrough workflow.

## Warm & Alive redesign (2026-07-18)

Founder's own words: "it's very dull and boring, I would like it to be
more dynamic and modern yet calming, think headspace." A deliberate
full visual-language pivot, explicitly overriding several of
`frontend/specs/product-experience-v1.md`'s stated principles rather
than extending them -- recorded here plainly, not silently, since that
document is otherwise still treated as authoritative elsewhere in this
codebase.

**What v1's restrained "paper and ink" language explicitly rejected,
now deliberately reversed:**
- A bright, saturated accent "used decoratively" -- v2 uses a warm
  coral primary accent plus four supporting tones (periwinkle, sage,
  lavender, gold), the latter used specifically to color-code the six
  Counseling modes on ModeSelect (see below), a genuinely new,
  intentional use of color as information, not decoration for its own
  sake.
- "No rounded-everything signature" -- v2 goes fully rounded: 20-28px
  card radii, pill-shaped buttons (`--radius-pill`), explicit reversal
  of Composer's own former "reuses --radius rather than introducing a
  new pill shape" stance.
- A single flat 260ms/ease-out motion value everywhere, near-zero
  actual animation in the shipped code (confirmed by inventory before
  starting: only the AmbientPresence breathing dot and two un-eased
  hover snaps existed) -- v2 adds real `svelte/transition` (fade/fly)
  entrances across Home's Journey list, ModeSelect's mode cards,
  Transcript's messages/options, and Understanding's cards, plus a
  springier `--motion-bouncy` timing for the primary button and
  bookmark star.
- One serif (Charter) for all reading/writing text -- v2 replaces it
  entirely with a warm, rounded sans pairing (Quicksand for the display
  moment, Nunito for body/UI), loaded via Google Fonts in `index.html`.
  `--serif`/`--sans` kept as aliases pointing at the new fonts rather
  than renamed everywhere, so nothing broke from missing a call site.
- A single near-imperceptible 3px radius used in exactly two places --
  gone; every card/button/input now uses a real, felt radius.

**What v1's principles were explicitly KEPT, not overridden** (the
redesign is a re-skin, not a re-architecture): no chat bubbles --
attribution stays typographic (user text plain, Confidant's own "voice"
italic); no dashboard chrome, no completion-percentage/stage-progress
UI; dark mode is its own considered warm-charcoal world, not light mode
inverted; AmbientPresence's underlying honest, bounded, wordless
breathing mechanic (the JS-driven phase/slowdown logic, see
`AmbientPresence.svelte`'s own long-standing comments) is UNCHANGED --
only its visual rendering grew from a 14px flat dot into a layered
glowing orb (a soft blurred halo behind a gradient core), since the
mechanic itself was already sound and "more dynamic... calming" doesn't
require touching a component's actual honesty properties, just its
paint.

**The "settled card" recipe finally got shared.** v1 had this exact
rule -- `background: var(--paper-raised); border-radius: var(--radius);
box-shadow: 0 1px 0 var(--line);` -- hand-copied across Home
(`.journey-card`), ModeSelect (`.mode-card`), and Understanding
(`.card-settled`), each with its own "no premature abstraction yet"
comment. Now that all three want the IDENTICAL new treatment, sharing a
global (unscoped) `.card`/`.card-interactive` class in `tokens.css` is
warranted, not premature -- Transcript's `.option` chips and
Composer/Home's CTAs similarly now share `.btn-primary`.

**One real functional addition, not just paint**: Settings' delete
button finally has a real `--danger` color -- v1 explicitly had none
("full-contrast ink... is enough to mark this as the serious,
irreversible action," per that file's own prior comment) and a real
palette gap this redesign was well-positioned to close while already
touching every color decision in the app.

**Verification**: `npm run build` green; `npm test` (vitest) initially
FAILED 2/31 on `ModeSelect.test.js` with `TypeError: element.animate is
not a function` -- jsdom doesn't implement the Web Animations API
`svelte/transition` calls under the hood. Fixed with a minimal
`Element.prototype.animate` polyfill in `src/tests/setup.js` (the
standard, documented fix for this exact Svelte-transitions-in-jsdom
gap) rather than removing the transitions -- full suite green after
(31 passed). Live-verified with a real backend (`uvicorn`, built
`dist/` served directly, matching production -- not the Vite dev
proxy, which only forwards `/sessions` and would 404 on `GET /modes`, a
pre-existing gap unrelated to this round) via a Playwright script:
screenshotted Home, ModeSelect (confirmed all six mode cards render
with distinct color-coded left edges and dots), a fresh Journey, the
honest-failure path (no LLM key configured in the verification
session, confirmed the failure message itself renders correctly in the
new visual language), and Settings' danger-red delete-confirm state.
No backend/Python code touched this round -- `pytest` untouched by this
change, not re-run.

## Settings -- organizing pass (2026-07-18)

Direct founder feedback: "the settings screen is messy and needs
organizing." Previously the three sections (Privacy/Account/Data) were
loose, unbordered paragraphs running directly into each other with only
an uppercase `.ui-label` to distinguish them -- no card, no shadow, no
spacing device beyond a bottom margin. Now each section is its own
`.card`, with a small color-coded marker dot next to its label (same
scannability device ModeSelect already established for its six modes --
periwinkle for Privacy, sage for Account, coral for Data), so the three
sections read as three distinct things at a glance rather than one
continuous block of text.

Dropped one incidental addition (a `transition:fade` on Data's journey
rows) after it broke `Settings.test.js`'s removal test --
`queryByText(...)` after confirming a delete kept finding the row,
because jsdom's `Element.animate()` polyfill (see the polyfill's own
comment in `src/tests/setup.js`) doesn't reliably signal outro-
transition completion the way Svelte's real DOM implementation does, so
the node never actually left the DOM within the test's wait window.
Not worth extending the polyfill for one minor list-item fade -- reverted
that one transition, kept everything else. Full suite green after (31
passed); `npm run build` green; live-verified via Playwright screenshot.

## Home hero: orb + inline modes (2026-07-18)

Direct founder feedback, in two parts: "the home page is nice now but
since we are leaving most of the page empty how can we use it better,"
offering two candidate directions (a large button, or the same small
button with more messaging around it). Proposed a third, combined
option instead of picking between the two: a decorative breathing orb
as a calm focal point (reusing AmbientPresence's visual language, which
already existed and already fit "Headspace"), plus -- a further founder
idea in the same exchange -- bringing the Counseling mode picker
directly onto Home instead of behind an extra tap through ModeSelect.
The founder's own framing of that second idea's tradeoff ("home screen
is more cluttered but we reduce friction and clicks") is exactly right,
and resolved by making it conditional on `sessions.length`, not
permanent -- see below.

**New `components/BreathingOrb.svelte`**: same breathing-cycle math as
`AmbientPresence.svelte` (duplicated, not shared/imported -- see that
file's own comment on this codebase's small-utility-duplication
convention), deliberately WITHOUT the pulseCount/slowdown mechanic --
AmbientPresence's own docstring explains that mechanic exists
specifically to honestly reflect real backend stage-completion events
during a live turn; Home has no such events to reflect, so this is pure
ambient decoration (`aria-hidden="true"`, no `role="status"`), not a
status indicator wearing the same visual costume.

**New `components/ModePicker.svelte`**: the mode-card list extracted
out of `screens/ModeSelect.svelte` (which now just wraps it with its
own heading/back button), so Home's inline picker and ModeSelect's
full-screen picker share one implementation rather than drifting apart.
`ModeSelect.test.js` needed no changes after the extraction --
testing-library's queries traverse the full rendered DOM regardless of
component boundaries.

**Conditional, not permanent**: Home shows the hero (orb + "Pick what
fits right now." + inline `ModePicker`) only when
`loaded && !showBookmarkedOnly && sessions.length === 0` -- a
deliberately strict "genuinely empty account" condition, not a fuzzy
"few Journeys" threshold, so it's unambiguous to reason about and easy
to tighten later if the founder wants it to persist a little longer.
The moment a real Journey exists, Home reverts to exactly its prior
shape: filter toggle, journey card list, and the original small
`+Begin something new` button (still routing through the full
ModeSelect screen). `showBookmarkedOnly` is excluded from the condition
on purpose -- switching to the Bookmarked filter with zero bookmarks
should show the existing "No bookmarked Journeys yet." message, not the
new-account hero; the hero is for people who have never started a
Journey at all, not for an empty filtered view.

**New `loaded` guard**: previously Home had no concept of "not yet
fetched" distinct from "fetched and genuinely empty" -- both rendered
the same single-button UI, so the difference was invisible. Now that
the two states render completely differently (hero vs. list), a
one-frame flash of the wrong one before `listSessions()` resolves would
read as a glitch, not a loading state -- `loaded` (mirroring
`Journey.svelte`'s own identical guard) suppresses both branches until
the first real fetch completes.

Verified: `npm test` (31 passed, including `ModeSelect.test.js`
unaffected by the extraction), `npm run build` green, live Playwright
screenshots of both states (empty account showing orb + all six mode
cards; a real Journey correctly collapsing the hero back to the
original compact list + button).

## Orb, round two: bigger "in-flight" signal + Journey's own opening state (2026-07-18)

Direct founder feedback, two asks: "can we use it similar to Claude
during chat to let users know things are happening in the background,"
and "make the orb part of the chat screen in the opening of a chat as
the screen is empty."

**AmbientPresence grown from 40px to 72px.** Same honest, bounded
JS-driven breathing mechanic as before (`pulseCount`/slowdown logic
completely unchanged -- only the CSS dimensions and the scale/opacity
RANGES the same math drives grew, see the component's own updated
comment) -- a 40px orb tucked between messages was easy to miss
entirely, which is the opposite of "let users know things are
happening." Explicitly did NOT pair the bigger orb with any text or
label: v1's "no percentage, no stage labels, no text of any kind"
principle is one this redesign has deliberately kept throughout (see
the original "Warm & Alive" entry's own "what was kept" list) --
growing the orb's visual presence is not the same decision as adding
words next to it, and Claude's own chat "thinking" indicators don't
rely on stage-by-stage text either, just visible motion.

**BreathingOrb now also opens a fresh Journey**, not just Home.
`screens/Journey.svelte`'s existing empty-state branch (`loaded &&
messages.length === 0`) now wraps the opening-prompt text in an
`.opening-hero` alongside a `<BreathingOrb />`, mirroring Home's own
empty-account hero exactly (same component, same size) -- the same
"fill the mostly-empty space with something alive, not just one line
of text" fix, applied to the second place in the app that has the same
problem. `AmbientPresence` (the in-flight, honest, mechanic-bearing
version) and `BreathingOrb` (purely decorative, `aria-hidden`) stay
deliberately separate components -- Journey now uses BOTH, at different
moments: BreathingOrb before the first message exists, AmbientPresence
while a turn is actually in flight.

Verified: `npm test` (31 passed), `npm run build` green, live
Playwright screenshot of the new opening-hero state (orb above the
opening-prompt card, matching Home's treatment). The in-flight
AmbientPresence resize couldn't be caught in a live screenshot this
round -- this verification environment has no LLM key configured, so
turns fail near-instantly and the "sending" window is too brief to
reliably capture -- but it's the same proven radial-gradient technique
already visually confirmed via BreathingOrb, just larger CSS
dimensions on otherwise-unchanged, already-tested logic.

## Orb as consciousness (2026-07-18)

Direct founder framing, verbatim: "the orb is confidant it is
consciousness... I want a Buddhist zen like vibe to the orb... the
clarity notes that we see in the conversations should seem that they
are the orb's consciousness's perspective or thought. no change in
language or grammar we are talking strictly ui." Three changes, all
visual/markup only -- nothing generated by the LLM pipeline was
touched, per the explicit "strictly ui" constraint.

**BreathingOrb gets an enso.** The traditional zen brush-stroke
circle -- an intentionally incomplete ring, not a flaw -- drawn as a
static SVG (`stroke-dasharray` leaving a deliberate gap, rotated so
the opening sits where a hand-drawn one traditionally would) framing
the existing glow/core. `--ink-muted`, not `--accent`, so it reads as
a drawn line rather than a second light source competing with the
glow. Static on purpose: stillness is as much a part of the vibe as
the breathing is, so the one moving thing in the component (the core's
pulse) now has a fixed frame around it rather than everything moving.
Cycle length went from 5000ms to 7000ms -- slower, more meditative --
but only on BreathingOrb; `AmbientPresence` stays at 5000ms since that
orb is honestly reporting live backend activity during a turn, not
meditating, and slowing it would misrepresent what it's for.

**ZenQuote.svelte (new)**: a curated list of real, attributed
Buddhist/Zen/Taoist teachings (Buddha, Thich Nhat Hanh, Lao Tzu, Pema
Chödrön, Shunryu Suzuki, Dōgen, Ajahn Chah, Rumi, and a few unattributed
Zen proverbs) -- one picked at component creation, same pattern as
Journey.svelte's own `OPENING_PROMPTS` (changes on every fresh mount,
i.e. every page load, not on every re-render while the page stays
open). Rendered between the orb and the "Pick what fits right now"
line in Home's existing empty-account hero -- the orb now has
something to say, not just something to look at. New content, not a
restyle of anything the backend generates, so it isn't in tension with
the "no change in language" constraint (that constraint was about the
next change, below).

**Understanding.svelte now reads as the orb's own perspective** --
the actual request was specifically about this component ("the clarity
notes that we see in the conversations"), and specifically UI-only.
`.voice` already meant "Confidant's own reading" before this round
(see tokens.css's own comment on that class), but was only applied to
`current_direction` and the asides -- everything else in the panel
(situation, key_insights, tier2, remaining_unknowns, decisions) was
plain, unvoiced text. Now `font-style: italic` applies to every `<p>`
and `<li>` inside a card, uniformly -- same font size and color, so
density is unchanged, only the "whose words are these" signal is.
Default list markers are replaced with small gradient dots (same
radial-gradient recipe as BreathingOrb/AmbientPresence's own core), so
each bullet reads as one of the orb's own thoughts rather than a form
field. A static, unbreathing `.orb-signature` (10px, same gradient
again) sits at the top of the region as a seal marking whose section
this is, deliberately not animated -- a third moving orb on screen
would compete with AmbientPresence/BreathingOrb rather than read as
attribution. Settled cards also picked up a very faint radial-gradient
wash (the identical rgba value already used for the page-level ambient
background in tokens.css), so the cards read as lit from the same
source as the orb rather than as flat white panels. `ui-label`
headings ("Where things stand", etc.) deliberately stay upright,
non-italic -- they're navigation chrome, not the orb's own words, and
that contrast is what makes the voiced content actually read as
content rather than as one more label.

Verified: `npm test` (31 passed), `npm run build` green. Live
verification used a temporary standalone Vite entry point (mounting
BreathingOrb/ZenQuote/Understanding directly with mock props, same
tokens.css) rather than a seeded backend session -- Understanding
needs a completed Judgment+Planner turn to populate, and producing one
means either a real (billable) LLM call or hand-constructing a full
Judgment/Planner payload, neither of which was warranted just to
screenshot a CSS change against deterministic markup. The harness and
its entry files were deleted after the screenshot; nothing from it was
committed. Screenshot confirmed: enso ring renders correctly around
the (now slower) breathing core, the zen quote displays with
attribution, and the Understanding panel's cards show italicized text,
gradient bullets, and the orb-signature seal as designed.

## The orb stays, and it tells you what it's doing (2026-07-18)

Direct founder feedback, verbatim: "once the first response comes in
the chat window the orb suddenly disappears this is jarry [jarring],
let's continue having the orb. Also I would like some poignant loading
text corresponding to the backend process running so that latency
friction is reduced."

**The bug**: `Journey.svelte` only ever rendered an orb in two narrow
windows -- the empty-opening-hero (`messages.length === 0`) and while
`sending` was true. The instant a turn's response landed, `sending`
flipped back to `false` and the opening-hero condition was long since
false too (the user's own message had already pushed `messages.length`
past zero) -- so nothing rendered in that slot for the rest of the
Journey, every single turn. What read as "the orb disappears after the
first response" was really "the orb only ever exists for a few hundred
milliseconds per turn, forever."

**The fix**: a new persistent `.orb-companion` slot, rendered for the
entire conversation once the opening hero has passed (`{:else if
loaded}`), that always shows something instead of conditionally
showing AmbientPresence or nothing: `AmbientPresence` (full mechanic,
completely unchanged) while `sending`, a small idle `BreathingOrb` the
rest of the time. `BreathingOrb` gained a `compact` prop for this --
72px/36px, matching `AmbientPresence`'s own sizing exactly, and no
enso ring (that's the one reflective, attention-holding moment, right
for Home's hero; a small recurring companion shouldn't compete with
the transcript turn after turn). Same slot, same footprint, both
states -- swapping between idle and active now reads as a change in
intensity, not a disappearance.

**The loading text**: `openStageStream`'s real backend events
(`interpretation`/`judgment`/`planner`/`response`, one per pipeline
stage, from `src/orchestrator/engine.py`'s `on_stage_complete`) were
already wired into Journey's `pulseCount` counter but the actual stage
name was discarded on arrival. Now also mapped to a `STAGE_LABELS`
lookup and shown next to the orb while sending, crossfading between
phrases as each stage completes (`{#key stageLabel}` + `in:fade`):
"Taking in what you shared." (initial, before any stage event) ->
"Sitting with it for a moment." (after Interpretation) -> "Thinking
through what might help." (after Judgment) -> "Finding the words."
(after Planner). This is a deliberate, explicit override of v1's "no
percentage, no stage labels, no text of any kind" principle -- the
founder asked for precisely the thing that principle was written to
rule out, so the override is intentional and named as such here, not a
quiet erosion. What's kept from that principle's *spirit*, per
Understanding.svelte's own "no raw backend vocabulary" precedent: the
real stage ids never reach the screen -- no "Judgment," no
"Interpretation," no pipeline talk, just short, human, poignant
phrases a person would actually want to read while waiting.

Verified: `npm test` (31 passed), `npm run build` green, live
Playwright screenshot (same temporary-Vite-harness technique as the
prior round, deleted after use) confirming the idle-compact orb and
the sending orb-plus-label render at identical size/position, side by
side.

## The orb stays on Home too (2026-07-18)

Same-session follow-up, direct founder feedback: "the orb is not
present on the home screen after the first journey populates the
screen." Home had exactly the same shape of bug Journey just had:
the big hero orb is deliberately conditional on `sessions.length ===
0` (see "Home hero" above -- that tradeoff itself is still correct,
promoting six mode cards above real history every visit would be a
real cost for no benefit once Journeys exist), but nothing replaced
it once the populated branch took over, so Home's orb also went from
"always visible" to "never visible again" the moment the first
Journey existed.

Fix: a `<BreathingOrb compact />` (the same compact variant just built
for Journey's companion) now sits next to the greeting line, inside a
new `.header` flex row, shown whenever the populated branch is
showing (`loaded && (showBookmarkedOnly || sessions.length > 0)` --
the exact negation of the hero's own condition, so there's never a
frame with both orbs or neither). The big hero orb and this small one
never render simultaneously; a person always has exactly one orb
somewhere on Home, empty account or not.

Verified: `npm test` (31 passed), `npm run build` green. Live
verification this time used the real backend directly -- two Journeys
seeded straight into the SQLite session table via `src.api.db`
(`create_session` + `append_message`, no LLM calls, no cost) rather
than a mock-props harness, then a Playwright screenshot of the actual
served build confirmed the compact orb sits correctly beside "A quiet
place to think something through." once real Journeys are showing.
Seed DB and server process were removed after the screenshot.

## Reduce motion, as a real setting (2026-07-18)

Prompted by a question about whether the orb honored the OS-level
`prefers-reduced-motion` setting (it did -- both `BreathingOrb.svelte`
and `AmbientPresence.svelte` already checked it directly via
`matchMedia`), then a direct follow-up: "add a toggle for it in
settings."

New `src/lib/motionPreference.js`: a plain `localStorage`-backed
override, deliberately one-directional -- an app-level toggle can only
ADD the reduced-motion treatment, never remove it. This app has no way
to know why someone's OS asks for reduced motion, so Confidant's own
setting only ever agrees or defers to it, never overrides it off.
`prefersReducedMotion()` replaces the direct `matchMedia` calls in both
orb components (their own animation logic is otherwise untouched).

Scoped honestly, not just to the two orbs: the Settings copy says
"Calms the breathing orb and other motion throughout Confidant," so it
needed to actually do that, not just the two components that happened
to prompt the question. `tokens.css`'s existing
`@media (prefers-reduced-motion: reduce)` rule (already collapsing
every `transition`/`animation` app-wide to near-zero) now has a second,
independent trigger: `:root[data-reduce-motion] * { ... same rule
... }`. `applyReduceMotionAttribute()` sets/clears that attribute on
`<html>`, called once at startup (`main.js`, so the preference is
already in effect on first paint) and again immediately when the
Settings toggle changes (so the effect is instant in the current tab,
not just after a reload).

**Settings.svelte**: a real pill switch (`role="switch"`,
`aria-checked`, `--radius-pill` shape matching `.btn-primary`), added
to the Account section rather than a new fourth section --
information-architecture-v1.md is explicit that Privacy/Account/Data
are the whole surface, and this is a personal preference about how the
app behaves for this person, which Account already covers in spirit
(if not, until now, in any actual content beyond a placeholder
sentence).

Verified: `npm test` (31 passed), `npm run build` green. Live
verification against the real served build: clicked the toggle,
confirmed via `page.evaluate` that both `localStorage` and the
`data-reduce-motion` attribute updated immediately, then navigated
back to Home and confirmed the compact orb's own DOM picked up
`.reduced` (its already-existing lower-opacity static state) without a
page reload. Screenshots of the toggle in both states (off: quiet gray
pill; on: coral, matching `--accent`) confirm the visual design reads
correctly against the Account card.

## Privacy, made real -- frontend (2026-07-18)

Backend side in `engine/decisions.md` -- this is Settings' own Privacy
card, first of the founder's five-item roadmap, sequenced "least
effort for most impact" first. Three controls, all reusing components
this file already built rather than inventing new ones:

- **"Learn across Journeys" toggle** -- the exact same `.toggle`/
  `.toggle-thumb` pill-switch recipe built for Account's Reduce Motion
  toggle last round, same file, so the two read as one consistent
  control language rather than two different switch designs. Unlike
  Reduce Motion (pure `localStorage`, no server round trip), this one
  is backend-backed (`GET`/`POST /privacy/settings`) since it gates
  real server-side behavior, not just this browser tab's own CSS.
- **Export your data** -- `exportPrivacyData()` returns a `Blob`; a
  throwaway `<a download>` + `URL.createObjectURL` triggers the
  browser's own save dialog, the standard pattern for turning a fetch
  response into a file download with no extra endpoint or redirect.
- **Forget everything** -- the exact two-step-confirm pattern Data's
  own per-Journey "Remove" already established (ask once, confirm
  once, no native `confirm()` dialog), just wider in scope. Shares the
  `.confirm`/`.link-button.danger` classes with Data's version rather
  than duplicating the pattern.

**Real bug caught and fixed during live verification, not by any
test**: the confirm message ("Forget everything Confidant knows about
you? This can't be undone." + two buttons) is much longer than Data's
own short per-Journey confirm text, and `.confirm`/`.privacy-actions`
were both non-wrapping flex rows -- the message overflowed the card's
right edge instead of wrapping. Fixed with `flex-wrap: wrap` on both
containers plus `min-width: 0` on `.confirm` (flex items default to
`min-width: auto`, which refuses to let text wrap below its
max-content width inside a flex container -- the actual cause, not
just the missing `flex-wrap`). Confirmed fixed via a second screenshot
of the same confirm state. This is exactly why `frontend/specs/`'s own
verification discipline insists on a live screenshot, not just
`npm run build` succeeding -- a build has no opinion on whether text
fits inside a card.

Account remains a placeholder, deliberately -- see `engine/decisions.md`
for why (no auth/user system exists to attach real fields to yet).

Verified: `npm test` (35 passed, 4 new: default state on load, toggle
persists via the API, two-step confirm does nothing on Cancel, confirm
clears every Journey). `npm run build` green. Live verification against
a real served build with a seeded Journey (via `src.api.db` directly,
no LLM calls): screenshotted the Privacy card in its default state and
mid-confirm (catching the overflow bug above), then exercised the real
download (`page.expect_download()`, confirmed the JSON's `world_state`
field is a real parsed object, not an escaped string) and the real
reset (confirmed the Data section correctly falls back to "Nothing
shared here yet." afterward) end to end against the actual backend.

## Delete a Journey, from the Journey itself (2026-07-18)

Direct founder instruction: "move the function to delete individual
journeys to the journey screen rather than settings." Settings' Data
section had exactly one function -- per-Journey delete -- rendered as
a second, action-augmented copy of the same journey list Home already
shows. That's the wrong place for it: a person deciding to delete a
Journey is looking at that Journey, not navigating away to a settings
screen to find it again in a duplicate list.

**Journey.svelte** gains a `.journey-footer` at the very bottom of the
screen (past `Understanding`, same "destructive action stays out of
the way of the actual conversation" placement Settings already used
for its own Privacy actions) -- same two-step-confirm pattern as
everywhere else in this app (`askToDelete`/`cancelDelete`/
`confirmDelete`), calling `onBack()` on success since there's nothing
left on screen once the Journey is gone. `App.svelte`'s `onBack` is
already `goHome`, so this lands the person on Home, whose own
`listSessions()` refresh already shows the correct, updated list with
no extra plumbing needed.

**Settings' Data section is removed entirely**, not just its delete
button -- with deletion gone, a read-only duplicate of Home's own
journey list had no remaining content of its own (Privacy's export/
reset already cover "everything at once"). `information-architecture-v1.md`'s
three-named-sections framing is now two real ones (Privacy, Account),
not three where one is a hollow shell.

**`.link-button`/`.link-button.danger`/`.confirm`/`.confirm .voice`
promoted from Settings.svelte's own scoped styles into `tokens.css`**
-- the exact "more than one deliberate identical use warrants sharing,
not premature abstraction" threshold this file's own `.card`/
`.btn-primary` comments already established, now that Journey needs
the identical two-step-confirm recipe Settings/Privacy already use.
Carries forward the `min-width: 0` fix from the Privacy confirm
overflow bug earlier this round, so Journey's own (longer) delete
confirm message ("Delete this Journey for good? This can't be undone."
+ two buttons) wraps correctly from the start rather than needing the
same bug caught twice.

New `Journey.test.js` -- the first dedicated test file for
Journey.svelte, scoped to the delete action specifically (two-step
confirm does nothing on Cancel; confirms call `deleteSession` and
`onBack`). Writing it surfaced a real, previously-latent gap in
`tests/setup.js`: jsdom has no `window.matchMedia` at all, and no
existing test file had ever actually rendered `BreathingOrb` or
`AmbientPresence` (Home has no dedicated test file yet; ModeSelect
never renders an orb) to hit it. Fixed with a minimal polyfill,
`matches: false`, same "jsdom's own known gap, not a real bug"
category as the existing `Element.prototype.animate` polyfill right
above it.

Verified: `npm test` (33 passed -- 5 Data-section tests removed from
`Settings.test.js`, 1 new export test added there, 2 new tests in
`Journey.test.js`), `npm run build` green, full `pytest` unaffected
(436 passed, no backend touched this round). Live verification against
a real served build with two seeded Journeys (`src.api.db`, no LLM
calls): confirmed Settings now shows only Privacy/Account,
screenshotted Journey's new delete action in both states (default and
mid-confirm, confirming the wrap fix holds), and confirmed the full
delete-and-return-home flow end to end -- the deleted Journey is gone,
the other one remains, on Home.

## Tuck destructive/secondary Journey actions behind an overflow menu (2026-07-18)

Same-session follow-up. Direct founder worry, raised right after Delete
first moved onto the Journey screen: "having it during an ongoing
journey is too much, I risk losing data every time." That round's
`.journey-footer` was a standing, always-visible red delete link at the
bottom of every Journey, active conversation or not -- fundamentally
different from something a person has to go looking for, even with a
two-step confirm already in place. Then: "add other journey level
functions like bookmark in the same place."

**Journey.svelte's header row** now has a quiet "..." (`.menu-trigger`,
`aria-label="Journey options"`) next to the back button. Clicking it
opens `.journey-menu`, a small popover (`position: absolute`, anchored
under the trigger) containing Bookmark and Delete. A `$effect` adds a
capture-phase `document` click listener only while the menu is open,
closing it on any click outside `menuEl` -- standard click-outside
pattern, safe against self-triggering on the same click that opened it
since the effect only attaches after that click has already finished
dispatching. Delete keeps its own two-step confirm *inside* the menu
(the menu itself is the first "are you sure" layer; the confirm text
is the second) -- this is additive protection, not a replacement for
it.

**Bookmark, newly reachable from inside a Journey**: Home already has
a bookmark star per row, but reading/writing an open Journey had no
way to bookmark THIS one without leaving the screen. New `GET
/sessions/{id}/bookmark` (mirrors the existing `POST`, same
`SetBookmarkRequest` shape reused as the response) -- Journey fetches
it once on mount (`db.get_bookmark`, a plain `SELECT ... WHERE id = ?`,
same shape as the existing `get_session_mode`). Non-destructive and
reversible, so it toggles immediately on click and closes the menu --
only Delete needs a confirm step.

Verified: `pytest` (439 passed, 3 new -- default-false for a new
session, reflects a prior set, 404 on an unknown session). `npm test`
(38 passed, 6 in the rewritten `Journey.test.js`: menu closed by
default, opens on click with both actions visible, bookmark toggles
and closes the menu, an already-bookmarked Journey shows "Remove
bookmark" on open, delete's two-step confirm still works, outside
click closes the menu). `npm run build` green. Live Playwright
verification against a real served build with a seeded Journey: opened
the menu, bookmarked it (confirmed the star state persists across a
re-open), ran the full delete confirm and deletion, confirmed landing
back on Home's own empty-account hero once the last Journey was gone.

## Only populate a Journey on Home after a real message is sent (2026-07-18)

Same-session follow-up. Direct founder observation: "a new journey
should be populated only after a user response is shared or sits in
the chatbox empty back from a journey screens can be ignored." Real
bug, confirmed by reading the actual flow: `createSession` fires the
moment a person picks a mode (`ModeSelect.svelte`/`Home.svelte`'s own
`choose()`/`chooseMode()`), before a single word is typed. Backing out
of that screen without sending anything left a permanent "A new
Journey" row on Home forever -- there was no cleanup path anywhere in
the app for an abandoned, empty session.

Fixed with the same defense-in-depth shape as Privacy's own
cross-session-learning opt-out earlier this round (gate at both the
read path and the write/action path, not just one):

- **Read path** (`db.py::list_sessions`): the query now filters to
  `id IN (SELECT DISTINCT session_id FROM messages WHERE role =
  'user')` -- an empty session simply never appears on Home, covering
  every way a person might leave one behind (in-app back button, tab
  close, browser back), not just the one this round happens to wire up
  actively. `get_all_sessions_raw`/`get_aggregated_knowledge_for_pom`/
  the offline Learning/Insight Engine/POM scripts deliberately stay
  unfiltered -- an empty WorldState contributes nothing to any of that
  computation either way, so there's no reason to touch them.
- **Action path** (`Journey.svelte`'s new `handleBack`): the in-app "←
  Home" tap now actively deletes the session if `loaded &&
  messages.length === 0`, rather than leaving an orphaned row for the
  read-path filter to just hide forever. The `loaded` guard matters --
  a real Journey with real history also has `messages.length === 0`
  for the split second between mount and `getMessages` resolving;
  deleting on THAT window instead of the genuinely-empty case would
  have been exactly the kind of accidental data loss the founder's
  earlier overflow-menu request was about preventing. Deliberately
  unconditional on bookmark state -- a Journey bookmarked via the new
  overflow menu and then abandoned with nothing in it still has
  nothing worth keeping.

**Real test-suite ripple, handled directly rather than avoided**: six
existing backend tests created a session and checked it immediately in
`GET /sessions` without ever sending it a message -- correct under the
old behavior, now testing a scenario that can't happen. Fixed each by
giving the session a message first (`db.append_message` directly where
the message content/pipeline wasn't the point, a real
`POST .../messages` turn where it already was), preserving each test's
actual intent rather than just deleting them. One test
(`test_preview_text_falls_back_to_surface_complaint_before_any_message`)
had its entire premise become unreachable through this endpoint and
was removed outright rather than patched around. New direct regression
test: `test_list_sessions_excludes_a_session_with_no_messages`.

Verified: `pytest` (439 passed -- net even: one test removed, one
added). `npm test` (40 passed, 2 new in `Journey.test.js`: an empty
Journey gets deleted and navigates home on back; a Journey that
already has messages does neither). `npm run build` green. Live
Playwright verification against a real served build: picked a mode,
landed on the resulting empty Journey, tapped "← Home" without typing
anything, confirmed Home showed its own empty-account hero again (no
ghost entry) -- then confirmed directly against the SQLite file that
zero session rows remained, not just that the list endpoint was hiding
one.

## Home: time period + mode filtering (2026-07-18)

Home was still strictly `ORDER BY updated_at DESC`, no grouping of any
kind -- fine for a handful of Journeys, but the founder pointed out
that as the list grows it just becomes a long undifferentiated scroll.
Requested: a This week / This month / This year / All time toggle with
a count per bucket, and a mode filter scoped to whichever modes
actually appear within the selected bucket.

**Time buckets are computed client-side, in the browser's local time**,
not server-side. This app has no per-person timezone stored anywhere
(a known, already-documented single-user simplification) -- a
server-side "this week" would either hardcode UTC (wrong for most
people most of the time) or require building timezone infrastructure
nobody asked for. `startOfWeek`/`startOfMonth`/`startOfYear` are pure
functions in `Home.svelte`; week start is Monday (ISO convention, not
Sunday).

**Mode filter chips only render when there's something to filter**:
`modesInPeriod.length > 1` gates the whole row. A period with Journeys
in only one mode (or zero) shows no chip row at all -- directly serving
the founder's own "reduce the clutter" framing rather than adding a
filter UI that's redundant most of the time. Selecting a new time
period resets the mode filter rather than carrying it over silently,
since a mode selected in one period may not even exist in another.

**Per-mode color coding, shared rather than duplicated**: `MODE_TINTS`
already existed inside `ModePicker.svelte` (mode-card left edge + dot).
Home's new mode-filter chips and journey-card left border need the
identical colors, so it moved out to `lib/modeTints.js`
(`MODE_TINTS` + `tintFor(modeId)`), matching the same "more than one
deliberate identical use warrants sharing" threshold already applied to
`tokens.css`'s own `.card`/`.btn-primary`/`.link-button` recipes.
Journey cards get `border-left: 4px solid var(--mode-tint, transparent)`
-- a Journey with a chosen mode gets a colored edge, a legacy
mode-less one gets none (`transparent` fallback, not a fake default
color implying every Journey has a mode).

**Backend**: `SessionSummary.mode` is a new field (`Optional[str]`,
`None` for any Journey predating Counseling modes or created with none
chosen) -- `mode` was already stored per-session but never surfaced on
`GET /sessions`, so Home had no way to group without one request per
session. `db.list_sessions()`'s `SELECT` and row-unpacking extended to
include it; no change to filtering/ordering.

Verified: 2 new backend tests (`test_list_sessions_includes_chosen_mode`,
`test_list_sessions_mode_is_null_when_none_was_chosen`). New
`Home.test.js` (7 tests, using `vi.useFakeTimers()`/`setSystemTime` to
pin "now" so calendar-boundary math is deterministic regardless of
which real day the suite runs on): default All-time view shows
everything; each period button shows the right count; selecting a
period filters correctly; the mode chip row appears only when the
selected period has more than one mode present and filters on click;
changing period resets the mode filter; a period with nothing in it
shows a contextual empty message instead of the generic one; mode-tinted
vs. plain journey-card borders. Full suite: `pytest` 441 passed, `npm
test` 47 passed, `npm run build` green. Live Playwright verification
against a real served build with 5 seeded Journeys spanning all four
buckets and four distinct modes: period toggle switched correctly with
accurate live counts, the mode chip row correctly stayed hidden on
"This week" (only one mode present in that bucket) and appeared on
wider periods, and journey cards showed the right tinted edge per mode
with the mode-less legacy Journey left plain.

## One "all", not two (2026-07-18)

Immediate founder follow-up on the time-period toggle above: the new
"All time" period pill sat right next to the pre-existing All/Bookmarked
filter pair, so the screen showed two different, competing "All"
buttons doing two unrelated things (one over time period, one over
bookmark state). Collapsed the bookmark filter from an All/Bookmarked
pair down to a single "★ Bookmarked only" toggle -- off (the default)
already means "show everything the period/mode filters allow", so a
redundant explicit "All" had nothing left to mean. `toggleFilter` now
takes the next boolean directly from the one button's own click
handler instead of two separate buttons each hardcoding one side.

Verified: `npm test` still 47 passed (no test exercised the old
All/Bookmarked buttons directly). `npm run build` green. Live
Playwright screenshot against a real served build with a mix of
bookmarked/unbookmarked Journeys across periods and modes: only one
"All"-shaped control remains on screen (the period row), the bookmark
toggle reads as a single star pill that highlights when active.

## Auth, the low-friction way (2026-07-18)

Direct founder brief: "let's move towards building a basic
authentication layer... we will approach this like how chatgpt
launched -- the chat is available for use without login but will need
login to access settings and privacy features it will also need login
to continue a conversation beyond a certain number of responses...
login and signup should be as low friction and easy as possible."

This turned out to be a bigger shift than "add two gates" -- this
codebase had NO concept of data ownership anywhere until now (see
src/api/db.py's own module docstring, already flagging this as "a
stated single-user simplification, revisit if/when multi-user support
exists"). Every visitor to the deployed app was seeing the exact same
global Journey list. Fixing that was a precondition for the rest of
this feature meaning anything at all.

**Method chosen**: magic link (passwordless email), over Google OAuth
or email+password -- the founder's own explicit choice after being
shown the tradeoffs (OAuth needs a Google Cloud Console app registered
by the founder before any code could use it; password is the only
option needing zero external services, but is the highest-friction of
the three). Magic link needs a transactional email provider
(Resend, chosen for its simple API and generous free tier) -- until an
API key is configured, and always in tests, `src/api/email.py` just
logs the link to stdout rather than sending it, so login can always be
completed locally by reading server output (or, in tests, by reading
the pending token straight out of SQLite) -- same "no paid/external
calls unless explicitly configured" discipline this codebase already
applies to LLM calls in tests.

**Anonymous identity, introduced for the first time**: the server
mints an `anon_id` httpOnly cookie on a visitor's first request if none
exists (`resolve_identity` in src/api/server.py). Every Journey now has
exactly one owner -- `anonymous_id` if begun logged out, `user_id` if
begun signed in -- and `GET /sessions` is scoped to the caller's own
identity instead of returning literally everything. Signing up
(clicking the magic link) claims that browser's anonymous Journeys
onto the new account (`db.claim_anonymous_sessions`) -- signing up
must not cost a person the Journey they were already in the middle of,
which is the whole point of doing this the ChatGPT way rather than
requiring login upfront.

**Sessions**: an httpOnly, `SameSite=Lax` cookie backed by a plain
`auth_sessions` table (30-day lifetime, "as low friction as possible"
meaning not asking someone to log in again every few days) -- not a
JWT, matching this codebase's "no ORM, plain SQLite" simplicity
elsewhere; logout is a plain row delete.

**Where the two gates live**:
- Settings (both Privacy AND Account, reduce-motion included) gates
  behind sign-in entirely -- the founder's own phrasing ("access
  settings and privacy features") didn't carve out an exception for
  the one purely client-side preference already living there, so
  neither did this. A new shared `LoginGate.svelte` (email input ->
  "check your email" state, magic link only, no password field
  anywhere in this codebase) replaces the whole screen's content when
  signed out.
- The response cap (`ANONYMOUS_MESSAGE_LIMIT = 10` in
  src/api/server.py) is per-CONVERSATION, not cumulative across every
  anonymous Journey a browser has started -- read from the founder's
  own phrasing ("continue A conversation beyond a certain number of
  responses"). Checked server-side, before the turn runs, so a blocked
  11th message never reaches the LLM at all. Journey.svelte's
  `handleSend` rolls back the just-added optimistic user message when
  this fires (it was never actually recorded) and swaps the Composer
  for the same `LoginGate`, rather than leaving the transcript
  claiming something that didn't happen.

**Deliberately out of scope**: `privacy_settings`/`personal_operating_model`/
`learned_patterns`/`insights` all stay the single, global,
cross-visitor models they already were -- gating ACCESS to Settings
behind login is straightforward; making the underlying data genuinely
per-account is a real, separate project (documented plainly in both
this file and engine/decisions.md, not silently assumed away). A
Journey begun before this round (no owner columns set) is not
retroactively assigned one -- it simply stops being returned to
anyone, an honest, documented consequence of introducing ownership
after the fact, not a silent data-loss bug.

**Not built, and a known rough edge**: clicking a magic link reloads
the whole app fresh (this codebase has no router -- see App.svelte's
own comment), so logging in from the response-limit gate mid-Journey
lands back on Home, not the exact conversation that triggered it. The
Journey itself is never lost (it's right there in the signed-in
account's list to reopen) -- just not resumed automatically. Building
that would mean threading a return-to-session id through the emailed
link itself, real but modest extra scope, deliberately deferred rather
than silently promised.

Verified: 12 new backend tests (`tests/test_api_server.py`) covering
anonymous isolation between two browsers, 404-not-403 on a
guessed/foreign session_id, the full request-link/verify/claim flow, a
single-use token rejecting reuse, logout, the response cap firing at
exactly 10 and never applying to a signed-in sender, and Settings'
`login_required` gate. Full backend suite: 451 passed. Frontend: new
`lib/auth.svelte.js` (7 tests), extended `Settings.test.js` (signed-in
Account/logout + a new signed-out describe block, 8 tests total) and
`Journey.test.js` (response-limit gate + rollback, and a regression
test confirming an unrelated error still shows the generic honest-failure
message rather than the login gate, 11 tests total). Full frontend
suite: 59 passed, `npm run build` green. Live Playwright verification
against a real served build end to end: an anonymous visitor started a
Journey and saw only their own on Home; Settings showed the login
gate; requesting a link logged the real link via the dev-mode email
fallback; clicking it (same browser cookie) claimed the Journey onto a
new account and unlocked Settings with the real signed-in email;
logging out re-gated Settings; and a separately-seeded 10-message
anonymous Journey correctly blocked an 11th send with the login
prompt, with the unsent message never appearing in the transcript.

## Bookmark and delete require login too (2026-07-18)

Direct founder follow-up right after the auth layer shipped: "do not
allow delete and bookmark journey functions without login either."
Both had shipped usable anonymously in the first auth round -- correct
per the original brief ("chat available without login"), but the
founder wants these two specifically pulled behind the same gate as
Settings/Privacy and the response cap, not left open.

**Journey's overflow menu**: when signed out, the menu shows "Log in
to bookmark or delete Journeys." with a single "Log in" item instead
of the two actions themselves -- not a disabled/greyed-out version of
them, an actual replacement, matching "do not allow" literally. Tapping
it opens the same shared `LoginGate` as a small card between the
header and the transcript (not replacing the Composer the way the
response-limit gate does -- being signed out doesn't stop the
conversation itself, only these two actions).

**Home's per-row bookmark star**: same treatment -- tapping it while
signed out shows a `LoginGate` card near the top of Home instead of a
doomed API call. Reading a Journey's current bookmark state (the GET,
both here and in Journey's own onMount) stays unauthenticated on
purpose -- only the WRITE actions are gated (see
engine/decisions.md's matching note on the backend side).

**A "Log in" link at the bottom of Home, in line with Settings**
(direct founder ask): only rendered once `authState.checked` is true
and `!authState.authenticated` -- a person who just wants to log in
doesn't have to detour through Settings' own gate first to find where.
Disappears the moment `authState.authenticated` flips true (no need
for a redundant control once signed in -- Settings' own Account
section already has Log out).

Verified: 3 new backend tests (`tests/test_api_server.py`) -- an
anonymous caller gets `401 login_required` from both POST bookmark and
DELETE, and the GET read is unaffected; updated the ownership-isolation
test so the "stranger" browser logs in first (bookmark/delete now 401
before ownership is even checked for an anonymous caller, so proving
ownership isolation specifically needs a signed-in stranger). 6
existing tests updated to log in first, now that they exercise a
genuinely login-required action. Frontend: 2 new tests in
`Journey.test.js` (signed-out menu copy; tapping "Log in" opens the
gate and never calls setBookmark/deleteSession) and 3 new tests in
`Home.test.js` (Log in link visibility toggles with auth state; tapping
the star while signed out shows the gate and never calls setBookmark;
tapping it while signed in actually calls setBookmark). Full suite:
`pytest` 452 passed, `npm test` 64 passed, `npm run build` green. Live
Playwright verification against a real served build (same seeded
anonymous Journey as the auth round): Home showed both "SETTINGS" and
"LOG IN" side by side at the bottom; tapping the star showed "Log in to
bookmark Journeys."; opening the Journey and tapping "•••" showed "Log
in to bookmark or delete Journeys." in place of the two actions.

## POM surfaced to users (2026-07-18)

First item off the founder's own 5-part roadmap ("privacy/account
functional" [done], "surface POM without intimidating", "sharpen mode
responses", "seed POM early", "harden to level 4 maturity"), tackled
in that stated order at the founder's own request. The Personal
Operating Model (`src/pom/schema.py`, engine/decisions.md "Personal
Operating Model") existed as a real, computed backend concept with
zero frontend consumers until now -- `GET /personal-operating-model`
had nothing reading it.

**Where it lives**: a third Settings section ("You"), not a new
screen. information-architecture-v1.md treats Home/Journey/Settings as
exhaustive and requires a real justification before a 4th space is
allowed to exist -- nothing about POM clears that bar, and the
founder's own "without intimidating" framing itself argues for folding
this into an existing, already-understood space rather than a new
dashboard. `PersonalOperatingModel.svelte` is fully self-contained
(fetches its own data on mount, renders its own `.card.setting-section`
wrapper) and mounted in `Settings.svelte` as a fourth sibling section,
alongside Privacy and Account.

**Copy discipline, deliberately narrower than Understanding.svelte's
own pattern**: no raw backend vocabulary anywhere (no `ConfidenceLevel`
string like "high"/"moderate"/"unclear", no academic framework name --
Self-Determination Theory, Narrative Identity Theory -- ever shown as
a label), matching frontend-philosophy-v1.md/trust-and-privacy-ux-v1.md's
existing rule. A confidence level is used ONLY as a gate (skip a
sub-system below "unclear" or with no evidence) -- the visible content
is always the real, grounded evidence sentence(s) `src/pom/engine.py`
already extracted, never an invented felt-language translation of a
coarse category. This is intentionally more conservative than
Understanding.svelte's per-item card treatment: POM's underlying
frameworks are only lightly calibrated and the founder's own source
document was never committed (see `src/pom/schema.py`'s own caveat) --
staying close to the real evidence text is the honest choice until
that's verified, rather than writing confident-sounding narrative
prose a coarse "moderate" doesn't actually support. Visual language
matches Settings' own existing Privacy/Account sections (one card,
plain rows inside) rather than importing Understanding's separate
nested-card-per-item look -- stacking Understanding's own
shadowed cards inside a Settings card would double the "raised"
treatment for no reason; the two live in different contexts (a
floating region beside an active conversation vs. a settled screen a
person visits deliberately).

**Omit rather than show a hollow signal** (same discipline already
used elsewhere -- e.g. Home's mode-filter chips only showing modes
actually present): each of the 8 sub-systems renders only when it has
real content (a non-"unclear" level with non-empty evidence, or
non-empty free text/lists); an empty sub-system is skipped entirely,
never shown as a placeholder. If POM hasn't been computed at all yet,
or every sub-system is still empty, one quiet line ("Nothing standing
yet -- this builds up the more we talk.") replaces the whole content
area rather than an empty-looking section.

**Also gated the endpoint**: `GET /personal-operating-model` had zero
login requirement until now -- since it's real personal content inside
the already-login-gated Settings screen, it now requires
`Depends(require_user)`, same as the four Privacy endpoints (see
engine/decisions.md for the backend side).

Verified: 1 new backend test (`test_get_personal_operating_model_requires_login`)
plus 2 existing ones updated to log in first. New
`PersonalOperatingModel.test.js` (4 tests): quiet placeholder both when
POM is null and when POM exists but every system is unclear/empty; a
fully-populated fixture renders every system using real evidence prose
with zero raw category vocabulary on screen (explicitly asserted:
`queryByText(/moderate|unclear|redemptive/i)` all null), including
Motivation correctly showing only the two non-"unclear" dimensions and
omitting Competence; a partially-populated fixture (Identity only)
omits every other system individually. `Settings.test.js` mock updated
with `getPersonalOperatingModel` (defaulting to `null`, matching every
existing test's own intent -- POM is covered by its own dedicated
file). Full suite: `pytest` 453 passed, `npm test` 68 passed, `npm run
build` green. Live Playwright verification against a real served build
with a realistic seeded POM (`db.replace_personal_operating_model`,
mirroring the pytest fixture pattern rather than running the real LLM
call): confirmed the login gate still applies to Settings as a whole;
after signing in, all three sections render together (Privacy,
Account, You) with every populated POM system showing real prose and
Competence correctly absent since it was seeded "unclear."

## Two earlier login nudges + return to the same Journey after magic-link verify (2026-07-18)

The two remaining items on the auth-layer backlog (#185/#186), tackled
together. Prompted by a founder question about getting richer POM
signal faster ("have one POM question asked before Home") -- declined
as designed (a mandatory pre-Home gate is exactly the kind of forced,
survey-shaped touchpoint the "no manufactured urgency"/three-sanctioned-
spaces philosophy exists to avoid), but it surfaced that the app's OWN
login funnel had the identical problem in miniature: today a
signed-out visitor looks identical to a signed-in one until they hit a
hard wall (Settings, bookmark/delete, or the response cap) -- no softer
nudge exists anywhere before that.

**Nudge 1 -- Journey completion** (`lib/loginNudge.svelte.js`, new
module-level `$state`, same pattern as `auth.svelte.js`): leaving a
Journey that actually has real content (`Journey.svelte`'s own
`handleBack`, the `else if (loaded)` branch alongside the existing
empty-Journey-delete branch) is the "winds down" moment -- calls
`markJourneyCompleted(sessionId)`, which is a no-op if already signed
in or if this browser has EVER seen the nudge before
(`localStorage`-backed `confidant_completion_nudge_seen`, checked at
mark-time so several Journeys completed before Home ever renders still
only ever flags once). Home's own `onMount` calls
`consumeCompletionNudge()` once, which marks "seen" the moment it's
actually shown (not on dismiss) and renders a quiet, dismissible card
above the Journey list -- "Want to keep that accessible everywhere? Sign in"
-- that expands into the real `LoginGate` (carrying the completed
Journey's own id as `returnSessionId`, so signing in from here also
reopens that Journey, not just Home) only once tapped.

**Nudge 2 -- proximity to the hard cap** (`Journey.svelte`): a small,
dismissible note above the still-functioning Composer once an
anonymous Journey's own user-message count reaches
`PROXIMITY_NUDGE_THRESHOLD = 7` -- 3 messages before
`ANONYMOUS_MESSAGE_LIMIT` (10, `src/api/server.py`) actually blocks
anything. Hardcoded, not fetched from the backend (this codebase has no
shared-constants mechanism between the two) -- a real, acknowledged
coupling to keep in sync by hand if the backend limit ever changes.
Dismissing only hides it for the REST of this one Journey (in-memory,
not persisted) -- a different Journey that also gets close to the
limit shows it again, since it's a factually true, non-repeating-
within-one-conversation note, not a nagging global gate (deliberately
different discipline from the completion nudge's "once, ever" --
they're solving different problems: one is a single moment worth
mentioning once anywhere, the other is a per-conversation fact that's
true again each time it recurs).

Both nudges reuse the exact same `LoginGate` component every other
login surface in this app already uses -- no new form, no new copy
pattern, just two new places it can appear.

**#186 -- return to the same Journey after magic-link verify** (the
"known rough edge" flagged in "Auth, the low-friction way" above, and
the direct reason both `LoginGate` usages above now pass
`returnSessionId`): every `LoginGate` render site (`Journey.svelte`'s
two gates, the new completion nudge) now threads its own relevant
session id through `sendLoginLink(email, returnSessionId)` ->
`requestMagicLink` -> `POST /auth/request-link`; Settings' own
screen-wide gate has no session context and simply omits it (stays
`null`, the component's own default). `consumeMagicLinkFromUrl`'s
return shape changed from a bare `boolean` to `{ authenticated,
returnSessionId } | false` -- `App.svelte`'s `onMount` now calls
`openJourney(consumed.returnSessionId)` instead of landing on Home
whenever the server's own verify response actually included one (see
engine/decisions.md "Return to the same Journey after magic-link
verify" for why that value is server-authoritative, not read back out
of the URL). `Journey.svelte`'s own `onMount` is now wrapped in
try/catch, falling back to `onBack()` on failure -- the first time an
id reaching this screen ISN'T simply copied from Home's own
`session.id` list (a stale/foreign/deleted id degrading gracefully to
Home, not a permanently blank screen).

Verified: 3 new unit-test files/blocks --
`tests/loginNudge.test.js` (6 tests: pending/no-op-while-signed-in/
no-op-once-seen/consume-marks-seen/consume-returns-null-when-nothing-
pending/doesn't-burn-the-flag-on-an-unshown-nudge), a new "Home:
Journey-completion login nudge" describe block in `Home.test.js` (4
tests: shows once signed out, never shows signed in, dismiss hides it,
Sign in reveals the gate carrying the right session id), and a new
"Journey proximity login nudge" describe block in `Journey.test.js` (5
tests: below threshold, at threshold, never while signed in, dismiss,
Sign in carries the right session id) -- plus `auth.test.js` updated
for `consumeMagicLinkFromUrl`'s new return shape and `sendLoginLink`'s
new second argument, and `Settings.test.js`/`Journey.test.js`'s
existing login-gate tests updated for the extra `return_session_id`
argument now on every `requestMagicLink` call. Full frontend suite: 85
passed (was 70; +15 new). `npm run build` green. Backend: see
engine/decisions.md's own entry -- 481 passed. Not Playwright-verified
end to end: reaching the response cap or completing a real Journey
requires sending real messages through the live LLM pipeline, which
the founder's own standing "don't run another validation test now"
instruction holds off on -- unit/component coverage above exercises
every new code path (the nudges' visibility gates, dismiss, the
LoginGate wiring, the return-session round trip) with the LLM layer
mocked out, same boundary every other screen test in this app already
draws.

## Home's bookmark login gate moved below .bottom-links (2026-07-18)

Direct founder bug report: the "Log in" trigger for Home's own
bookmark-login gate lives in `.bottom-links`, at the very bottom of
the page -- but the card it opens (`showLoginGate`) rendered right
after the header, at the very TOP. On any account with enough Journeys
to need scrolling, tapping "Log in" (visible, at the bottom) opened a
card that was now off-screen above the current scroll position --
indistinguishable from the button silently doing nothing.

**Fix**: moved the `{#if showLoginGate}` block from right after
`.header` to right after `.bottom-links`, so it now renders directly
below its own trigger -- always in view the moment it opens, no scroll
required. Same "appear near what triggered you" placement discipline
`Journey.svelte`'s own `.actions-gate` comment already documents for
its own login card. `.login-gate-card`'s CSS flipped from
`margin-bottom` to `margin-top` to match (it now follows
`.bottom-links` rather than precedes the Journey list).

The Journey-completion nudge added earlier this same round
(`completionNudge`, see "Two earlier login nudges" above) was
unaffected -- it's triggered by leaving a Journey, not by an
on-screen Home button, so there's no equivalent "trigger is far from
its card" problem for it to have.

Verified: full frontend suite still 85 passed (Testing Library queries
by text/role, not DOM position, so no test assertions needed to
change) and `npm run build` green. Not re-verified with a live scroll
test (would need a real Journey list long enough to scroll, i.e. real
messages through the live LLM pipeline) -- the fix itself is a pure
DOM-reordering change with no new logic, so unit coverage plus a read
of the resulting markup order is enough confidence for this one.
