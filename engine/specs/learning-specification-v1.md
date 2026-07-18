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

**The real order, now that (1) and (3) are resolved**: #214 (frontend
disclosure) can be built without the correctness gap this section
originally flagged. `CONFIDANT_RECORD_EVENTS` should still only be
turned on in production (#211) once #214 actually ships — a real
disclosure surface existing in code isn't the same as it being live for
real users to see (`src/instrumentation/events.py`'s own docstring:
"turning this on in production is a deliberate product/privacy
decision, not an engineering default"). Backlog #213 (calibrating
`MIN_EVIDENCE` against real data) is still blocked behind #211, since
it needs real accumulated production data to calibrate against in the
first place.

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
