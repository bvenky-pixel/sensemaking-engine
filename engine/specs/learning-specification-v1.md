# Learning v1 — Specification

**Status: IMPLEMENTED, offline-only, not yet enabled in production.**
Written retroactively (2026-07-18, backlog #212) to give Learning the
same versioned-spec treatment every other mature component already
has, and to consolidate — in one place — the real prerequisites that
stand between "Learning is implemented" and "Learning runs for real
users," which were previously scattered across three different files.

## What Learning is, and what it isn't

Learning answers one question: *has a Goal or Decision's status
changed enough times, in a mechanically-countable way, to call it a
pattern?* It is the **Behavioral Pattern System** — one of the nine
systems the founder's Personal Operating Model vision document
describes. It is deliberately NOT an LLM call, NOT semantic clustering,
and NOT a diagnosis: `src/learning/engine.py::compute_behavioral_patterns`
groups `BehavioralEvent`s by `(event_type, new_status)` and reports a
pattern only when a group's count meets `MIN_EVIDENCE` (currently 3,
explicitly uncalibrated — see Open Questions below). Silence below the
floor is the correct, intended output, not a bug to work around.

**Learning and POM are siblings, not competitors** (see the 2026-07-18
reconciliation in `src/learning/engine.py`'s own docstring): the
vision's other 8 systems (Identity, Motivation/SDT, Belief,
Relationship, Learning Style, Stress, Narrative, Theory of Mind) are
POM's charter, already shipped in `src/pom/engine.py`. Learning owns
system 9 only. Any future "richer Learning" work should mean deepening
the Behavioral Pattern System itself (e.g. the vision's own example,
"delays decisions while seeking more certainty" — semantic clustering
across differently-worded content, infrastructure that doesn't exist
yet), not re-attempting POM's 8 systems here.

## Architecture

