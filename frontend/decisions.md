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
