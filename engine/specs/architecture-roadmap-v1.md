# Architecture Roadmap v1 — from today's System Architecture to the 12-layer vision

**Status: DISCUSSION DRAFT.** Written to reconcile `system-architecture-
v2-specification.md` (the current, implemented architecture) against the
12-layer vision described in the founder's uploaded vision documents
(`Confidant_Architecture.docx` and its companions — signal, output,
personal-operating-model, security, ROI, and investor-measurement specs).
Not a commitment to build all 12 layers, and not a replacement for
`system-architecture-v2-specification.md`, which remains authoritative
for everything it already covers. This document exists to answer one
question honestly: **if we're going to grow toward that vision, what do
we build first, and in what order, without inventing capability the
evidence doesn't support?** — the same discipline this codebase has
applied to every component built so far (Interpretation's multi-round
hardening, Judgment's boolean-gates, Planner's "resist tuning until real
samples exist," Learning's own reserved-slot status).

---

## 1. What the vision documents actually describe

Read together, the eight vision documents describe a **Series A-stage
enterprise workforce-development platform**: a 12-layer reasoning
pipeline, three interaction modes (conversational, reflective, proactive),
four signal categories (conversational, behavioral, environmental,
physiological — including wearables), a nine-system Personal Operating
Model grounded in named psychological frameworks (Self-Determination
Theory, Narrative Identity Theory), an enterprise sponsor/organization
layer with leadership-readiness dashboards, SOC2/ISO27001/GDPR compliance
architecture, and an investor-grade measurement framework (cohort
retention, LTV/CAC, POM Lift Studies).

That is a different scale of system than what exists today: a
single-user Sensemaking Engine reasoning about one conversation at a
time, with no persistent cross-conversation memory, no organization
concept, and no enterprise apparatus. Most of the vision documents'
content (the sponsor layer, the compliance/investor apparatus, wearable
integration) presupposes a business and user base that doesn't exist
yet — building toward it now would repeat the exact mistake this
codebase has refused to make everywhere else. This roadmap only concerns
itself with the parts of the vision that extend the **reasoning core**,
since that's what's actually in scope right now.

---

## 2. Mapping the vision's 12 layers to what exists today

**Updated 2026-07-15** -- this table was stale against actual code
(previously claimed 6/12 built; Learning, Insight Engine, and Memory
Store were all already real by the time this was checked, and Retrieval
has since been added). Corrected here rather than left to mislead the
next planning pass.

| # | Vision layer | Current status | Current equivalent |
|---|---|---|---|
| 1 | Interpretation | **Built** | `src/interpretation/` |
| 2 | Learning | **Built** | `src/learning/engine.py` -- offline, evidence-gated (`MIN_EVIDENCE=3`) behavioral pattern detection |
| 3 | Memory Store | **Built** | `behavioral_events` table (`src/api/db.py`) -- append-only per-user log Learning reads from |
| 4 | Personal Operating Model | **Not built** | — |
| 5 | World State | **Built** | `src/state/world_state.py` |
| 6 | Insight Engine | **Built** | `src/insight/engine.py` -- offline, evidence-gated (`MIN_EVIDENCE_SESSIONS=2`) cross-session theme detection |
| 7 | Need State Inference | **Not built** | Planner infers priority implicitly; no scored need-state vector exists |
| 8 | Retrieval | **Built, scoped narrow** | `src/retrieval/engine.py` -- unfiltered surfacing of Learning/Insight output into Judgment, not need-aware selective retrieval (needs #7 first) |
| 9 | Judgement | **Built, single-perspective** | `src/judgment/` — one reasoning pass, not the vision's 5-persona fusion |
| 10 | Synthesis | **Not built** | No multi-perspective output to synthesize yet. Counseling modes (`src/orchestrator/modes.py`) is a scoped-down preview -- one fixed lens per Journey, not the vision's multi-lens fusion per turn |
| 11 | Planning | **Built** | `src/planner/` |
| 12 | Response | **Built** | `src/response/` |

Nine of twelve layers exist. The three that don't — Personal Operating
Model, Need State Inference, Synthesis — are exactly the layers that
require **inventing a scored model** (psychological dimensions, a
need-state vector, or a fusion of multiple reasoning perspectives) with
no evidence yet to calibrate it against, which this codebase has
correctly refused to build before real usage existed to learn from. That
refusal was right at the time. It's worth revisiting now specifically
because real usage has started (see the Learning
discussion this document formalizes).

---

## 3. What Instrumentation would need first

`src/instrumentation/usage.py` today records exactly one thing: LLM
call cost/latency/reliability. It has no concept of a **behavioral
event** — "a Decision resolved," "a Goal's status changed," "a
stagnation signal crossed threshold" — even though `src/state/builder.py`
already computes several of these as part of normal WorldState updates.
Nothing persists them past the session's own WorldState.

This is the actual, concrete gap standing between "Learning is a named,
reserved slot" and "Learning has something real to learn from." Building
any Learning logic before this exists would mean inventing patterns from
nothing — precisely what the existing spec warns against.

---

## 4. Phasing

### Phase 0 — done
The current Sensemaking Engine (Interpretation → WorldState → Judgment →
Planner → Response), System Architecture v2's Orchestrator/
Instrumentation/Executor, and this session's three reasoning-depth
increments (salience, provenance, stagnation). Single-conversation scope
throughout — nothing here persists across Journeys yet.

### Phase 1 — proposed next: Memory Store + Learning's first real slice

Scoped to exactly one thing from the vision's nine-system Personal
Operating Model: the **Behavioral Pattern System**
(`Confidant_Personal_Operation_Model.docx`'s own example — `{pattern,
confidence, evidence_count, evidence}`), because it's the one system
that's a direct generalization of work already shipped
(`compute_stagnation_signals` already does evidence-counted, mechanical
pattern detection — just scoped to one Journey instead of across them).
The other eight systems (Identity, Motivation scored against
Self-Determination Theory dimensions, Belief, Relationship, Learning,
Stress, Narrative, Theory of Mind) require inventing scored psychological
dimensions with no evidence behind them yet — explicitly **not** in this
phase.

Concretely:

1. **Instrumentation gains one new, small responsibility**: recording
   discrete behavioral events (decision resolved, goal status changed,
   stagnation threshold crossed) as they already happen inside
   `update_state`/`apply_judgment_resolutions` — observation only, no
   interpretation, consistent with Instrumentation's existing non-goal
   ("It observes; it does not evaluate or act").
2. **A new Memory Store**: an append-only, per-user (not per-session)
   log of those events — separate from WorldState, which stays
   per-conversation. This is the "Layer 3" from the mapping above,
   scoped to exactly the events Phase 1 needs, not a general-purpose
   store.
3. **Learning runs asynchronously, never inside a live turn** (per the
   existing spec's non-goal), reading the accumulated event log and
   computing simple, evidence-counted patterns in the same mechanical,
   non-invented style as `compute_stagnation_signals` — with a hard
   minimum evidence floor (e.g. no pattern surfaces below
   `evidence_count = 3`) so a single data point can never be reported as
   a pattern.
4. **Learning's output feeds forward, never writes live state**: per the
   existing non-goal, its output becomes external input to a *future*
   Interpretation call or WorldState-seeding step — Learning itself
   never edits an in-progress WorldState.
5. **First real product surface**: `interaction-model-v4.md`'s "Quiet
   Discovery" moment currently has two tiers — one buildable today from
   a single Journey's own accumulated understanding (built), and
   "something noticed across Journeys," explicitly deferred pending
   Learning. Phase 1 is exactly what unlocks the second tier — no new
   frontend design work needed beyond wiring it to real data once it
   exists.

### Phase 2 — done for Insight Engine + Retrieval; Need State Inference still open
Insight Engine (`src/insight/engine.py`) shipped and is now wired live
via Retrieval (`src/retrieval/engine.py`, `engine/decisions.md`
"Retrieval"). Need State Inference has not been attempted -- it's the
one Phase 2 item that requires inventing a scored need-state vector with
no evidence yet to calibrate it against, the same risk this document
warns against everywhere else. Until it exists, Retrieval stays
unfiltered/surface-everything rather than need-aware, by design (see its
own module docstring).

### Phase 3 — Counseling modes shipped a scoped preview; full fusion still gated
Multi-perspective Judgement + Synthesis (the vision's five coaching
lenses — Strategic Advisor, Accountability Coach, Mentor, Supportive
Companion, Socratic Guide) remains unbuilt as originally envisioned (a
per-turn fusion across lenses). Counseling modes
(`src/orchestrator/modes.py`) shipped a deliberately narrower version --
one fixed lens chosen once per Journey, biasing Planner/Response prompts
-- not per-turn multi-perspective fusion. Full fusion directly attacks
the original "sounds like a regular LLM" complaint, and is honestly
testable against the existing eval harness
(`experiments/confidant-validation/`) — run single-pass Judgment against
fusion Judgment on the same transcripts and compare, mirroring the
vision doc's own "Fusion Cost Tracking" idea (quality lift vs. added
cost, measured, not assumed). Unlike Need State Inference/Personal
Operating Model, this doesn't require inventing an unevidenced scoring
system first -- it can be attempted and measured directly.

### Explicitly not scoped by this roadmap
The sponsor/organization layer, SOC2/ISO27001/SAML/investor-dashboard
apparatus, physiological/wearable/calendar/task-app signal ingestion,
client-side E2EE key management. Not because they're bad ideas — because
building them now would invent infrastructure for a business and user
base that doesn't exist yet. Revisit if/when there's an actual
organization customer or investor process that needs them.

---

## 5. One idea worth adopting immediately, independent of phasing

`Confidant_Data_Security_Architecture.docx`'s explainability requirement
— every inference carries `{statement, confidence, evidence, evidence_count}`
— is already this project's instinct (`stagnation_notes`, WorldState
provenance) without being a formally named, universal pattern. Worth
keeping explicit as new fields get added, not new work on its own.

---

## 6. Verification plan for Phase 1, when scoped for real

Same discipline as every prior round: full test suite, a live dispatch
against the real pipeline (multi-session, since this is the first
component that spans more than one conversation), and an honest write-up
in `engine/decisions.md` — including a check for the failure mode this
document explicitly guards against: Learning inventing a pattern that
isn't really there. A `evidence_count` floor is necessary but not
sufficient; the live verification pass should include at least one case
designed to confirm Learning stays silent when evidence is thin, not
just that it speaks up when evidence is strong.
