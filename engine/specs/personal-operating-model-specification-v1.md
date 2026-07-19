# Personal Operating Model (POM) v1 — Specification

**Status: IMPLEMENTED, live via offline computation, read on every
turn.** Written retroactively (2026-07-19, backlog #217) to give POM
the same versioned-spec treatment every other mature component already
has.

## What POM is, and what it isn't

POM is the vision doc's Layer 4 (`engine/specs/architecture-roadmap-v1.md`).
Of the vision's nine POM systems, one (Behavioral Pattern System)
already shipped as Layer 2 Learning (`src/learning/engine.py`) —
`src/pom/` covers the other eight: Belief, Relationship, Identity,
Motivation, Learning Style, Stress, Narrative, Theory of Mind.

**Explicit, load-bearing caveat**: the founder's original vision
documents describing these eight systems are not present in this
repository — they were shared as uploaded context earlier in this
project's history, never committed. The Motivation and Narrative
systems below therefore use the STANDARD, textbook formulations of two
named frameworks (Self-Determination Theory's autonomy/competence/
relatedness — Deci & Ryan; Narrative Identity Theory's redemption/
contamination sequences — McAdams), not necessarily the founder's own
specific operationalization. This is flagged in the schema's own
docstring and in `engine/decisions.md`, not silently assumed correct.

**Scope was a deliberate, overridden default.** This project's own
default caution recommended building only Belief + Relationship first
— the two systems that reduce to existing structured WorldState data
with no invented scoring. The founder explicitly chose to build all
eight at once anyway (see `engine/decisions.md` "Personal Operating
Model"). Six of the eight genuinely require inventing a scored/
interpreted model with no evidence yet to calibrate it against — that
risk is accepted here, explicitly, at the founder's own direction, not
discovered later as an oversight.

## Mechanical vs. LLM-inferred split

Same discipline as everywhere else in this codebase: never invent a
mechanism where a cheaper, already-trusted one exists.

**Mechanical (`src/pom/engine.py`, no LLM call, pure aggregation):**
- `compute_belief_system` — order-preserving deduplicated Claims +
  Assumptions content, verbatim, across every session this account
  owns. A restatement, not a new interpretation.
- `compute_relationship_system` — verbatim Entity descriptions across
  every session, using the same `_render_entity_text` rendering as
  `src/understanding/engine.py` (duplicated, not imported — this
  codebase's established "small utility functions deliberately
  duplicated across engine packages" convention). An Entity with no
  attributes or relationships is skipped, same "a bare mention adds
  nothing a Fact doesn't already say" reasoning as Understanding's own
  Tier 1 render loop.

**LLM-inferred (`run_inferred_pom`, ONE call, ONE schema
`InferredPOMBatch`)** — same "one call, no hybrid complexity"
discipline as Judgment/Planner/Insight Engine, not six separate calls
for six separate fields: Identity, Motivation, Learning Style, Stress,
Narrative, Theory of Mind.

Every LLM-inferred field uses a coarse, closed scale
(`ConfidenceLevel = "low"/"moderate"/"high"/"unclear"`) rather than a
float — a numeric score would imply a precision this data cannot
support, since nothing here has been calibrated against ground truth
the way Judgment's confidence field at least has some real usage
behind it. Every field carries its own free-text `evidence` list, same
discipline as Judgment's `supporting_evidence` / Insight's
`evidence_session_ids` — never trust a score without being able to see
what it was based on.

## Engine-level grounding enforcement

`_ground_batch` never trusts the model's own evidence strings
uncritically — mirrors `src/insight/engine.py`'s id-based filtering,
adapted to free text since POM evidence is prose, not an id: each
evidence string is checked for real word overlap (`_is_evidence_grounded`,
a duplicated utility, same category as
`src/interpretation/engine.py`'s `_word_overlap`/`_is_option_grounded`)
against the aggregated content actually sent. A field whose evidence is
entirely stripped this way is downgraded — `motivation`/`stress` scale
values fall back to `"unclear"`, `narrative.arc` to `"unclear"` with
`summary` cleared, `identity.self_concept`/`learning_style.style`
emptied, and a `TheoryOfMindEntry` with zero surviving evidence is
dropped from the list entirely — rather than left asserting something
ungrounded.

## Offline computation and per-account scoping

`scripts/run_pom_computation.py` runs OFFLINE ONLY (workflow_dispatch
or manual), never inside a live request — same "operates
asynchronously, never inside a live conversation turn" boundary
Learning and Insight Engine already established. Nothing in
`src/api/server.py` computes POM; it only reads whatever was last
computed offline.

**Made per-user 2026-07-18** (`engine/decisions.md` "POM made
per-user"): `src/api/db.py::get_aggregated_knowledge_for_pom(user_id)`
reads every session owned by ONE account — uncapped within that scope
(POM is a single-person, all-history profile, not a recency-capped
sample), but no longer aggregated across every account the way it
originally was. An anonymous-owned session (never claimed via login)
is correctly excluded. `replace_personal_operating_model` truncates and
replaces per account (upsert keyed on `user_id`) — POM is one standing
profile per person, not an accumulating log, same "latest wins"
precedent as `learned_patterns`.

`GET /personal-operating-model` (gated behind login, `require_user`)
returns `db.get_personal_operating_model(user_id)` directly — `None`
until the offline script has computed this account's own POM at least
once, a correct "nothing yet" state for a brand-new account, never
another account's data.

## Where POM is consumed

1. **Retrieval** (`src/retrieval/engine.py::_render_pom_lines`) — a
   compact, top-level-only summary (beliefs, relationships, identity
   self-concept, SDT motivation levels, learning style, stress level,
   narrative arc, theory-of-mind entries) folded into Judgment's
   "Retrieved Context," never the underlying evidence quotes (see
   `engine/specs/retrieval-specification-v1.md`). A field left at its
   `"unclear"`/empty default is omitted entirely.
2. **Frontend** — `PersonalOperatingModel.svelte`, surfaced in
   Settings, reads the same `GET /personal-operating-model` response
   directly for a person to see their own standing profile.
3. **Mode-specific early seeding** (`engine/decisions.md` "POM early
   seeding via mode design") — later rounds used POM to target which
   system a mode's opening prompt nudges toward, thinnest-system-aware.

## Non-goals

No live/in-turn computation — POM only ever reflects the last
`workflow_dispatch` run, not this exact conversation. No numeric/float
scoring for the LLM-inferred systems (see "coarse, closed scale"
above). No claim that the Motivation/Narrative operationalizations
match the founder's original, uncommitted vision documents exactly —
see the caveat above.

## Open questions

1. **Backlog #207–#210**: several POM-adjacent increments remain
   unbuilt — an opt-in Journey-close reflection question, drawing
   Motivation/competence from existing `behavioral_events` rather than
   solely from the LLM inference, a light affirm/correct affordance on
   the frontend's You surface, and Insight-triggered conversational
   callbacks. None of these are required for POM v1 to function; they
   were deferred as distinct, separately-scoped increments.
2. **Backlog #272**: now that POM is per-account (closing the original
   cross-account leak), whether uncapped all-history aggregation
   remains the right choice as any single account's history grows is
   still an open question — not resolved by this doc.
3. **The Motivation/Narrative textbook-vs-founder's-own-formulation
   gap** (see the caveat above) has never been resolved with the
   founder directly — this spec documents the current, standard-theory
   implementation, not a confirmed match to original intent.

## Verification

Covered by `tests/test_pom_schema.py` (schema defaults/validation),
`tests/test_pom_engine.py` (mechanical systems' dedup/skip behavior,
`_ground_batch`'s downgrade-on-ungrounded-evidence logic, provider
fallback and error handling in `run_inferred_pom`), and
`tests/test_pom_aggregation.py` (`get_aggregated_knowledge_for_pom`'s
per-account scoping and content rendering). No dedicated live-dispatch
calibration round has been run specifically for the six LLM-inferred
systems' output quality.
