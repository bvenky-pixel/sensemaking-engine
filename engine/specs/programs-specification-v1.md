Confidant Programs Specification v1

Status: SPEC ONLY. Nothing in this document has been implemented.
Written from the founder/CPO's direct product-architecture memo on
Plans/Programs (2026-07-22), grounded against the actual current
implementation (`src/api/db.py`'s table conventions,
`src/orchestrator/modes.py`'s per-type-focus-note pattern,
`frontend/app/src/screens/Plans.svelte`, backlog #266). Same discipline
as every other spec in this set: implementation only after this is
confirmed.

**This is the most greenfield spec of the five.** Priorities 1-4 each
had substantial existing infrastructure to ground against. Programs has
almost none -- `Plans.svelte` today is a deliberate, honest "Coming
soon" placeholder (backlog #266: "nothing in the backend or the rest of
the frontend produces a 'Plan' yet... design work on it hasn't
started"). This spec is the first real design pass, not a mapping of
an existing capability's gaps.

---

Purpose

Direct founder framing: "Programs are the primary content of the Plans
tab... think of Plans similarly to how training plans function in
running apps... Programs should feel like structured personal-
development journeys rather than project-management plans." The Plans
tab should eventually answer "What am I actively working on right now?"
-- not "What tasks do I have?"

The founder's own explicit instruction: treat Programs as a core
product pillar alongside Journeys and the Personal Operating Model, not
a secondary feature bolted onto the existing five-tab structure.

---

The Core Distinction: Programs vs. Journeys

> "Programs persist across Journeys. Journeys are conversations."

This is the single load-bearing architectural fact this whole spec is
built around. A Journey is a bounded conversation with its own
WorldState, same as today. A Program is a long-lived entity that
outlives any single Journey, maintaining its own state (stage,
progress, experiments, reviews, insights, history) independent of which
Journey most recently touched it. A single Program (e.g. "Decision
Program: Career Move") is expected to span MANY Journeys over weeks or
months, each contributing to the same persistent Program state.

This is a genuinely new relationship in the data model -- today,
`sessions` (Journeys) are the only persisted, addressable entity above
individual messages; nothing outlives a single session's own row.

---

Entry Points (three, per the founder's own spec)

1. **Start a Program directly from Plans**, no Journey first --
   analogous to today's mode picker (`ModePicker.svelte`), but picking a
   PROGRAM TYPE (Decision, Career Transition, Confidence -- the
   founder's own worked examples) rather than a conversational mode.
   Starting a Program this way should immediately open a Journey linked
   to it -- Programs are the persistent container, but all actual
   thinking still happens through conversation; a Program with no
   Journey yet is an empty shell, not a place to "do work" outside
   conversation. **Naming note** (see Decided, below): "Decision
   Program" is this spec's own internal name for the TYPE, not the
   literal picker copy a user sees -- the picker shows something closer
   to "Work through a decision" / "Navigate a career move," with
   "Program"/"Program Type" staying architectural vocabulary, the same
   relationship "WorldState" has to the UI today.
2. **A Journey recommends a Program.** Founder's own example: "This
   seems like a significant career decision. Would you like to start a
   Decision Program?" This is a NEW capability, not an existing one --
   see "The Recommendation Mechanism" below for exactly what has to be
   built. Same naming note applies: the SHIPPED offer text drops
   "Program" (e.g. "Would you like help working through this as its own
   thread you can come back to?"), even though the founder's own memo
   language is quoted here verbatim as the originating idea.
3. **Manage existing Programs** from the Plans tab: view, resume,
   review progress, complete, archive, start new. Mirrors the existing
   Activity tab's Journey-list pattern (filter, bookmark, resume) --
   same list-of-cards shape, different underlying entity.

---

The Program <-> Program Type Parallel to Modes

Worth naming explicitly because it changes how much of this spec is
genuinely new versus a second application of a pattern this codebase
already has proven: **Program Types are to Journeys-across-time what
Counseling Modes are to a single turn.** Modes (see
`counseling-modes-frameworks-specification-v1.md`) are per-turn
cognitive frameworks, keyed by id, each with its own focus-note text
injected into Planner/Response's prompts (`PLANNER_MODE_FOCUS`,
`RESPONSE_MODE_FOCUS` dictionaries in `src/orchestrator/modes.py`).
Program Types are the same SHAPE of idea one level up: each type (e.g.
"decision", "career_transition", "confidence") needs its own defined
STAGE SEQUENCE (the multi-Journey structure the founder's memo implies
-- a Decision Program's stages are not the same as a Confidence
Program's), the same way each Mode needs its own conversational
framework. The engineering pattern (`type id -> dict of type-specific
content`) does not need to be invented; it needs to be applied to a new
kind of "type."

**Decided (founder/CPO, 2026-07-22): three worked stage sequences,
confirmed after a full revision pass.** The original two-sequence draft
(Decision, Confidence) is superseded below -- both were reworked, and
Career Transition's sequence (previously undrafted, despite being named
as a worked example throughout this spec) is now specified for the
first time.

- **Decision Program**: Frame Decision -> Explore Options -> Reduce
  Uncertainty -> Decide -> Live the Decision -> Review Outcome.
  The original draft's "Test Assumptions" and "Commit" stages are both
  gone. "Test Assumptions" is replaced by the deliberately broader
  "Reduce Uncertainty" -- founder's own framing: assumption-testing is
  one narrow way to reduce uncertainty, but experiments, conversations,
  research, and observation all belong in this stage too. "Commit" is
  cut entirely, not renamed -- founder's own diagnosis: it didn't
  represent a distinct state transition ("Decide to leave job. Decision
  made. The commitment is implicit."). "Live the Decision" is the real
  addition in its place: the decision has entered reality (accepted the
  new role, had the difficult conversation, moved cities) -- only once
  that's true can Review Outcome evaluate actual consequences rather
  than a still-hypothetical choice. Founder's own framing for the whole
  arc: "Thinking -> Investigation -> Choice -> Reality -> Reflection...
  much closer to life."
- **Confidence Program**: Identify the Edge -> Take the First Step ->
  Build Evidence -> Expand the Edge -> Internalize the Change. Founder's
  own diagnosis of the original draft: "mechanically correct but
  emotionally weak... describing the intervention, not the
  transformation" -- a training-plan analogy shouldn't read as "Run,
  Run Again, Run Again, Run Again." The repeated-attempt structure the
  original draft put at the WHOLE-PROGRAM level (a bare "Repeat" stage)
  moves down into "Expand the Edge" specifically -- that stage may
  itself repeat many times as the person takes on harder versions of
  the same challenge, but the Program as a whole still has a real
  ending: "Internalize the Change" asks the key question ("Do I now see
  myself differently?") and the Program can actually complete. See
  "Every Program Must Be Completable," below -- this fix is the direct
  answer to that principle for this Program type specifically.
- **Career Transition Program**: Understand Current Reality -> Define
  What You Want Next -> Explore Possible Paths -> Validate Options ->
  Make the Transition -> Settle Into the New Reality. Founder's own
  framing for why this needs to sit above job-board mechanics ("that's
  LinkedIn. Confidant should operate at a higher level"): "Understand
  Current Reality" probes what's actually wrong (burnout, a manager, the
  industry, the role, identity -- not just "I want a new job"); "Define
  What You Want Next" is named as the stage most people skip entirely,
  since knowing what you dislike isn't the same as knowing what you
  want; "Settle Into the New Reality" is the closing stage precisely
  because early transition discomfort is otherwise easy to misread --
  the Program's job here is helping the person tell adjustment
  discomfort apart from a genuine mismatch, not just marking "moved"
  and closing the file.

---

Stage Phases: Discovery / Action / Integration

**A real structural addition on top of the three sequences above, not
just naming polish** -- founder's own framing: "the bigger structural
recommendation... not names, not counts, the stage architecture
itself." Every stage across every Program Type belongs to one of three
PHASES:

| Phase | Goal | Examples across the three types above |
|---|---|---|
| Discovery | Understand | Frame Decision; Understand Current Reality; Identify the Edge |
| Action | Generate reality | Reduce Uncertainty, Live the Decision; Validate Options, Make the Transition; Take the First Step, Build Evidence, Expand the Edge |
| Integration | Convert experience into learning | Review Outcome; Settle Into the New Reality; Internalize the Change |

Every stage above classifies cleanly into one of these three except
one: Decision Program's "Decide" stage itself -- the choice-point
between Discovery and Action, arguably belonging to neither. This spec
tentatively classifies "Decide" as the last Discovery stage (the
decision is made, but not yet real), on the reasoning that "Action" per
this table's own definition means GENERATING reality, and a decision
made but not yet acted on hasn't done that yet -- but this one
classification is worth the founder's explicit confirmation rather than
silently assumed correct along with everything else here.

**Why this matters beyond labeling** (founder's own reasoning, worth
preserving verbatim): "eventually Claude can reason about stage
transitions more intelligently. Instead of: Decision Program, Stage 4.
You know: Decision Program, Integration Phase. This becomes useful
across all future programs." Concretely: `program_context` (see
"Threading Program Context Into a Turn," below) can name the PHASE
generically ("This Journey is in the Integration phase of an active
Program") in addition to the type-specific stage name -- meaning
Planner/Response prompt guidance can eventually be written once, per
phase, and apply across every current and future Program Type, rather
than needing bespoke guidance rewritten for each new type's own stage
names. This spec does not propose building phase-conditioned prompt
behavior in v1 (see "Deliberately Out of Scope for v1," below) -- the
phase taxonomy is specified now because retrofitting it onto stage data
that didn't carry it from the start would be real rework later, not
because phase-aware prompting itself needs to ship this round.

**Data model implication**: `programs.stage` (see Data Model, below)
stores a stage ID string (e.g. `"reduce_uncertainty"`), not the phase --
phase is looked up from a new `PROGRAM_TYPE_STAGES` dict (`{program_type:
[{"id", "label", "phase"}, ...]}`), the same "don't persist what can be
derived" discipline this spec already applies to Program "history"
above, and the same `type id -> dict of type-specific content` shape
already proven by `PLANNER_MODE_FOCUS`.

---

Every Program Must Be Completable

New, explicit design principle, stated because it changed the Confidence
Program's own redesign above and should constrain every future Program
Type too. Founder's own framing: "I think every Program should be
completable. Otherwise the Plans tab becomes a graveyard of perpetual
processes." A Program Type whose stage sequence has no real Integration-
phase ending (the original Confidence draft's bare "Repeat" was exactly
this failure) is a design defect, not a stylistic choice -- any future
Program Type added to `PROGRAM_TYPE_STAGES` must end in a genuine
Integration-phase stage, the same way these three now do.

---

Data Model

Grounded directly against `src/api/db.py`'s existing table
conventions (`learned_patterns`/`insights`'s `user_id`-scoped shape,
`insight_sessions`' join-table pattern, `sessions.mode`'s per-session-
scalar precedent):

```sql
CREATE TABLE IF NOT EXISTS programs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    program_type TEXT NOT NULL,
    title TEXT NOT NULL,            -- e.g. "Career Move" (the specific
                                     -- instance, not the type's own name)
    status TEXT NOT NULL DEFAULT 'active',  -- active | completed | archived
    stage TEXT NOT NULL,            -- stage id within program_type's own
                                     -- PROGRAM_TYPE_STAGES sequence (e.g.
                                     -- "reduce_uncertainty") -- phase
                                     -- (discovery/action/integration) is
                                     -- looked up from that dict, not stored
    progress_summary TEXT NOT NULL DEFAULT '',  -- prose, NOT a percentage
                                     -- -- see "No Progress Bars" below
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS program_experiments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    program_id TEXT NOT NULL,
    description TEXT NOT NULL,      -- the concrete thing being tried
    status TEXT NOT NULL DEFAULT 'in_progress',  -- in_progress | completed | abandoned
    reflection TEXT,                -- filled in on completion/abandonment
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    FOREIGN KEY (program_id) REFERENCES programs(id)
);

CREATE TABLE IF NOT EXISTS program_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    program_id TEXT NOT NULL,
    session_id TEXT NOT NULL,       -- which Journey produced this review
    summary TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (program_id) REFERENCES programs(id),
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);
```

Plus one new column on the existing `sessions` table, same `ALTER
TABLE` migration pattern already used for `mode`:

```sql
ALTER TABLE sessions ADD COLUMN program_id TEXT;
```

**"Insights" and "history" from the founder's own field list are
deliberately NOT new tables**:

- **Insights**: reuse the EXISTING `insights`/`insight_sessions`
  infrastructure (see `insight-generation-specification-v1.md`), scoped
  to a Program by filtering to sessions that share that Program's
  `program_id`. A Program is a natural, narrower scoping boundary for
  cross-session synthesis than "all of a person's Journeys ever" --
  worth noting as a real, valuable extension of Insight Engine's own
  scope once Programs exist, not a new insight mechanism.
- **History**: a COMPUTED timeline (Program creation, stage
  transitions, `program_experiments` started/resolved, `program_reviews`
  created), not its own stored table -- same "don't persist what can be
  derived" discipline as everything else in this codebase.

---

No Progress Bars (for the summary) / Numbered Stage Tracker (for the stage) -- these are two different UI elements, decided differently

`progress_summary` stays prose ("You've explored two of the three
options you named, and you're waiting to hear back about the
compensation question before comparing them seriously"), never a
percentage -- this part of the constraint stands as originally written.
This is the same "no dashboard chrome, no score" discipline already
enforced everywhere else in this product
(`frontend/specs/product-experience-v1.md`), and it's also a MORE
honest representation of what a Program actually is -- "how much of a
career decision is done" has no real percentage, and asserting one
would be inventing false precision the same way this codebase has
refused to do with `confidence` fields elsewhere (Judgment/Planner's
own `confidence` reflects EVIDENCE COMPLETENESS, never a fabricated
sense of certainty).

**A separate, distinct display question -- the current STAGE within the
Program's own sequence -- was decided the other way** (see Decided,
below): a numbered "Stage 2 of 6"-style tracker, not prose-only. This
spec's own first draft recommended prose-only for stage display too,
matching the discipline above; the founder's explicit call reversed
that specific piece, not the percentage-free `progress_summary`
principle. Worth being precise about the boundary: no field in this
data model will ever show a percentage or a fabricated completion
score, but the Program's discrete stage position (an ordinal, not a
completion estimate) is the one place in this spec where a numbered UI
element is intentional.

---

The Recommendation Mechanism (entry point 2 -- the one piece with no
existing plumbing to lean on)

Confirmed by reading the actual code: tapping one of Response's
existing `options` buttons today just sends that option's `label` back
as a normal user message (`Transcript.svelte`'s `onOptionSelect`) --
there is no "special action" option type. A Program recommendation
needs one of two designs:

**Option A (no new mechanism, reuse the existing option-tap-sends-a-
message pattern)**: Response offers "Yes, start a Decision Program" /
"Not now" as ordinary `options`. Tapping "yes" sends that literal text
as the next message; a NEW, separate, deterministic check (not an LLM
call) on the NEXT turn's message content decides whether to actually
create the Program record. Simple, but fragile -- it's pattern-matching
on message text, the same category of thing this codebase has
consistently preferred NOT to do (compare: `has_decision_resolution`
exists specifically because "did the user decide something" is too
important to leave to fragile text matching).

**Option B (new, small mechanism)**: a new Planner field,
`recommended_program_type: Optional[str]`, populated only when
Judgment/WorldState show a genuinely significant, still-open Decision
or Goal (mirrors the existing "MANDATORY, answer this first" boolean-
gate discipline used for `has_risk_signal`/`has_decision_resolution` --
this should likely be `has_program_recommendation: bool` +
`recommended_program_type` as a paired boolean-gate, not a bare
optional string, for exactly the reasons those existing gates were
added). Response then surfaces this as a natural offer with real
`options`, and a TAPPED "yes" hits a dedicated API action
(`POST /programs` with a `source_session_id`) rather than being
re-interpreted from prose. More engineering, but consistent with this
codebase's own established preference for structured signals over text
pattern-matching.

**This spec recommends Option B**, consistent with the precedent every
other "did something important just happen" signal in this codebase has
set -- but flags it as a real Open Question given the added schema
complexity on an already-large Planner schema.

---

Threading Program Context Into a Turn

Once a Journey has a `program_id`, Planner and Response need to know
their conversation is part of an ongoing Program, not a standalone
Journey -- otherwise nothing about the conversation would actually
reflect the Program's persistent state. This reuses an EXISTING
plumbing pattern exactly: `mode` is already threaded through
`planner_mode_focus_note`/`response_mode_focus_note` as a pre-resolved
string parameter into `build_messages` (see `src/planner/prompt.py`,
`src/response/prompt.py`). A `program_context: str` parameter follows
the identical shape -- built once (e.g. "This is part of an ongoing
thread called 'Career Move,' currently at the 'Reduce Uncertainty'
stage (Action phase). Two experiments logged: [...]. Last review:
[...]"), passed alongside `mode`, requiring no change to either
prompt-building function's own contract beyond one more optional
string. Naming both the stage AND its phase here, rather than the stage
alone, is exactly the payoff described in "Stage Phases," above -- it
costs nothing extra to include today, and positions future phase-
conditioned prompt guidance to slot in without touching this threading
mechanism again.

---

Deliberately Out of Scope for v1

- **Automatic, inferred Program state updates.** This spec does NOT
  propose a mechanism for Judgment/Planner to automatically decide "the
  user just completed an experiment" or "advance to the next stage"
  from conversation content alone. Given how much schema complexity
  every other automatic-inference gate in this codebase has needed to
  become reliable (`has_risk_signal`, `has_decision_resolution`,
  `has_knowledge_correction` each needed a dedicated boolean-gate
  round), adding this on top of an already-new Program concept is
  overreach for v1. Stage advancement, marking an experiment complete,
  and completing/archiving a Program are all explicit USER actions in
  the Plans tab UI for v1 -- a deliberate scope cut, not an oversight.
- **Program templates beyond the three named examples.** Decision,
  Career Transition, Confidence are the founder's own worked examples;
  this spec does not invent additional types. Adding a fourth type
  later is additive (new dict entries, same pattern), not a redesign.
- **Cross-Program relationships** (e.g. "these two Programs are related").
  Multiple concurrent Programs are explicitly supported (data model
  above has no artificial limit), but they're independent of each other
  in v1 -- no shared state, no cross-Program insights.

---

Decided (founder/CPO, 2026-07-22)

- **Login requirement: required upfront.** Confirmed, matching this
  spec's own recommendation and POM's existing per-account-only
  precedent.
- **Recommendation Mechanism: Option B.** The new boolean-gate pair
  (`has_program_recommendation` / `recommended_program_type`) plus a
  dedicated `POST /programs` API action on tap, confirmed over reusing
  the fragile option-tap-then-text-match pattern -- matching this spec's
  own recommendation and the precedent set by every other "did something
  important just happen" signal in this codebase.
- **Modes and Programs stay fully orthogonal.** Confirmed, matching this
  spec's own recommendation -- a Program never biases which Counseling
  Mode a linked Journey uses; Governing Law 2 (user agency) keeps that
  choice with the person every time.
- **`progress_summary` authorship: hybrid.** An LLM call drafts it at
  Journey-close (same "not per-turn, only per-Journey-close" cost
  profile as the plain "new LLM call" option this spec originally
  offered), rendered as an editable field so the person can correct or
  rewrite it. This is a genuine third option beyond the two this spec
  originally posed (LLM-only vs. manual-only) -- it keeps the field
  "alive" by default without requiring the person to write it from
  scratch, while still giving them the last word on their own summary.
- **"Program" stays internal vocabulary, not user-visible language.**
  Confirmed, matching this spec's own recommendation and
  `product-risks-and-design-principles-v1.md`'s Risk 2 audit. Plans shows
  only named instances ("Career Move," "Speaking Up at Work"); "Program"
  and "Program Type" never appear as UI copy, the same relationship
  "WorldState" has to the UI today. See the naming notes added to Entry
  Points above for what shipped copy should look like instead.
- **Stage display: a numbered tracker ("Stage 2 of 6"), not prose-only.**
  This is a deliberate reversal of this spec's own original
  recommendation (prose-only, matching the Brief's "no progress bars"
  principle) -- noted explicitly rather than silently dropped, since it
  cuts against a discipline enforced everywhere else in this product.
  See "No Progress Bars (for the summary) / Numbered Stage Tracker (for
  the stage)" above for the precise boundary this draws: `progress_summary`
  still never shows a percentage or a fabricated completion score: only
  the Program's discrete stage POSITION (an ordinal, not a completion
  estimate) gets the numbered treatment.

Open Questions

All prior open questions are now resolved (see Decided sections
throughout this document). One narrow item remains, deliberately kept
open rather than force-closed:

1. **"Decide" stage's phase classification** (Decision Program). This
   spec tentatively classifies it as Discovery-phase (see "Stage
   Phases," above) on the reasoning that Action means generating
   reality and a decision not yet acted on hasn't done that -- but this
   is this spec's own tentative call, not yet explicitly confirmed the
   way the rest of the phase table was. Low-stakes to leave open:
   `PROGRAM_TYPE_STAGES`' `phase` value for this one stage is a one-line
   change whenever it's confirmed, and nothing else in the rollout below
   depends on it being resolved first.

---

Rollout

1. Build the data model (`programs`, `program_experiments`,
   `program_reviews`, `sessions.program_id`) and CRUD API endpoints
   (`POST/GET /programs`, `GET /programs/{id}`, status transitions),
   mirroring existing endpoint conventions in `src/api/server.py`.
3. Build the Plans tab for real: a program-type picker (direct reuse of
   `ModePicker.svelte`'s existing visual pattern for a new content type,
   with jargon-free copy per the naming decision above), an
   active-Programs list (direct reuse of Activity's existing list
   pattern), and a Program detail view (new -- numbered stage tracker,
   prose progress summary, experiments, reviews, scoped insights).
4. Thread `program_context` into Planner/Response, reusing the `mode`
   parameter's existing shape exactly.
5. Build the Recommendation Mechanism per the decided Option B above:
   the new Planner boolean-gate pair, and the dedicated `POST /programs`
   API action wired to a tapped recommendation.
6. Live-dispatch verify a full multi-Journey Program lifecycle (start,
   several linked Journeys advancing stage/logging experiments, a
   review, completion) before shipping -- this is the one spec in this
   set with no existing test/verification precedent to extend, so the
   first verification pass needs to be built from scratch alongside the
   feature, not adapted from an existing script.
