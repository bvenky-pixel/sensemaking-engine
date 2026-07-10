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
