Confidant Counseling Modes: Frameworks Specification v1

Status: SPEC ONLY. Nothing in this document has been implemented.
Written from the founder/CPO product-direction memo "Make Understanding
Visible, Not Just Better" (2026-07-22, Priority 4), grounded against the
actual current implementation (`src/orchestrator/modes.py`,
`src/planner/schema.py`, `src/planner/engine.py`). Same discipline as
every other spec in this set: implementation only after this is
confirmed.

---

Purpose

From the product-direction memo: "Modes should not be prompt variants...
each mode should own a distinct planning framework... the user should be
able to identify the mode from conversation behavior alone, even if the
mode name is hidden."

This is the largest-looking priority of the four, and the one most
worth de-risking with an honest look at what already exists before
concluding it needs a rebuild. It does not need one. The plumbing this
memo is asking for -- distinct objectives, distinct interventions, and a
mode-specific mechanism for choosing between them per turn -- is already
built. What's missing is that the six modes' PROMPT CONTENT doesn't yet
go as far as this memo's own framework descriptions, and ONE new Planner
field (a stated success criterion) doesn't exist yet.

---

What already exists (confirmed against `src/orchestrator/modes.py`)

- **Per-mode prompt injection, not a single shared paragraph.**
  `PLANNER_MODE_FOCUS` and `RESPONSE_MODE_FOCUS` are already separate
  dictionaries keyed by mode id, each with real, distinct guidance text
  injected into Planner's and Response's prompts respectively. This is
  not "one prompt with a tone knob" -- it is already six (five modes +
  Adaptive) separate instruction blocks.
- **Six modes, one shared Planner schema.** Every mode's Planner call
  produces the same `Planner` object shape (`primary_objective`,
  `rationale`, `conversational_strategy`, `resolution_blocker`,
  `priority_topics`, `questions_to_explore`, `assumptions_to_test`,
  `planning_constraints`, `desired_outcome`, `temporal_horizon`,
  `confidence`). The memo's framework descriptions map onto this
  EXISTING shared shape more directly than it might first appear (see
  the framework table below) -- most of what's being asked for is
  sharper INSTRUCTION about how to fill the existing fields per mode,
  not new fields.
- **Adaptive mode already implements "diagnose before intervening."**
  The memo's proposed Adaptive framework -- "Diagnose -> Select
  Framework -> Reassess" -- is, functionally, what Adaptive mode already
  does: Judgment runs first every turn (the diagnosis, already
  happening regardless of mode), Planner then chooses one of the five
  concrete lenses via `active_lens` based on that Judgment (the
  selection), and because Judgment re-runs fresh every turn, the next
  turn's diagnosis is a genuine reassessment, not a stale one. Once the
  five underlying lenses are sharpened per this spec, Adaptive inherits
  the improvement automatically -- it requires no separate Adaptive-
  specific rebuild.

---

The Framework Table

For each mode: the memo's proposed framework, its success metric, and
which EXISTING Planner field is the natural home for each concept --
versus what's genuinely new.

