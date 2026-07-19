# Insight Engine v1 — Specification

**Status: IMPLEMENTED, offline-only computation, read on every turn and
surfaced in the frontend.** Written retroactively (2026-07-19, backlog
#220) to give Insight Engine the same versioned-spec treatment every
other mature component already has. Reflects the #273 per-account fix,
not the original cross-account design.

## What Insight Engine is, and what it isn't

Insight Engine answers one question: *do a person's separate sessions
describe a recurring pattern?* — the semantic-clustering piece
Learning Phase 1's own docstring (`src/learning/engine.py`) named as
needing infrastructure that didn't exist yet. Unlike Learning Phase 1's
mechanical, non-LLM behavioral-event counting within one session, this
genuinely needs an LLM call for real language understanding across
differently-worded sessions — detecting that "waiting on my manager's
approval" and "stuck until my co-founder decides" describe the same
underlying pattern is language understanding, not counting.

`src/insight/engine.py::run_insight_detection` is OFFLINE ONLY
(`scripts/run_insight_detection.py`), never inside a live request —
same "operates asynchronously, never inside a live conversation turn"
boundary Learning already established. Nothing in `src/api/server.py`
calls it directly.

## One call, one schema, engine-level grounding enforcement

Same "one call, no hybrid complexity" discipline as every other
LLM-calling stage (Interpretation/Judgment/Planner/Response/POM).
`InsightBatch` (`src/insight/schema.py`) wraps a list of `Insight`
objects (`theme`, `detail`, `evidence_session_ids`).

`_enforce_grounding` never trusts the model's own
`evidence_session_ids` uncritically — mirrors
`src/interpretation/engine.py`'s own code-level grounding filters:
after the call, every Insight's evidence ids are filtered down to the
intersection with session ids actually sent in the prompt, and any
Insight whose surviving evidence count falls below
`MIN_EVIDENCE_SESSIONS` (2 — lower than Learning Phase 1's
`MIN_EVIDENCE=3` because sessions are few and rich, one real
conversation each, rather than many and small individual behavioral
events) is dropped entirely. A hallucinated or duplicated session id
must not let a genuinely under-evidenced theme slip through.
`run_insight_detection` also short-circuits before spending an LLM call
at all when fewer than `MIN_EVIDENCE_SESSIONS` sessions are available —
structurally no way to ground a recurring theme in fewer.

`MAX_SESSIONS_FOR_INSIGHT` (30) caps how many sessions' worth of text
get sent in one prompt as session count grows — most-recently-updated
sessions win. Both constants are explicit, honest first guesses, not
empirically tuned (see "Open questions" below).

## Per-account scoping (the #273 fix)

**Originally computed one cross-account aggregate** — before backlog
#273, `get_session_texts_for_insights` read the most-recently-updated
sessions across every account on the server, unscoped, and
`send_message` then injected that shared result into every live
conversation regardless of who was asking. This was closed alongside
#257 (Learning made per-account) but #273 tracked the fact that
Insight Engine specifically had NOT yet been fixed when #257 landed.

**Fixed 2026-07-19**: `get_session_texts_for_insights(user_id)` now
reads THIS account's own sessions only, capped at
`MAX_SESSIONS_FOR_INSIGHT` most-recently-updated. This closed a second,
non-privacy bug at the same time: on a server with several active
accounts, another account's more-recent activity could crowd this
account's own sessions out of the window entirely, occasionally leaving
an account with real history seeing zero of its own sessions
considered. `replace_insights(user_id, ...)` truncates and replaces
THIS account's own share of `insights`/`insight_sessions` only (mirrors
`replace_learned_patterns`'s precedent), not a global truncate.
`get_insights(user_id)` returns only this account's own rows. Every
per-account offline job in this codebase (Learning, POM, Insight
Engine) now follows the same discipline.

## Where Insight Engine is consumed

Two distinct surfaces, not one:

1. **Retrieval** (`src/retrieval/engine.py`) — `insights` folded into
   Judgment's "Retrieved Context" alongside Learning's patterns,
   rendered verbatim (`- {theme}: {detail}`), unfiltered (see
   `engine/specs/retrieval-specification-v1.md`).
2. **`GET /insights`** (`src/api/server.py`, login-gated via
   `require_user`) — returns this account's own `InsightOut` list
   directly for any frontend surface that wants the raw list.
3. **`list_sessions`'s per-session `insight_theme`/`insight_detail`**
   (`src/api/db.py`) — a deliberate deviation from the
   boolean-only-flag precedent `has_stagnation_signal` set: a session
   that's evidence for a real Insight gets that Insight's actual theme
   text surfaced directly on its Home-screen summary row
   (`session.insight_detail`, rendered by `Home.svelte` as "This has
   come up before, too. {insight_detail}"). If a session ever evidences
   more than one Insight, the most-recently-computed one wins — a
   documented simplification, not a silent one.

## Non-goals

No live/in-turn computation — Insight Engine only ever reflects the
last `workflow_dispatch` run. No cross-account aggregation of any kind
post-#273. No semantic deduplication of themes across separate
`run_insight_detection` runs — each run still replaces an account's
insights wholesale rather than merging with the previous run's themes
(backlog #293; see Open Questions below for what's shipped vs. still
proposed).

## Open questions

**Backlog #249** ("Insight Engine: calibrate its uncalibrated
thresholds") tracks `MIN_EVIDENCE_SESSIONS`/`MAX_SESSIONS_FOR_INSIGHT`
— both explicit first guesses, never validated against real production
theme-detection quality. **Backlog #268 — CONFIRMED 2026-07-19** ("no
recurring computation cadence", see engine/decisions.md "Learning/POM/
Insight Engine: manual-only cadence confirmed") applies here too:
Insight Engine has no scheduled recompute, only `workflow_dispatch` --
the founder was asked directly and confirmed this stays a deliberate
choice, not an oversight, same "workflow_dispatch-only, no cron"
precedent `backup-database.yml` already established.

**Backlog #293** ("dedupe/merge themes across successive computation
runs") -- two-part, 2026-07-19:
1. **Narrow fix, SHIPPED** (see engine/decisions.md "Insight Engine:
   keep re-offering existing evidence sessions across runs"):
   `get_session_texts_for_insights` (`src/api/db.py`) now always
   includes any session that's currently evidence for an existing
   Insight, even if it's aged out of the plain top-`MAX_SESSIONS_FOR_INSIGHT`
   recency window -- stops a still-true Insight from being deleted by
   the next run purely because its evidence session rotated out of
   scope, with no merge/dedup decision involved.
2. **Deeper merge/dedup logic, PROPOSED not built**: a discussion-draft
   design (see `engine/specs/insight-dedup-design-proposal.md`) for
   feeding an account's existing Insights back into the same
   `run_insight_detection` call as context, so the model itself decides
   whether a new theme is the same underlying pattern as an existing
   one (and reuses its wording) rather than each run being wholly
   independent. Not yet approved or implemented -- recommended to ship
   and observe against real successive `workflow_dispatch` runs before
   deciding whether a mechanical fallback matcher is also needed.

## Verification

Covered by `tests/test_insight.py` (grounding enforcement dropping
under-evidenced Insights, the sub-`MIN_EVIDENCE_SESSIONS` short-circuit,
provider fallback/error handling) and the per-account scoping tests
added for #273 (`get_session_texts_for_insights`/`replace_insights`/
`get_insights` each scoped correctly, `list_sessions`'s
`insight_theme`/`insight_detail` join). No dedicated live-dispatch
calibration round has been run specifically for cross-session theme
detection quality.
