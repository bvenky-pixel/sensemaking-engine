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
   conversation.
2. **A Journey recommends a Program.** Founder's own example: "This
   seems like a significant career decision. Would you like to start a
   Decision Program?" This is a NEW capability, not an existing one --
   see "The Recommendation Mechanism" below for exactly what has to be
   built.
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

Two worked stage sequences, inferred from the founder's own examples
(NOT yet founder-confirmed -- flagged as an Open Question below):

- **Decision Program**: Frame the decision -> Explore options -> Test
  assumptions -> Decide -> Commit -> Review outcome.
- **Confidence Program**: Identify the avoided situation -> Design a
  small experiment -> Attempt it -> Reflect -> Repeat with a harder
  experiment.

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
    stage TEXT NOT NULL,            -- current stage within program_type's
                                     -- own stage sequence
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

No Progress Bars

Direct design constraint, stated explicitly because the founder's own
"training plan" analogy could otherwise be read as inviting a
percentage-complete bar: `progress_summary` is prose ("You've explored
two of the three options you named, and you're waiting to hear back
about the compensation question before comparing them seriously"), not
a number. This is the same "no dashboard chrome, no score" discipline
already enforced everywhere else in this product
(`frontend/specs/product-experience-v1.md`), and it's also a MORE
honest representation of what a Program actually is -- "how much of a
career decision is done" has no real percentage, and asserting one
would be inventing false precision the same way this codebase has
refused to do with `confidence` fields elsewhere (Judgment/Planner's
own `confidence` reflects EVIDENCE COMPLETENESS, never a fabricated
sense of certainty).

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
the identical shape -- built once (e.g. "This Journey is part of an
active Decision Program ('Career Move'), currently at the 'Explore
options' stage. Two experiments logged: [...]. Last review: [...]"),
passed alongside `mode`, requiring no change to either prompt-building
function's own contract beyond one more optional string.

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

Open Questions

1. **Login requirement.** Journeys today support anonymous use (capped,
   then a magic-link prompt). Programs are long-lived, cross-Journey
   entities -- does starting a Program require login upfront (consistent
   with POM/Learning's existing per-account-only scoping), or does an
   anonymous person get to start one and hit the login wall only later?
   Recommend requiring login upfront, matching POM's own precedent --
   a Program that could vanish because an anonymous session expired
   would undermine the entire "persists across time" promise this
   feature exists to make.
2. **Stage sequences.** The two worked examples above (Decision,
   Confidence) are this spec's own inference from the founder's memo,
   NOT founder-confirmed. Needs an explicit design pass per type, same
   rigor as Priority 4's per-mode framework table -- these are genuinely
   new content, not derivable from existing code the way most of
   Priorities 1-4 were.
3. **The Recommendation Mechanism** (Option A vs. B above) -- needs a
   founder call given the schema-complexity tradeoff.
4. **Does a Program's own Journeys still each pick a Counseling Mode?**
   E.g. is a Journey inside a Decision Program free to be started in
   Vent mode, or does entering a Program implicitly bias toward
   Strategize? Recommend: modes and Programs stay orthogonal -- a
   Program is WHAT you're working on across time, a Mode is HOW this
   particular conversation should go right now; forcing a mode based on
   Program type would remove a degree of freedom the founder's own mode
   design has otherwise protected carefully (Governing Law 2, user
   agency).
5. **Naming for `progress_summary` generation.** Who writes it -- a new
   small LLM call after each Journey that touches the Program (cost:
   one more call, though not per-turn, only per-Journey-close), or does
   it stay a manually-edited field a person updates themselves? A new
   LLM call is more "alive," but costs money on every Program-linked
   Journey close; a manual field is free but adds friction. Needs a
   product call, not an engineering default.

---

Rollout

1. Resolve Open Questions 1-3 with the founder before writing schema
   code -- these change the data model and API shape materially.
2. Build the data model (`programs`, `program_experiments`,
   `program_reviews`, `sessions.program_id`) and CRUD API endpoints
   (`POST/GET /programs`, `GET /programs/{id}`, status transitions),
   mirroring existing endpoint conventions in `src/api/server.py`.
3. Build the Plans tab for real: a program-type picker (direct reuse of
   `ModePicker.svelte`'s existing visual pattern for a new content type),
   an active-Programs list (direct reuse of Activity's existing list
   pattern), and a Program detail view (new -- stage, prose progress,
   experiments, reviews, scoped insights).
4. Thread `program_context` into Planner/Response, reusing the `mode`
   parameter's existing shape exactly.
5. Build the Recommendation Mechanism per whichever option Open
   Question 3 resolves to.
6. Live-dispatch verify a full multi-Journey Program lifecycle (start,
   several linked Journeys advancing stage/logging experiments, a
   review, completion) before shipping -- this is the one spec in this
   set with no existing test/verification precedent to extend, so the
   first verification pass needs to be built from scratch alongside the
   feature, not adapted from an existing script.