1. **`src/instrumentation/events.py::diff_behavioral_events`** — pure,
   diff-based (not recorder-threaded, see that module's own docstring
   for the specific double-counting bug this design avoids). Called
   from `src/orchestrator/engine.py::run_turn` on every turn; returns
   an empty list on most turns (most turns change nothing's status).
2. **`src/api/db.py::save_events`** — the persistence boundary. Gated
   on `is_events_enabled()` (`CONFIDANT_RECORD_EVENTS`, off by
   default everywhere including production — see Open Questions).
   Writes to the `behavioral_events` table, an append-only Memory
   Store spanning every session.
3. **`scripts/run_learning.py`** — offline only, never called from a
   live request. Reads `db.get_all_events()` (the ENTIRE Memory Store,
   with no per-account scoping — see Open Questions), computes
   patterns, truncate-and-replaces the `learned_patterns` table.
4. **`GET /patterns`** — read-only, unauthenticated today, returns the
   whole (global) `learned_patterns` table. Not yet consumed by the
   frontend (see Open Questions).

## Non-goals (unchanged from the original reserved-slot scope)

Learning never writes to a live WorldState, never runs inside a live
conversation turn, and never makes an LLM call. Its output feeds
forward only as far as `GET /patterns` today — wiring it into a live
Interpretation/WorldState-seeding step is a separate, later, explicitly
unstarted increment.

## Open questions — the real sequencing, consolidated

Three items were previously scattered across `src/instrumentation/
events.py`'s docstring, `frontend/specs/trust-and-privacy-ux-v1.md`'s
Principle 6, and backlog #257 — written together because they form one
real dependency chain, not three independent nice-to-haves.

1. **No per-account scoping — RESOLVED 2026-07-18** (see
   engine/decisions.md "Learning made per-account"). `learned_patterns`
   now carries a real `user_id` (same non-additive migration pattern
   `personal_operating_model` used); `get_events_for_user(user_id)`,
   `replace_learned_patterns(user_id, ...)`, `get_learned_patterns(user_id)`
   all scope correctly; `GET /patterns` now requires login;
   `export_all_data`/`reset_all_data` both now include/delete a
   person's own share correctly. The cross-account leak this item
   described is closed.
2. **No frontend disclosure surface.** `frontend/specs/
   trust-and-privacy-ux-v1.md`'s Principle 6 requires, before real
   behavioral data should accumulate: patterns traceable to real,
   inspectable evidence (the `{statement, evidence, evidence_count}`
   shape already used elsewhere), and a way to see them at all.
   Nothing in the frontend surfaces `GET /patterns` today (backlog
   #214, now unblocked by (1) above).
3. **No deletion path for `learned_patterns` independent of a full
   database wipe — RESOLVED alongside (1)**: `reset_all_data(user_id)`
   now deletes exactly this account's own `learned_patterns` rows,
   real per-account attribution having made this possible for the
   first time.

**Status: all three RESOLVED 2026-07-18.** #214 shipped Settings' new
"Patterns" card; `CONFIDANT_RECORD_EVENTS = "1"` is now set in
`fly.toml` (#211) — committed, not yet deployed as of this spec
revision; takes effect on the next `deploy.yml` run. Backlog #213
(calibrating `MIN_EVIDENCE` against real data) remains blocked until
real production data has actually accumulated after deploy — a
same-day calibration attempt would have nothing real to calibrate
against yet.

4. **Backlog #268 — CONFIRMED 2026-07-19** ("no recurring computation
   cadence", see engine/decisions.md "Learning/POM/Insight Engine:
   manual-only cadence confirmed"): Learning stays `workflow_dispatch`-
   only, same as Insight Engine and POM — the founder confirmed this is
   a deliberate standing choice, not a gap, mirroring
   `backup-database.yml`'s own precedent.
5. **Backlog #269 — RESOLVED 2026-07-19** (see engine/decisions.md
   "Learning/POM: surface computed_at staleness signal"): `GET
   /patterns` now includes each pattern's `computed_at` --
   `learned_patterns` has stored this column since the table was first
   created, but `get_learned_patterns` never selected/returned it until
   now. `BehavioralPatterns.svelte` shows a "Last updated" line sourced
   from it (one computation run per account, so one shared line for the
   whole card, not per-pattern).
6. **Backlog #270 — RESOLVED 2026-07-19**: `LearnedPatternOut`'s and
   `GET /patterns`' own docstrings both claimed this was "not yet
   rendered in the frontend" — stale since #214 actually shipped
   `BehavioralPatterns.svelte`. Both docstrings (`src/api/schema.py`,
   `src/api/server.py`) now say so correctly.

## Verification

`tests/test_learning.py` (5 tests) covers `compute_behavioral_patterns`
directly: floor-respecting silence below `MIN_EVIDENCE`, correct
grouping by `(event_type, new_status)`, correct subject wording
(goals vs decisions). No live-dispatch verification has ever actually been run for the full
offline pipeline end to end (`diff_behavioral_events` -> `save_events`
-> `scripts/run_learning.py` -> `GET /patterns`) — `.github/workflows/
learning-walkthrough.yml` exists and was confirmed locally to run
end-to-end without crashing (correctly hitting the honest-failure path
with no `OPENROUTER_API_KEY` set), but per engine/decisions.md the real
`workflow_dispatch` run against a live LLM provider was never
triggered. This remains open regardless of what the rest of this
sequencing section resolves to.

**Gap closed, dispatch still pending (2026-07-19):** until now, no
workflow existed that could run `scripts/run_learning.py` against real
production data at all — `pom-computation.yml` and
`learning-walkthrough.yml` both only ever touched an ephemeral GitHub
Actions runner's own local SQLite file, with no network path to
Fly.io's persistent volume. `.github/workflows/learning-computation.yml`
now runs `scripts/run_learning.py` for real inside the live,
already-deployed `confidantsense` container via `flyctl ssh console`
(same pattern as `backfill-knowledge-item-ids.yml`); `pom-computation.yml`
was fixed the same way (see engine/decisions.md "Learning + POM
computation workflows fixed to reach real production data"). Neither
workflow has actually been dispatched against production yet — that is
a separate, deliberate action requiring its own explicit go-ahead each
time, consistent with this project's standing discipline around
production-touching dispatches.
