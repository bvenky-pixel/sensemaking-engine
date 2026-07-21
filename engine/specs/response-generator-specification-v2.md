# Response Generator v2/v3 — Specification

**Status: IMPLEMENTED, current production behavior.** Written
retroactively (2026-07-19, backlog #216) as a versioned update to
`engine/specs/response-generator-specification-v1.md`, which is
pre-implementation and philosophical — it describes the Core Principle,
Inputs, Responsibilities, and Non-Goals as originally designed, and
those still hold. It predates every round below and was never updated
to reflect them; this doc is the retroactive correction, not a
replacement — read v1 first for the unchanged design philosophy, then
this doc for what actually shipped on top of it.

## What v1 got right, and what's changed since

v1's Core Principle (Faithful Execution — never reinterpret,
reprioritize, introduce new reasoning, or override Planner's intent)
and Grounding law are unchanged and still enforced. What v1's `Output`
section doesn't reflect: `Response` (`src/response/schema.py`) has
grown from `{response_text, confidence}` to
`{response_text, confidence, options: list[ResponseOption]}`, and the
engine now receives `mode`/`pom` parameters v1 never anticipated. None
of this is new cognition — every addition below is Structure/Expression
work the v1 spec already grants Response, not a scope expansion.

## `response_text` hard-fails on empty/whitespace, not just missing

Found via a live Ollama/llama3.2:3b dispatch: the model returned an
empty string and it passed schema validation silently, even though an
empty response is a hard failure for this layer specifically — unlike
every upstream layer, where an empty list/string is often the CORRECT
sparse answer, `response_text` is the one artifact the user actually
sees. A `mode="after"` field validator rejects `""` and whitespace-only
values (not just `Field(min_length=1)`, which wouldn't catch `"   "`) —
same "empty is as useless as missing" principle already enforced at the
provider level in `src/llm/providers.py::_extract_message_content`.

## Response v2 Priority 1 (2026-07-11) — three prompt-only fixes

The third and final stage of a pipeline-wide depth-parity pass
(Interpretation → Planner → Response), driven by grepping all 30
`Response quality` scored rows in
`experiments/confidant-validation/log.md`. Response scored notably
higher (mostly 6-9) than Interpretation/Planner had before their own
rounds — several apparent "defects" in the log were actually upstream
Planner/Judgment gaps Response was correctly, faithfully mirroring
(fixing those at the Response layer would have violated the v1 Core
Principle), and were excluded from scope. Three real, Response-owned
defects remained, all fixed in `src/response/prompt.py` only — no
schema or engine change:

1. **Inconsistent pacing under "avoid overwhelming the user."** The
   prior guidance was scoped narrowly to the word "open_unknown" and
   read as being about the unknowns list specifically, not how many
   `questions_to_explore` items to actually voice. Broadened to
   explicitly cover `questions_to_explore`/`priority_topics`, with a
   concrete rule of thumb (at most one, or at most two closely related,
   questions per turn under this constraint).
2. **Missing brief emotional acknowledgment before pivoting to
   fact-finding.** A stress-test pass caught the original fix draft
   pointing at a field that doesn't exist on WorldState
   (`emotional_signals` — that's Interpretation's schema field, never
   carried into WorldState by `src/state/builder.py`; Response never
   sees Interpretation at all). Reworded before shipping to trigger off
   content Response actually receives: WorldState's
   `facts`/`claims`/`surface_complaint`, or Judgment's
   `primary_problem`/`current_focus`. Capped at one sentence, additive
   to (not a replacement for) fix #1's question budget — guarding
   against an emotionally-significant AND overwhelm-constrained turn
   becoming all-acknowledgment/no-progress.
3. **Advice-flavored closing lines drifting outside Planner's actual
   `conversational_strategy`.** Added closing-register discipline: a
   response's closing must stay within Planner's own strategy, with a
   worked BAD/GOOD example.

Verified via a live `single-turn-smoketest.yml` re-test dispatch
(pinned `openai/gpt-4o-mini`) plus the full suite; two of three fixes
showed direct, on-target evidence of working, the third (pacing)
couldn't be cleanly re-verified because the specific Planner constraint
it targets didn't reproduce in the re-test dispatches — an honest gap,
not a negative result.

## Response v3 — compact structure, then real choice buttons (2026-07-11)

Direct user complaint against a live reply: three declarative
observations stacked into one turn, zero question marks anywhere. Two
rounds, same day, because round 1's fix wasn't actually what the user
had asked for.

**Round 1 — compact structure.** v2's pacing rules only capped how many
QUESTIONS a response could ask, and only under an explicit
"avoid overwhelming the user" constraint — they never capped plain
declarative/suggestion sentences, and never applied by default.
Replaced the old "organize using whatever structure fits the strategy"
freedom with one fixed shape, unconditional every turn: exactly one
grounding sentence, then exactly one question. No schema change.

**User pushback and correction.** The user asked directly whether their
request for choice options had been ignored. Round 1's soft
"prose may name 2-3 options" idea wasn't what they'd described — "give
the user a couple of choices to choose from... like you do right now"
was pointing at a real UI affordance (tappable options + free text
still available), not wording inside a sentence. Asked directly which
was wanted: real clickable options, unambiguously.

**Round 2 — real choice buttons.** `Response.options: list[str]`
(later widened, see round 3), default empty, max 3, no blank entries —
fails loud rather than silently truncating, same principle as
`response_text`'s own empty-string validator. Populated ONLY when
WorldState/Judgment/Planner already name a small, concrete,
mutually-exclusive set (e.g. `decision_options`) — same Grounding law
as everything else in this layer, never invented to fill the list. The
question sentence itself stays neutral/open — it no longer re-lists
option names in prose, which would duplicate the buttons.
`src/api/db.py` gained a `messages.options_json` column so a page
reload still shows the same buttons; `Transcript.svelte` renders each
option as a real button under the LAST message only (disabled mid-turn,
gone once a further message exists), routed through the same
`onSend`/`handleSend` path the composer's own send button uses — a
shortcut into the existing free-text flow, never a separate mechanism.

Verified three ways: unit/schema tests, a live Playwright pass (mocked
LLM, real button render/click/disappear cycle), and a live 10+-turn
`worldstate-walkthrough.yml` dispatch against the actual production
model (`openai/gpt-4o-mini`) — 11/11 turns produced exactly the
2-sentence compact shape, 10/11 exactly one question mark, and the one
exception correctly produced zero question marks with a declarative
closing because Planner had set `"no direct questions in the response"`
that turn — the intended fallback, not a miss.

**Round 3 — option reasoning (same day).** Direct follow-up: "write a
short description or reasoning behind each choice." Widened each bare
`str` option into `ResponseOption {label, description}`
(`src/response/schema.py`). `label` is unchanged in spirit — the button
text, and exactly what's sent as the person's reply if tapped.
`description` is new: 1-2 sentences of grounded reasoning for WHY the
option might apply, shown alongside the button, never itself sent
anywhere — same Grounding law as everything else in this layer,
restating only content already present in WorldState/Judgment/Planner
(the prompt's own BAD example: inventing "...could cause you
significant stress" when nothing upstream said so). Threaded end to
end through `ResponseOptionOut` (`src/api/schema.py`) and
`options_json` (same column, now storing `{label, description}` dicts)
to `Transcript.svelte`, restructured from a chip row into full-width
cards (bold label, muted description) — still firing
`onOptionSelect(option.label)` only.

## Mode-aware expression: `response_mode_focus_note`

`run_response_generator` takes an optional `mode` (Counseling mode id)
and resolves it to prompt-injection text via
`src/orchestrator/modes.py::response_mode_focus_note`, alongside
`state.turn_count` (Realign's rotation is precomputed in Python, not
left to the model to compute `turn_count % 5` itself) and `pom` (used
only to decide whether that mode's POM-seeding clause should fire this
turn — see `engine/specs/personal-operating-model-specification-v1.md`).

**Adaptive mode / Synthesis**: when the session's mode is `"adaptive"`,
`RESPONSE_MODE_FOCUS` has no separate `"adaptive"` entry — Planner
itself chooses which of the five concrete lenses fits THIS TURN
(`plan.active_lens`), and Orchestrator resolves `effective_mode` from
that before calling Response (see
`engine/specs/orchestrator-specification-v1.md`), so Response is always
given a concrete lens's already-tuned focus text, never the literal
string `"adaptive"`.

## Per-component model pinning

Response is one of the components covered by the per-component model
map in `src/llm/providers.py` (2026-07-18) — given a cheaper model in
the primary/fallback chain than components doing heavier
assessment/reasoning, since Response's job (expression, not judgment)
tolerates a lighter model better. `TEMPERATURE=0.7` (vs. Judgment/
Planner's 0.15) is unchanged since v1 — expression benefits from more
variation than analytical reasoning does; still an unvalidated first
guess, not recalibrated by any of the rounds above.

## Non-goals

Unchanged from v1: no reasoning, no WorldState/Judgment/Planner
mutation, no new motivations or evidence invented to justify an
expression choice. `options` staying empty is the common, correct case
— free text is always available regardless of whether options are
offered.

## Open questions

**Backlog #223 — RESOLVED 2026-07-21** (see engine/decisions.md
"Planner/Response calibration: 3/3 scored, first case-ID-tracked round
for either stage"): `scripts/run_planner_response_calibration.py`
(cases PR01-PR05) dispatched against production's actual model chain --
3/3 scored cases hit (response-style-constraint translation, User
Agency on an already-made decision, overwhelm pacing), plus two clean
observation-only reads (emotional acknowledgment fired correctly; one
mild over-fitting signal on a mundane negative control worth watching,
not acted on from a single data point). First structured, case-ID-
tracked round either stage has had.

## Verification

Covered by `tests/test_response_schema.py` (empty/whitespace rejection,
`options` bounds and blank-entry rejection across both the bare-`str`
and `ResponseOption` shapes), `tests/test_response_engine.py`,
`tests/test_api_server.py` (options threading through `send_message`
and persisting across a reload), and `Transcript.test.js` (button
render/click/disappear behavior, both chip-row and card-layout eras).
Live-dispatch verification exists for the v3 compact-structure rule
(11-turn `worldstate-walkthrough.yml` run against production's actual
model) and for the button/card UI via Playwright — v2 Priority 1's
pacing fix specifically was never cleanly re-verified live (see that
section above).