| Mode | Framework | Existing field mapping | New? |
|---|---|---|---|
| **Vent** | Observe -> Validate -> Clarify | `primary_objective` = surface emotions/meaning/impact; `conversational_strategy` = "reflect emotions"; `planning_constraints` MUST include something equivalent to "no action plan, no advice" this turn | `success_criterion` field (see below) |
| **Strategize** | Options -> Tradeoffs -> Decision | `priority_topics` = the options; `assumptions_to_test` = the assumptions; `planning_constraints` = the constraints; Judgment's own `risks` = the risks (Planner doesn't need to re-derive these, just foreground them) | `success_criterion` |
| **Commit** | Goal -> Obstacle -> Commitment | `resolution_blocker` = the obstacle; `questions_to_explore` sharpened toward "what, by when" rather than open reflection; `desired_outcome` = the concrete commitment itself, phrased as a specific action, not a general intention | `success_criterion` |
| **Explore** | Assumption -> Challenge -> Discovery | `assumptions_to_test` = the assumption being challenged; `conversational_strategy` = "challenge assumptions" (already a documented example value in Planner's own field definition); `primary_objective` = press on the single most load-bearing assumption/contradiction | `success_criterion` |
| **Realign** | Values -> Reality -> Alignment | `resolution_blocker` = the gap between stated value and actual behavior; `primary_objective` = connect current situation to a specific, WorldState-grounded value/goal | `success_criterion`; grows more powerful once POM's own `identity`/`narrative` systems mature, per the memo's own observation |
| **Adaptive** | Diagnose -> Select Framework -> Reassess | Already implemented via Judgment (diagnose) + `active_lens` (select) + fresh Judgment next turn (reassess) | Nothing structurally new -- inherits whichever of the five lenses above it selects |

**The one clearly new schema element across all six rows**:
`success_criterion` -- a short, mode-conditioned statement of what
"this turn went well" would mean (e.g. Vent: "the person feels more
understood than when they started"; Strategize: "the decision became
easier"; Commit: "a concrete commitment was made"). This is the field
Priority 3's feedback-signal work is designed to eventually check
against (see `understanding-feedback-signals-specification-v1.md`'s
"The Priority 4 Connection").

---

The Schema-Per-Mode Question (the one real architectural fork)

The memo's framing ("each mode should own a distinct planning
framework") could be read as calling for six distinct Planner SCHEMAS
(different fields entirely per mode), not just six distinct prompts
over one shared schema. This spec explicitly does NOT recommend that,
for a reason grounded directly in this codebase's own stated design
principle:

> "This is a full LLM call, not a rule engine... Deliberate simplicity:
> one call, one schema, no hybrid complexity." -- `planner/engine.py`'s
> own module docstring, restated from `planner-specification-v1.md`.

A schema-per-mode redesign would mean six different structured-output
shapes, six different `model_json_schema()` calls, and real complexity
in `run_planner`/`run_turn` to route between them -- a genuine
architecture change, not a prompt-engineering round. This spec's
position: there is no evidence yet that the shared schema is actually
insufficient to carry the six frameworks above -- the table shows every
framework mapping onto existing fields plausibly well. The correct,
evidence-based sequence (same discipline as every boolean-gate this
codebase has added only after proving a prompt-only version failed) is:
sharpen the six prompts first, live-dispatch-verify whether the shared
schema can actually carry the distinctiveness the memo wants, and ONLY
escalate to per-mode schemas if that verification shows the shared
shape is genuinely the bottleneck -- not before.

---

Non-Goals

- Not a personality rewrite. Modes differ in what they track and
  optimize for, not in artificial verbal tics -- the memo's own framing
  ("modes should not be personalities... they should be different
  cognitive frameworks") is the guardrail here, and Response's existing
  Grounding law (never invent content Planner didn't authorize) already
  prevents modes from becoming costume changes.
- Not a change to Governing Law 2 (user agency is absolute). No mode,
  including Explore's "willing to say 'is that actually a fact?'", may
  cross from challenging a belief into deciding for the user or
  pressuring a direction -- this line already exists in Planner's
  Governing Laws and applies identically across all six modes.
- Not, yet, a schema-per-mode rebuild (see above) -- explicitly deferred
  pending live evidence.

---

Open Questions

1. **Pilot scope.** Start with all six at once, or pilot two (the memo
   itself flags Explore as "where you currently have the most
   opportunity" and Realign as the mode with a clear future POM
   dependency) before rolling out the rest? Recommend piloting
   Strategize and Realign first: Strategize because its framework
   (Options -> Tradeoffs -> Decision) is the most structurally different
   from today's prompt and thus the best test of whether the shared
   schema holds up; Realign because it's the mode most likely to reveal
   whether `success_criterion` is actually a useful, checkable field or
   just a nice-sounding addition.
2. **How is "the user should be able to identify the mode from behavior
   alone" actually tested?** This needs an evaluation method, not just
   a prompt rewrite -- e.g. a blind read-through of live-dispatched
   transcripts (mode names stripped) asking a reviewer to guess the
   mode, similar in spirit to this codebase's existing live-dispatch
   verification discipline but new as a formal test design. Worth
   scoping explicitly rather than assuming the prompt rewrite alone
   proves itself.
3. **Does `success_criterion` get surfaced to the user at all**, or
   does it stay a private Planner field Response never voices (matching
   every other Planner field's "private plan, never spoken directly"
   status)? Recommend staying private for v1, consistent with Planner's
   own Governing Laws ("you never address the user directly").

---

Rollout

1. Add `success_criterion: str` to the Planner schema, with per-mode
   prompt guidance for what it should contain (mirrors how `active_lens`
   was added on top of the original v1 spec once Synthesis needed it --
   same incremental-field precedent).
2. Rewrite `PLANNER_MODE_FOCUS`/`RESPONSE_MODE_FOCUS` for the two pilot
   modes (Open Question 1) to the sharper framework language in the
   table above -- explicit stage names (e.g. Strategize's prompt should
   name "Options -> Tradeoffs -> Decision" as its own internal structure,
   not just describe the goal in prose).
3. Live-dispatch verify the two pilot modes against fresh transcripts,
   specifically checking: (a) does `success_criterion` come out
   genuinely mode-specific and non-generic, (b) does the SAME underlying
   WorldState, run through two different modes, actually produce
   visibly different Planner output -- the sharpest test of whether
   this is real behavioral differentiation or still just flavor text.
4. Resolve Open Question 2 (the blind-mode-identification test) and run
   it against the pilot before declaring the pilot successful.
5. Roll out to the remaining four modes only after the pilot's live
   verification actually shows distinct behavior, not on schedule.
