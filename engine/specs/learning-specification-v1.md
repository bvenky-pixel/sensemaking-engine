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

These three items were previously scattered across
`src/instrumentation/events.py`'s docstring, `frontend/specs/
trust-and-privacy-ux-v1.md`'s Principle 6, and backlog #257. Written
together here because they form one real dependency chain, not three
independent nice-to-haves:

1. **No per-account scoping.** `get_all_events()`'s own docstring
   admits "single-user scope, no user_id column" — every account's
   behavioral events are aggregated together into one shared
   `learned_patterns` table with no way to attribute a row back to one
   account. This is the exact same class of bug already found and
   fixed for POM (`personal_operating_model` made per-user after a
   real cross-account leak, see engine/decisions.md "POM made
   per-user"). Today `reset_all_data(user_id)` deletes an account's
   own raw `behavioral_events`, but NOT their contribution to
   `learned_patterns` — once aggregated, a person's own evidence can
   no longer be separated back out. Surfacing "your patterns" to a
   real user while this is true would show them a blend of every
   account's behavior, not just their own — both misattributed and a
   real privacy leak once more than one real account exists.
2. **No frontend disclosure surface.** `frontend/specs/
   trust-and-privacy-ux-v1.md`'s Principle 6 requires, before real
   behavioral data should accumulate: patterns traceable to real,
   inspectable evidence (the `{statement, evidence, evidence_count}`
   shape already used elsewhere), and a way to see them at all.
   Nothing in the frontend surfaces `GET /patterns` today.
3. **No deletion path for `learned_patterns` independent of a full
   database wipe.** Principle 6 also requires a person be able to
   delete their own accumulated behavioral history — genuinely hard
   while (1) is unresolved, since there's nothing to selectively
   delete once evidence is aggregated without attribution.

**The real order, given these three are entangled**: (1) must be
resolved (or explicitly, knowingly accepted as a temporary risk at
today's real user scale) before (2) can honestly ship, and (2)+a real
deletion path must exist before `CONFIDANT_RECORD_EVENTS` should be
turned on in production (`src/instrumentation/events.py`'s own
docstring: "turning this on in production is a deliberate
product/privacy decision, not an engineering default"). Backlog #213
(calibrating `MIN_EVIDENCE` against real data) is blocked behind all
three, since it needs real accumulated production data to calibrate
against in the first place.

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
