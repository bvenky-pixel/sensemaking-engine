# Instrumentation v1 — Specification

**Status: IMPLEMENTED, three layers: in-memory tracking, offline
behavioral-event detection, and (as of #230) persisted production
observability.** Written retroactively (2026-07-19, backlog #227) to
give Instrumentation the same versioned-spec treatment every other
mature component already has.

## What Instrumentation is, and what it isn't

Instrumentation measures the pipeline; it never changes it. "It
observes; it does not evaluate or act" —
`engine/specs/system-architecture-v2-specification.md`'s own framing,
carried through every module here. Three genuinely separate pieces
share this package because they're all measurement, not because they
share a data model:

1. **`src/instrumentation/usage.py`** — per-call token/cost/latency
   measurement and per-attempt structured-output reliability, in
   memory, for one run.
2. **`src/instrumentation/events.py`** — diff-based behavioral event
   detection (Learning Phase 1's data source).
3. **`src/instrumentation/pricing.py` / `frontier_pricing.py`** —
   two unrelated cost tables, easy to conflate but answering different
   questions (see below).
4. **The #230 persistence layer** (`src/api/db.py`'s
   `llm_usage_records`/`llm_attempt_records`) — the "beyond opt-in
   UsageTracker" extension that makes usage/reliability data survive
   past one in-memory run.

## `UsageTracker` / `LLMUsage` / `AttemptRecord`

**Off by default.** `is_tracking_enabled()` gates on
`CONFIDANT_TRACK_USAGE` — when unset, `UsageTracker.record`/
`record_outcome` are no-ops, zero behavioral footprint outside
evaluation runs or production observability, per explicit constraint.

**`LLMUsage`** — one record per successful call that actually returned
content. Fields cover the full set providers can expose
(prompt/completion/reasoning/cached tokens), normalized via
provider-specific `extract_*_usage` functions (`extract_openai_compatible_usage`
covers OpenRouter and OpenAI's shared shape; `extract_anthropic_usage`
is provided ahead of an actual Anthropic adapter, not currently wired
into any provider chain). `reasoning_tokens`/`cached_tokens` are `None`
when a provider genuinely doesn't expose them — NEVER estimated or
defaulted to 0, since 0 would falsely claim "confirmed zero" where the
truth is "unknown." The provider's raw usage object is preserved
verbatim in `raw_usage` so a future provider, or a new field an
existing one starts exposing, never requires another instrumentation
redesign.

**`AttemptRecord`** — fills a gap `LLMUsage` structurally can't:
`LLMUsage` says nothing about whether returned content went on to parse
as JSON or validate against the target schema. Every `engine.py`
records one `AttemptRecord` per provider attempt
(`success`/`provider_call_error`/`invalid_json`/`schema_validation_failed`)
at the same decision points it already has — purely additive, recording
an outcome never changes which provider is tried next or what gets
returned/raised. `model` is always `None` on an `AttemptRecord` — the
`resolve_provider_chain()` loop only knows `provider`; the resolved
model string is internal to `call_openrouter` and never returned to the
caller. Same None-honesty rule as `reasoning_tokens`/`cached_tokens`.

`UsageTracker.summary()` returns a plain dict (not printed text) so
programmatic aggregation is possible without parsing console output —
`.reliability` (built from `outcomes`) is deliberately not reconciled
against `.records`' length, since an `AttemptRecord` exists for every
provider attempt regardless of whether it produced a usable `LLMUsage`.
`print_turn_summary` is the human-readable console form, used by
`conversation_runner.py` and the walkthrough scripts.

## Two unrelated cost tables — do not conflate

- **`pricing.py::estimate_cost_usd`** — what a call ACTUALLY cost, on
  its real provider/model. Manually-maintained snapshot, explicitly
  flagged as going stale; an unlisted, non-`:free` model returns `None`
  (unknown cost), never a guessed number. `:free`-suffixed and
  `openrouter/free` OpenRouter models are verified `$0.00`, confirmed
  against OpenRouter's own docs, not assumed.
- **`frontier_pricing.py::estimate_frontier_costs_usd`** — a
  calculated COMPARISON, not a real cost: what the SAME token counts
  would have cost on a fixed set of frontier reference models
  (Fable 5, Opus 4.8, Sonnet 5, Haiku 4.5), regardless of which
  provider actually served the call. Always fully populated (the
  reference table is fixed), unlike `estimate_cost_usd`'s honest
  "unknown" case.

## Behavioral events (`events.py`) — diff-based, not recorder-threaded

Feeds Learning Phase 1. An earlier design threaded an `EventRecorder`
through `src/state/builder.py`'s mutation functions, mirroring
`UsageTracker`'s inline-recording pattern — a plan review caught a real
correctness bug: several builder functions assign `.status`
unconditionally whenever a matching update appears, never checking
whether the new status differs from the old one, and Interpretation is
stateless per turn (a Decision the user is still deferring can
plausibly re-emit the same event turn after turn). Recording at the
mutation line as originally designed would have recorded N events for
one real transition, inflating exactly the evidence a `MIN_EVIDENCE`
floor is supposed to protect against.

`diff_behavioral_events(old_state, new_state, session_id, turn)` is a
pure function, no side effects — compares old/new Goals/Decisions by a
content-key match (`content.strip().lower()`, the same dedup key
`_merge_content_items` uses elsewhere, valid because content itself is
never mutated in place for an existing item), emitting an event only
where a matched item's status actually differs. An item present only in
`new_state` (freshly created this turn) has no old counterpart and is
correctly skipped — creation is not a status transition.

`is_events_enabled()` gates `CONFIDANT_RECORD_EVENTS`, checked at the
persistence boundary (`src/api/db.py::save_events`), not inside
`diff_behavioral_events` itself, which stays a pure function with no
environment dependency. Off everywhere, including production, until
`trust-and-privacy-ux-v1.md` Principle 6 was genuinely satisfied
(real per-account attribution, a real frontend disclosure surface, a
real deletion path) — turned on in production 2026-07-18 as a
deliberate product/privacy decision, not an engineering default.

## Production observability beyond opt-in UsageTracker (#230)

`UsageTracker` is fresh and in-memory per request — without a
persistence layer, seeing the pipeline's aggregate health/cost across
every turn meant either re-deriving from raw per-session `debug_json`
blobs one at a time, or SSHing in and querying the DB by hand.

`fly.toml` sets `CONFIDANT_TRACK_USAGE=1` in production. After
`run_turn` completes, `send_message` calls
`db.record_llm_usage`/`record_llm_attempt` once per record the turn's
`tracker` accumulated — a second, independent write, not a replacement
for the in-memory tracker (which still feeds that turn's own
`debug_json` for per-session inspection). **Deliberately given no
privacy-prerequisite gate** the way `CONFIDANT_RECORD_EVENTS` needed:
`LLMUsage`/`AttemptRecord` contain component/provider/model/token
counts/latency/cost/outcome — zero raw message content — so there is
nothing here for Principle 6 to apply to. `get_llm_usage_records`/
`get_llm_attempt_records` are correspondingly NOT scoped to one
account — this is operational telemetry about the system's own
health/cost, not personal data belonging to any one person.

`scripts/usage_report.py` (workflow_dispatch via
`.github/workflows/usage-report.yml`) reads both tables and prints,
per component: call count, success rate (from attempt outcomes),
P50/P95 latency, and total estimated cost — the "beyond" in the
backlog's own title.

## Non-goals

Instrumentation never changes provider selection, retry behavior, or
what gets returned to a caller — a try/except around every recording
step ensures an instrumentation failure can never break the actual LLM
call. No cross-account scoping on the #230 persistence tables (see
above — deliberate, not an oversight). No unification with
`src/evaluation/`'s own metrics machinery.

## Open questions

**Backlog #251** ("Instrumentation: unify with src/evaluation/
metrics") tracks a real, still-open overlap: `src/evaluation/` has its
own metrics/scoring machinery for calibration rounds, built
independently of this package's reliability/cost tracking. Not resolved
here.

**Backlog #294** tracks routine upkeep both cost tables' own docstrings
already call out: `pricing.py`/`frontier_pricing.py` are manually-
maintained snapshots that will go stale, and neither has a scheduled
re-verification cadence against OpenRouter's/Anthropic's current
pricing pages.

## Verification

Covered by `tests/test_instrumentation.py` (usage/outcome recording,
`UsageTracker.summary()`'s aggregation math, the None-honesty rules for
optional token fields, `diff_behavioral_events`'s content-key matching
and the created-vs-transitioned distinction), `tests/test_usage_persistence.py`
(the #230 DB round-trip for both tables), and `tests/test_usage_report.py`
(the report's percentile/formatting logic). `tests/test_api_server.py`
has a dedicated test confirming `send_message` persists
`AttemptRecord`s when `CONFIDANT_TRACK_USAGE` is enabled and persists
nothing when it isn't — `llm_usage_records` isn't asserted there, since
the mocked-provider pattern those tests use bypasses
`src/llm/providers.py::call_provider`, where `tracker.record(LLMUsage(...))`
actually lives.
