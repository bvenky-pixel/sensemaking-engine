# Retrieval v1 — Specification

**Status: IMPLEMENTED, live in every turn.** Written retroactively
(2026-07-19, backlog #218) to give Retrieval the same versioned-spec
treatment every other mature component already has.

## What Retrieval is, and what it isn't

Retrieval is the vision doc's Layer 8 (`engine/specs/architecture-roadmap-v1.md`),
scoped deliberately narrow — it is explicitly **NOT** the vision doc's
own description of "need-aware selective retrieval" (Decision
Retrieval, Accountability Retrieval, Reflection Retrieval, each pulling
different context per the inferred need). That description depends on
Layer 7 (Need State Inference) doing real selective filtering; building
selective-retrieval logic ahead of real evidence for what "relevant"
means would mean inventing a relevance model with no evidence behind
it — the same mistake this codebase has refused to make everywhere
else (Learning's own `MIN_EVIDENCE` discipline, Planner's "resist
tuning until real samples exist").

**What it actually does**: surface everything Learning
(`src/learning/engine.py`) and Insight Engine (`src/insight/engine.py`)
have already, offline, evidence-gated computed about this person,
unfiltered. Correct at this project's current scale, where "everything
currently known" about one account is still a handful of short
entries. `src/retrieval/engine.py::build_retrieved_context` is a pure
formatting function — no I/O, no LLM call, same "mechanical, not a
call" category as `src/judgment/engine.py::compute_stagnation_signals`.
Callers (`src/api/server.py::send_message`) are responsible for
actually reading `db.get_learned_patterns`/`get_insights`/
`get_personal_operating_model` and calling
`src/need_state/engine.py::infer_need_state` themselves — this module
has no database or WorldState dependency of its own.

## What it feeds, and why

Retrieved Context feeds **Judgment only** (see
`src/judgment/prompt.py`'s "Retrieved Context" section) — the vision
doc's own pipeline places Judgment as the first layer downstream of
Retrieval, and Judgment already owns synthesizing "what's true"
(WorldState) into "what it means." Cross-session patterns/themes are
additional input to that synthesis, not a new pipeline stage with its
own independent reasoning.

## Four inputs, all optional, all label-only

`build_retrieved_context(patterns, insights, need_state=None, pom=None) -> str`:

1. **`patterns`** (`List[Pattern]`, from Learning) — rendered verbatim:
   `- [{pattern_type}] {detail} (evidence_count={evidence_count})`.
2. **`insights`** (`List[Insight]`, from Insight Engine) — rendered
   verbatim: `- {theme}: {detail}`.
3. **`need_state`** (`Optional[NeedState]`, added 2026-07-16 once Layer
   7 existed) — **LABEL-ONLY, not filtering**. Patterns/insights stay
   exactly as unfiltered as before Need State Inference existed; the
   inferred need is surfaced as an explicit, visible line
   (`_NEED_STATE_LABELS`: "an open decision genuinely being weighed",
   "a goal or decision that has stalled without a status change", "a
   goal exists to weigh the situation against, with no sharper signal
   yet") so Judgment can weigh the still-complete evidence knowing what
   this turn actually needs. The alternative considered and rejected:
   actually filtering patterns/insights by a text-relevance match
   against free-text `pattern_type`/`theme` fields — rejected as an
   unvalidated relevance model with no evidence behind it (see
   `engine/decisions.md`'s "Fork 2, effect on Retrieval" for the full
   fork). `need_state="general"` is treated the same as `None` — it
   conveys nothing actionable, so it never earns its own line.
4. **`pom`** (`Optional[PersonalOperatingModel]`, added 2026-07-16) —
   rendered by `_render_pom_lines` as a compact, top-level-only summary
   (beliefs, relationships, identity self-concept, SDT motivation
   levels, learning style, stress level, narrative arc, theory-of-mind
   entries) — never the underlying evidence quotes behind each POM
   field, which would bloat Judgment's prompt without adding anything
   actionable (POM's own grounding already lives in `src/pom/engine.py`).
   A field left at its `"unclear"`/empty default is omitted entirely,
   same "omit rather than show a hollow signal" discipline as
   everywhere else in this module.

**Empty-input contract**: no patterns, no insights, no meaningful
`need_label`, and no meaningful `pom_lines` together produce `""` — a
brand-new Journey, or an account with nothing learned yet, must not see
an empty-but-present "Retrieved Context" section in Judgment's prompt.

## Non-goals

No selective/relevance-based filtering of patterns or insights (see
above — deliberately deferred pending real evidence for what
"relevant" should mean). No caching or memoization — `send_message`
calls this fresh every turn, cheap since it's pure string formatting
over data already read from the DB. No LLM call of its own.

## Open questions

**Backlog #224** ("Retrieval: close the 'label-only, not filtering'
gap") tracks the still-open question this module's own docstring
raises but doesn't resolve: once Need State Inference (or some other
signal) has enough real evidence behind it, should Retrieval actually
start filtering patterns/insights by inferred need, rather than only
labeling them? Not resolved here — this spec documents the current,
deliberately-narrow shape, not a commitment to stay this way forever.

## Verification

Covered by `tests/test_retrieval.py` (empty-input contract, each of
the four inputs rendering independently and in combination,
`need_state="general"` treated as absent) and
`tests/test_api_server.py`'s retrieval-threading tests (confirming
`send_message` actually reads patterns/insights/POM from the DB and
passes them through to Judgment's prompt, not just that
`build_retrieved_context` formats correctly in isolation).
