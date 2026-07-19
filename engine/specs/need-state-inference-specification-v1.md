# Need State Inference v1 — Specification

**Status: IMPLEMENTED, live in every turn, feeds Retrieval only.**
Written retroactively (2026-07-19, backlog #219) to give Need State
Inference the same versioned-spec treatment every other mature
component already has.

## What Need State Inference is, and what it isn't

Need State Inference is the vision doc's Layer 7
(`engine/specs/architecture-roadmap-v1.md`). It must run BEFORE
Retrieval, which feeds Judgment — unlike Synthesis's `active_lens`
(chosen inside Planner's own call, which runs AFTER Retrieval/Judgment),
there is no existing LLM call already happening at the right point in
the pipeline to fold this into for free.

`src/need_state/schema.py::NeedState` is a small, closed
`Literal["decision", "accountability", "reflection", "general"]` — only
the three need categories the founder's vision doc actually names in
its Retrieval discussion ("Decision Retrieval, Accountability
Retrieval, Reflection Retrieval"), not an invented larger taxonomy,
plus a `"general"` fallback for when nothing more specific fires. This
is explicitly NOT the vision's fuller scored need-state vector.

## Process note: an unresolved design fork, decided under a tooling failure

Two real design forks existed here that this project normally resolves
via a direct question to the founder before implementing (the same
practice Retrieval's own scoping and Synthesis's two forks followed):

1. **Computation**: a deterministic classifier vs. a new dedicated LLM
   call.
2. **Effect on Retrieval**: label-only vs. actually filtering
   Retrieval's output by the inferred need.

`AskUserQuestion` was attempted twice for this round and failed both
times with a tool-level stream error, not a user response. The
implementation proceeded on best judgment rather than blocking
indefinitely, flagged plainly in `engine/decisions.md` and in chat at
the time specifically so either choice could be overridden if the other
was actually wanted. **Neither fork has since been revisited with the
founder** — backlog #225 ("Need State: resolve the unresolved design
fork") tracks this explicitly. This spec documents what was built under
that constraint, not a confirmed-correct design.

## Fork 1 (computation) — chosen: deterministic, no new LLM call

`infer_need_state(state, threshold=3) -> NeedState`
(`src/need_state/engine.py`) is a pure function over WorldState only —
same trusted "mechanical, not a call" category as
`src/judgment/engine.py::compute_stagnation_signals`/
`recommend_phase_transition`. The alternative (a new LLM call reasoning
over WorldState) is the vision's more faithful design, but is exactly
the "invent a scored model with no evidence to calibrate it against"
risk this project's own roadmap doc flags for this specific layer —
plus it would add a new LLM call, and cost, to every turn.

Priority order, each branch grounded in a signal this codebase already
trusts elsewhere:

1. **`accountability`** — a Goal (`status="active"`) or Decision
   (`status="open"`) has gone `threshold` (3 — same constant value as
   Judgment's own `STAGNATION_TURN_THRESHOLD`, duplicated rather than
   imported, same "small utility functions deliberately duplicated
   across modules" convention as `src/orchestrator/modes.py`) turns
   without a status change. Checked FIRST — a stalled item is a more
   urgent need than a fresh, not-yet-stagnant one, even when both are
   present in the same turn.
2. **`decision`** — an open Decision exists, not yet stagnant. Mirrors
   Strategize mode's own criterion.
3. **`reflection`** — at least one Goal with `status="active"` exists
   (same "active only" scoping as `compute_stagnation_signals` — a
   paused/completed/abandoned Goal is already accounted for, not
   neglected, so it shouldn't drive a reflection need on its own), but
   nothing sharper fired.
4. **`general`** — none of the above; a brand-new Journey correctly
   infers `"general"`, not a guessed need.

Never invents a need beyond what's structurally present.

## Fork 2 (effect on Retrieval) — chosen: label-only, still unfiltered

`build_retrieved_context` (`src/retrieval/engine.py`) accepts the
inferred `need_state` and, when meaningfully set (anything but
`"general"`, which conveys nothing actionable and is deliberately
omitted), prepends a plain, explicit line ("This turn's inferred need:
decision (an open decision genuinely being weighed).") to the same
Retrieved Context block — Learning/Insight's patterns and insights stay
UNCHANGED and fully unfiltered alongside it.

The alternative (actually filtering or reordering patterns/insights to
match the inferred need) was rejected: `Pattern.pattern_type`/
`Insight.theme` are free text with no existing, validated need taxonomy
to match against reliably — building that matching logic now would risk
silently hiding a genuinely relevant pattern on a crude, unvalidated
heuristic, exactly the kind of invented-with-no-evidence mechanism this
project has refused everywhere else. Label-only lets Judgment weigh the
still-complete evidence knowing what this turn actually needs, without
anything being hidden from it. See
`engine/specs/retrieval-specification-v1.md` for Retrieval's own side of
this.

## Wiring

`src/api/server.py::send_message` calls `infer_need_state(state)` on
the PRE-turn `state` (loaded via `db.load_state`, before this turn's
own Interpretation has run) — correct, since Need State Inference has
to be ready before Retrieval, which itself runs before Judgment even
sees this turn's fresh Interpretation. Threaded only into
`build_retrieved_context`, which still feeds Judgment only, same scope
as Retrieval itself.

## Non-goals

No LLM call of its own. No filtering of Retrieval's output (see Fork 2
above — label-only is the current, deliberately narrow shape). No
scored/continuous need vector — only the closed four-value enum the
vision doc's Retrieval discussion names.

## Open questions

**Backlog #225** is this doc's central open item: both forks above were
decided without founder confirmation, under a tooling failure, not as a
considered design choice ratified by the person who owns the vision
doc. Revisiting either fork — e.g. moving to an LLM-based inference
once real usage exists to calibrate it, or moving Retrieval from
label-only to actual filtering — is explicitly still on the table and
not resolved by this spec.

## Verification

Covered by `pytest` (`tests/test_need_state.py`): priority ordering
across all four need states, including the "stagnant Goal beats a fresh
open Decision" and "fresh open Decision beats reflection" ordering
cases, plus confirming a paused Goal or resolved Decision never counts
toward `accountability`. `tests/test_retrieval.py` covers the label
being omitted when `need_state="general"` even alone, a meaningful
label appearing even with no patterns/insights to attach it to, and the
label never filtering or hiding an unrelated pattern/insight.
`tests/test_api_server.py` has an end-to-end two-turn test confirming
`send_message` actually threads a real inferred need through to
Judgment's prompt.
