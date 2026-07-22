Confidant Product Risks & Design Principles v1

Status: SPEC ONLY, but a different kind of document than the other five
in this set. Written from the founder/CPO memo "Product Risks & Design
Principles for Confidant" (2026-07-22). This is not a new capability
spec -- it is a governing evaluation lens the other five specs
(`clarity-brief-specification-v1.md`, `insight-generation-specification-v1.md`,
`understanding-feedback-signals-specification-v1.md`,
`counseling-modes-frameworks-specification-v1.md`,
`programs-specification-v1.md`) must be checked against, both now and at
every future rollout step. Grounded against the actual current frontend
(`frontend/app/src/`) to establish, concretely, which parts of these
three risks the codebase already guards against versus where the newest,
least-built work (Insight Engine, Programs) is the real exposure.

---

Purpose

Three strategic risks, restated from the memo, each paired with a design
principle: Over-Intellectualization (the architecture must stay invisible
to the user), Too Many Product Abstractions (the user's mental model
should stay to three outcomes: Conversation, Progress, Self-Understanding
-- not this codebase's own module boundaries), and Missing the Signature
Insight (accumulated understanding, not conversation quality alone, is
the intended long-term moat). None of these are new work items in the
sense the other five specs are -- they are a lens applied TO that work,
now and at every future review.

---

Risk 1: Over-Intellectualization

**Design principle**: the product should feel simpler than the
architecture. Every new capability should reduce user effort, not
increase it.

**Grounding in this codebase (confirmed, not assumed)**: this discipline
already exists and is already enforced, not a new ask. A direct audit of
`frontend/app/src/` (every user-visible string, not comments or variable
names) found zero occurrences of "Judgment," "Planner," "Tier 1," "Tier
2," "Clarity Brief," "Personal Operating Model," "POM," "Learning
Engine," or "Insight Engine" rendered anywhere a user sees it:

- `Understanding.svelte`'s section headers are "Where things stand,"
  "What matters here," "Putting it together" (this is Tier 2's actual
  rendered name), "Still uncertain," "In play" -- never "Tier 1/2."
- `BehavioralPatterns.svelte` (Learning's actual surfaced UI) headers
  with "Patterns," not "Learning System" -- copy reads "Things noticed
  across your Journeys, purely by counting -- never a diagnosis."
- `Activity.svelte` renders Insight Engine output as "This has come up
  before, too. {detail}" -- a code comment there explicitly documents
  "no 'Insight:' label" as a deliberate choice, not an oversight.
- `PersonalOperatingModel.svelte` never uses "POM" or "framework" in
  visible copy -- "A standing sense of you, built up across every
  Journey," "What seems to drive you," etc.
- `Settings.svelte`'s toggle comment explicitly documents that the
  underlying systems it gates ("Learning/Insight Engine/POM") must never
  leak into the toggle's own visible label.

**What this means for the five specs in progress**: this principle is
not a new requirement to design FOR -- it is an existing, working
discipline to hold the newest work to. The exposure is concentrated in
exactly the two specs with the least existing code to keep them honest:

- **Insight Generation spec, Open Question 1 (surfacing location)**:
  whatever answer is chosen for where Insight Engine's synthesized
  observations surface, the rendered copy must follow the same pattern
  as `Activity.svelte`'s existing "This has come up before, too" --
  never a labeled "Insight Engine says..." card. Worth stating this
  explicitly in that spec's own rollout, not assuming it'll be caught
  in review.
- **Programs spec**: the biggest new surface risk in this whole set,
  because it's the one net-new tab-level concept. "Program," "stage,"
  and "experiment" are already being used as visible UI words in that
  spec's own worked examples (e.g. "Frame -> Explore options -> Test
  assumptions...") -- these need the SAME casual-language treatment
  Understanding and BehavioralPatterns already got (a stage probably
  shouldn't be *labeled* "Stage 2 of 6" any more than Understanding
  labels anything "Tier 1"). This is a new open question for that spec,
  not yet asked there (see below).

---

Risk 2: Too Many Product Abstractions

**Design principle**: the user's mental model should revolve around
exactly three outcomes -- Conversation ("help me think"), Progress ("help
me move forward"), Self-Understanding ("help me understand myself
better"). Every feature maps to one of these three; none requires the
user to learn a new internal concept to use it.

**Grounding in this codebase**: the current five-tab navigation (You,
Activity, +, Plans, Settings) already maps cleanly:

| Tab | Outcome |
|---|---|
| + (start a Journey) | Conversation |
| Plans | Progress |
| You, Activity | Self-Understanding |
| Settings | (none -- utility, not a fourth outcome) |

This mapping is worth stating explicitly because it is the actual test
for whether a future tab, sub-screen, or new terminology is warranted:
if a proposed feature doesn't cleanly extend one of the three rows
above, that is itself signal the feature needs to be reframed or folded
into an existing surface rather than getting its own new destination.

**Applying this to the five specs**:

- **Programs is the one spec that adds new terminology the user must
  learn** ("Program," "Program Type," "stage," "experiment," "review").
  This is the direct tension with this risk, and it is not resolved by
  this document -- it's the reason "Program" as end-user-facing language
  needs the same scrutiny "Journey" itself presumably went through
  originally. Concretely: does a user need to understand the word
  "Program" as a category, or can Plans just show "Career Move" and
  "Speaking Up at Work" as named things-in-progress, with "Program"
  staying an internal/architectural noun the way "WorldState" already
  is? Recommend adding this as an explicit open question to the Programs
  spec (see below) rather than assuming the founder's own memo language
  ("Decision Program," "Confidence Program") is meant literally as
  user-visible copy.
- **Clarity Brief, Insight Generation, Understanding Feedback Signals,
  Counseling Modes** all extend EXISTING surfaces (the Brief, You/
  Activity tabs, the Journey-close reflection card, mode selection) --
  none of the four introduce a new tab or new top-level concept. They
  pass this risk's test structurally, by construction, not by add-on
  discipline.
- The Journey End Survey (Feedback Signals spec) is worth double-
  checking against this risk specifically: three explicit questions at
  Journey close is the correct minimal surface already (per that spec's
  own "journey-close, not per-turn" framing), but if implementation ever
  grows past three questions, that growth is itself the anti-pattern
  this risk warns against -- worth naming as a hard ceiling, not just a
  starting point.

---

Risk 3: Missing the Signature Insight

**Design principle**: the product should actively generate "I hadn't
realized that" / "that's exactly what I keep doing" moments, tracked as
a first-class product goal -- not a side effect of Judgment/Learning/
Insight Engine functioning correctly, but a thing the product explicitly
tries to produce and can be measured on.

**This is not actually a new capability request** -- it's a reframing of
work already scoped in `insight-generation-specification-v1.md`, plus one
real gap. Checking the memo's four candidate areas against that spec's
existing category table:

| Memo's candidate area | Insight Generation spec status |
|---|---|
| Recurring decision patterns (autonomy > compensation; over-researching past clarity) | **Already scoped** -- this is that spec's own worked example almost verbatim ("Decision-making tendencies," "Repeated tradeoff patterns, synthesized form"). |
| Recurring tradeoff patterns (security vs. growth, stability vs. freedom, harmony vs. honesty) | **Already scoped** -- "Repeated tradeoff patterns, raw form," same Learning-layer mechanism. |
| Recurring relationship patterns (conflict avoidance across unrelated situations; over-owning outcomes outside one's control) | **Partially scoped.** "Recurring avoidance patterns" is already a Learning category, and conflict avoidance is its own named example there -- but "assumes responsibility for outcomes outside your control" is a genuinely distinct pattern shape (a locus-of-control tendency, not an avoidance tendency) not currently in that spec's table. |
| Recurring growth patterns (action creates confidence more reliably than preparation; reflection produces insight but experiments produce change) | **Not scoped.** This is a real gap -- no existing Learning category captures a pattern about WHAT KIND OF ACTIVITY correlates with a person's own reported change over time. This would need Program data as an input (an "experiment" outcome, per the Programs spec) as well as session content, which is a new cross-cutting dependency neither the Insight Generation spec nor the Programs spec currently names. |

**Recommendation**: add "recurring growth patterns" and sharpen
"recurring relationship patterns" (splitting the locus-of-control shape
out from avoidance) as two more entries in
`insight-generation-specification-v1.md`'s existing category table --
additive, same `MIN_EVIDENCE`-gated mechanism as every other category
there, no new architecture beyond what that spec already proposes. The
one real new dependency worth flagging explicitly: "growth patterns"
being genuinely evidenced requires Program experiment outcomes as an
input, which means Insight Engine's new input path (already scoped to
read Learning's patterns) may eventually need a second new input path
reading Program history too -- worth noting now, building later, once
Programs itself ships and has real data to synthesize from.

**The direct, already-built connection to measurement**: Journey End
Survey question 3 -- "Did Confidant surface anything important?
Yes/No" -- IS a signature-insight detector, already decided in the
Feedback Signals spec, just not yet framed that way. Recommend explicitly
tagging this in that spec: when Q3 is answered Yes, that Journey's
transcript becomes a labeled candidate for "what made this feel like a
signature insight" review -- the same aggregate-reporting mechanism
that spec already proposes (signal type 3), just with this one question
elevated to its own tracked rate over time, not buried as one of three
equally-weighted rows. This is the closest thing to a "signature insight
success metric" this product can measure without inventing a new
instrument.

**Long-term product test, applied concretely to the current five specs**:
"what becomes dramatically better after six months that cannot exist on
day one?" -- Insight Engine's synthesis step and Programs' persistence
across Journeys are the only two of the five specs that pass this test
structurally (both require accumulated history to produce anything at
all). Clarity Brief, Feedback Signals, and Counseling Modes are all
valuable but are NOT compounding in this sense -- they work identically
on day one and month six. This isn't a reason to deprioritize them (a
better Brief and better mode differentiation are real, immediate value),
but it is a reason Insight Engine and Programs deserve to be treated as
the actual long-term moat work, and resourced/protected as such if
tradeoffs have to be made between this set of five.

---

Non-Goals

- This is not a rewrite mandate for any of the five specs. Two small,
  additive amendments are recommended above (two new Learning category
  rows in Insight Generation; two new open questions in Programs) --
  everything else in this document is an evaluation lens applied going
  forward, not a change to what's already been decided.
- Not a claim that Risks 1 and 2 are currently failing. The audit above
  found the opposite for existing surfaces -- these principles are
  already real, working discipline in this codebase. The risk is
  entirely in NOT extending that same discipline to the newest,
  as-yet-unbuilt surfaces (Programs, Insight Engine's new surfacing
  location), where there's no shipped code yet to keep it honest by
  construction.
- Not a new scoring system, dashboard, or KPI framework. Risk 3's
  "signature insight" tracking recommendation reuses the Feedback
  Signals spec's own already-decided Journey End Survey question rather
  than proposing a new metric or instrument.

---

Open Questions

1. **Should "Program" be user-visible language at all**, or should Plans
   show only named instances ("Career Move," "Speaking Up at Work")
   with "Program" staying an internal/architectural noun -- the same
   relationship "Journey" has to "WorldState" today? This should become
   an explicit open question added to `programs-specification-v1.md`
   itself, not just live here.
2. **Should Program stages be user-visible as a labeled sequence**
   ("Stage 2 of 6") or rendered the same prose-only way Understanding
   and the Brief already are ("no progress bars," already a decided
   principle in the Clarity Brief spec)? Same answer likely applies:
   no numbered stages, prose only -- but worth confirming as a decision
   rather than an assumption, since Programs is the one spec where a
   numbered-stage UI is a very natural default to reach for.
3. **Does elevating Journey End Survey Q3 into a tracked "signature
   insight rate" require anything more than a reporting-layer change**
   (Feedback Signals spec's signal type 3), or does it also want a
   qualitative review step (a human actually reading the flagged
   transcripts periodically)? If the latter, that's a process
   commitment, not a code change, and worth naming as such rather than
   assuming instrumentation alone answers the founder's actual question.

---

Rollout

1. Add the two recommended category rows (recurring growth patterns,
   sharpened recurring relationship patterns) to
   `insight-generation-specification-v1.md`'s existing table, flagging
   growth patterns' new Program-history input dependency as a forward
   reference to Programs, not something to build until Programs itself
   ships real data.
2. Add Open Questions 1-2 above to `programs-specification-v1.md`
   directly, since they are genuinely that spec's open questions, not
   just this document's.
3. Add the Q3-elevation recommendation to
   `understanding-feedback-signals-specification-v1.md`'s existing
   signal-type-3 rollout step, as a labeling/reporting change only.
4. Treat this document itself as a standing checklist: any future spec
   added to this set should include a short explicit section (as this
   document models for the existing five above) checking itself against
   all three risks before being considered complete, the same way every
   spec here already includes a Non-Goals section as standard practice.
