# Judgment v2 Evaluation Design

**Status:** DESIGN ONLY. No code, no harness, no experiment has been run.
This document is the methodology to be reviewed and approved before any
of it is built.

**Research question:** Does reasoning over a structured, persistent
WorldState produce better judgments than reasoning directly over raw
conversation — and does that hold independent of which underlying LLM
does the reasoning?

---

## 1. The One Principle Everything Else Depends On

**Model invariance.** Every condition being compared must use the *same*
underlying LLM, at the same temperature, for the actual Judgment-producing
call. If Confidant's Judgment uses `openai/gpt-4o-mini` via OpenRouter and
Baseline A uses a different model, any measured difference is confounded
— you can't tell whether WorldState helped or the other model is just
better. Confidant's existing provider layer (`src/llm/providers.py`,
`OPENROUTER_MODEL` env var) already makes this mechanically easy: every
condition's final reasoning call should go through the identical
`call_openrouter` path with the identical model pinned for the whole
study.

The corollary: **the output schema and system-prompt governance must also
be held constant across conditions.** Baseline A and B should be asked to
produce the exact same `Judgment` schema (`src/judgment/schema.py`), under
the exact same "MUST NOT coach/comfort/persuade/recommend/respond/ask
follow-ups" constraints as Confidant's actual system prompt — with only
the *input representation* (raw transcript vs. summary vs. WorldState)
changed. If Baseline A gets a looser prompt, differences could come from
prompt wording, not input structure. The only thing that should vary
between conditions is what the model is shown, not what it's asked to
produce or how it's asked to behave.

---

## 2. Experimental Conditions

### Baseline A — Raw conversation
Full raw transcript (all turns, verbatim) → single LLM call, same
`Judgment` schema/prompt-governance as Confidant → `Judgment`.
Represents "no memory architecture at all, just replay everything."

### Baseline B — Conversation summary
Two variants worth running separately, since they represent different
real alternatives to Confidant, not one thing:
- **B1 (fresh summary):** regenerate a plain-language summary from the
  *full* transcript every turn, then reason over that. Costs roughly the
  same as Baseline A (still reads everything each turn) but changes the
  *shape* of what the model reasons over.
- **B2 (incremental summary):** maintain one summary that's updated
  turn-by-turn (new message + old summary → new summary), never
  re-reading the full transcript. This is the closer real-world analog to
  WorldState's accumulate-don't-replay approach, but with a naive,
  unstructured, untyped summary instead of typed epistemic tiers — this
  is probably the single most informative baseline, since it isolates
  *structure* from *persistence* (Confidant has both; B2 has persistence
  without structure).

### Confidant — Full pipeline
Conversation → Interpretation → State Builder → WorldState → Judgment, as
implemented.

### Proposed additional baselines (ablations)

These aren't just "more baselines for coverage" — each isolates one
specific Confidant design bet, so a result like "Confidant beats Baseline
A" can be decomposed into *which part* of the architecture is doing the
work, rather than crediting "structure" as an undifferentiated whole.

- **Baseline C — Flat extraction, no tiers.** Extract facts/goals/etc.
  into one undifferentiated list per turn (no Facts vs. Claims vs.
  Assumptions vs. Inferences distinction), persisted the same
  accumulate-don't-replace way WorldState is. Isolates whether the
  *epistemic tier separation* specifically — the thing this project's own
  development history (`engine/decisions.md`) found essential for
  preventing advice/fact conflation during *extraction* — actually
  produces better *downstream judgments*, or whether that benefit stops
  at extraction quality and doesn't propagate.
- **Baseline D — WorldState, tiers collapsed.** Take the real, live
  WorldState objects Confidant produces, but flatten Facts/Claims/
  Assumptions/Inferences into one list before handing them to Judgment.
  A tighter ablation than C (same underlying extraction quality, only the
  presentation to Judgment changes) — isolates the tier-separation
  question with fewer confounds than Baseline C, at the cost of needing
  Confidant's real pipeline to already be running.

Recommend running the **core three (A, B2, Confidant)** first; add C and
D only if the core result shows a real gap worth decomposing further.
Don't build the ablations before knowing there's an effect to explain.

---

## 3. Evaluation Dimensions

Organized by what each one actually measures, with how it gets scored —
"objective wherever possible" per the brief, but a few are irreducibly
human-judgment calls, marked as such.

| Dimension | What it measures | How it's scored |
|---|---|---|
| **Groundedness** | Every conclusion traceable to real source content | Human/LLM-judge checks each `supporting_evidence` entry against the actual transcript/WorldState; % traceable |
| **Hallucination rate** | Conclusions asserting something not present anywhere in the source | % of claims in the Judgment with no supporting source content at all (stricter than groundedness — this is about the conclusion itself, not just its cited evidence) |
| **Stability across repeated runs** | Same input, same model → same conclusion | N repeated runs per (condition, conversation); field-level agreement rate + semantic-similarity variance on free-text fields |
| **Internal consistency** | Judgment's own fields don't contradict each other | Human rubric: does `confidence` match evidence density; does `primary_problem` align with `key_blockers`; do `risks`/`opportunities` contradict `active_decisions` |
| **Correct prioritization** | `primary_problem`/`primary_goal` match what's actually most important | Compare against pre-registered ground truth (synthetic) or adjudicated expert-panel gold label (naturalistic) |
| **Evidence traceability** | Can a reader verify a citation supports its conclusion, not just exists | Rubric score per evidence-conclusion pair, not just presence/absence |
| **Sensitivity to new information** | Judgment updates appropriately when new turns arrive | Track judgment deltas turn-over-turn on conversations with a planted informative event (e.g. a contradiction or resolution) at a known turn |
| **Recency bias resistance** | Doesn't overweight the most recent message vs. materially important earlier content | Planted-conflict conversations where an early fact matters more than a later, more recent but less important one; measure whether the later mention wrongly dominates |
| **Robustness to long conversations** | Quality doesn't degrade as length grows | Same dimensions above, measured across length strata (see §4), plotted as a function of turn count |
| **Preservation of important context** | An early important fact/goal survives to influence later judgments | Planted-fact-at-turn-1, check-for-presence-at-turn-N tests |
| **Constraint adherence** | Judgment never coaches/comforts/persuades/recommends/responds/asks follow-ups | Binary violation flag per output, rated against the spec's MUST NOT list; report violation rate per condition |
| **Contradiction detection** | Flags real conflicts, doesn't flag false ones | Precision/recall against planted contradictions (see §4) |
| **Cost & latency** *(secondary — not a quality dimension)* | Practical viability | Tokens + wall-clock per Judgment call, per condition |

---

## 4. Datasets

### Categories (topical diversity)
Career decisions, relationship conflicts, health-related uncertainty
(non-diagnostic), long-term personal projects, multi-session
conversations, ambiguous situations, contradictory information — all from
the brief. These aren't just topic variety; they stress different parts
of the architecture (health/relationship conversations tend to be
emotionally dense — good for testing constraint adherence; contradictory-
information conversations are the direct test bed for contradiction
detection; multi-session conversations test persistence specifically).

### Length strata (a second, orthogonal axis)
Short (3–5 turns), medium (8–12 turns), long (20+ turns or genuinely
multi-session). "Robustness to long conversations" can't be measured
without conversations actually varying in length as a controlled
variable, independent of topic.

### Synthetic vs. naturalistic
Recommend a **majority-synthetic, minority-naturalistic** mix:
- **Synthetic (constructed)**: needed for the stress-test categories
  where ground truth must be known precisely — planted contradictions,
  planted "this fact matters more than that recent one," a clearly
  intended primary problem. Ground truth is pre-registered by the
  conversation's author *at construction time*, before any condition is
  run against it, to avoid post-hoc rationalization of what the "right"
  answer was.
- **Naturalistic (real or realistic)**: smaller set, used to check the
  synthetic findings aren't an artifact of synthetic conversations being
  too clean/legible. Ground truth here comes from a panel of 2–3
  independent expert annotators reading the raw transcript *blind to any
  system's output*, producing their own gold judgment, with
  disagreements adjudicated by discussion — standard gold-label practice
  when there's no objectively verifiable answer.

**Role separation, stated explicitly**: whoever writes a synthetic
conversation's planted ground truth must not also serve as a blind
evaluator scoring that same conversation's outputs later — otherwise
their prior knowledge of "the intended answer" contaminates their
blind rating.

### How many conversations
Two-stage, not one number:
- **Pilot: 20–30 conversations** (3–4 per category, spanning all three
  length strata). Purpose isn't a confident conclusion — it's validating
  that the metrics actually discriminate between conditions at all, and
  estimating effect sizes/variance needed to properly power the full run
  (see §7). Committing to a large N before knowing whether the rubric
  even separates conditions is how you burn budget on a study that can't
  answer its own question.
- **Full run: 80–120 conversations**, sized from the pilot's observed
  effect size (see §7 for the reasoning), once the methodology is
  validated.

---

## 5. Metrics

### Quantitative
- **Agreement score**: Krippendorff's alpha (or Cohen's kappa for exactly
  2 raters) between independent evaluators scoring the same Judgment —
  measures rater reliability, a precondition for trusting any of the
  scores below.
- **Variance across repeated runs**: per (condition, conversation), N
  runs' pairwise semantic-similarity variance on free-text fields, and
  exact/near-match agreement rate on categorical-ish fields
  (`primary_goal`, `primary_problem`).
- **Precision/recall**: against planted ground-truth items (contradictions,
  key facts that must survive to later turns, the intended primary
  problem).
- **Hallucination frequency**: % of stated conclusions with no traceable
  source support (see §3).
- **Contradiction detection rate**: recall on planted contradictions
  specifically, separate from general hallucination rate.
- **Constraint-violation rate**: % of outputs violating the MUST NOT list.

### Qualitative
- **Human preference ranking**: blinded, randomized side-by-side ranking
  of same-conversation outputs across conditions (see §6) — "which of
  these is the most accurate, useful assessment of this person's
  situation?"
- **Expert evaluation**: for categories where domain judgment matters
  (health, relationship), a small panel of relevantly-experienced
  reviewers (not necessarily licensed professionals — reasonable
  adjacent expertise is enough for this purpose) rates realism/soundness
  on a Likert scale.
- **Explanation quality**: rubric score for whether `supporting_evidence`
  actually justifies its associated conclusion (not just whether it
  exists — a citation that's real but irrelevant should score low).
- **Actionability of downstream Planner inputs**: since Planner doesn't
  exist yet, operationalized as a proxy question to evaluators: "if you
  were about to decide what should happen next based only on this
  Judgment, would you need to go back and re-read the conversation?" A
  frequent "yes" indicates the Judgment isn't self-sufficient — a direct,
  practical stand-in for Planner-readiness until Planner is real enough
  to test against directly.

---

## 6. Blind Evaluation Protocol

1. **Single-blind minimum**: evaluators never see which condition
   produced a given Judgment. Labels are opaque IDs, mapped back to
   conditions only after all scoring is complete.
2. **Within-subject where possible**: the same evaluator rates all
   conditions' outputs for a given conversation, so their ranking is a
   direct comparison, not an absolute score compared across different
   people's separate scales.
3. **Randomized presentation order** per conversation, to control for
   position bias (evaluators anchoring on whichever output they read
   first).
4. **Duplicate-injection noise check**: occasionally show the same
   Judgment twice, under two different random IDs, without telling the
   evaluator. Disagreement between an evaluator's own two ratings of the
   literal same content measures rater noise directly — a real noise
   floor to compare condition-level differences against, rather than
   assuming all disagreement reflects genuine quality differences.
5. **At least 3 independent evaluators per conversation** (not 2) — gives
   a usable inter-rater reliability estimate and lets majority/median
   scoring resolve ties, rather than a single evaluator's idiosyncrasies
   deciding the result.

---

## 7. Failure Taxonomy

Organized into categories, each applicable equally to *any* condition
(baseline or Confidant) — the point is comparing architectures on the
same failure vocabulary, not describing Confidant-specific problems.
Every flagged failure gets a severity tag (minor/major/critical) so rates
are comparable across conditions, not just presence/absence.

**A. Grounding failures**
- Hallucinated conclusion — asserts something absent from all source material.
- Unsupported inference — a conclusion beyond what evidence reasonably supports, even if not outright fabricated.
- Evidence mismatch — cites real evidence that doesn't actually support the stated conclusion.

**B. Prioritization failures**
- Incorrect prioritization — wrong `primary_problem`/`primary_goal` against ground truth.
- Recency bias — overweights the most recent message vs. more materially important earlier content.
- Missing important context — fails to surface something clearly important that was stated.

**C. Consistency failures**
- Inconsistent reasoning — the Judgment's own fields contradict each other.
- Instability across repeated runs — same input, materially different output.
- Failure to integrate multiple facts — misses an implication that only follows from combining 2+ separate pieces of information.

**D. Calibration failures**
- Overconfidence — high `confidence` despite thin evidentiary support.
- Underconfidence — unnecessarily hedges despite strong, direct evidence. (Added as the natural complement to overconfidence — a calibration axis has two failure directions, not one.)

**E. Constraint violations**
- Role violation — coaches, comforts, persuades, recommends actions, addresses the user directly, or asks a follow-up question. Worth explicitly hypothesizing that baselines reasoning over raw, emotionally-laden conversation text may violate this *more* than Confidant, which reasons over already-depersonalized structured state — itself a testable prediction, not just a category to check off.

**F. Contradiction-handling failures**
- Missed contradiction — fails to flag two directly conflicting pieces of information.
- False contradiction — flags two compatible/complementary things as conflicting.

---

## 8. Statistical Confidence

Recommending concrete numbers, with the caveat stated plainly: these are
reasoned starting points for an early architecture-validation study, not
outputs of a formal power analysis (which needs a pilot's effect-size
estimate as input — that's exactly why this is staged).

- **Repeated runs per (condition × conversation): 3–5.** Enough to
  estimate stability/variance per condition without every conversation
  needing dozens of runs.
- **Evaluators per item: at least 3.** Below that, inter-rater
  reliability can't be meaningfully estimated, and a single evaluator's
  quirks can decide a result.
- **Conversations: pilot 20–30, full run 80–120** (see §4). For the
  *primary* comparison (Confidant vs. Baseline A, on a single headline
  metric like human-preference win-rate), 80–100 paired comparisons gives
  reasonable power (~80%, α=0.05) to detect a moderate effect
  (Cohen's d ≈ 0.3–0.5) using a paired test (e.g. Wilcoxon signed-rank on
  preference scores, or McNemar's test if the outcome is binarized to
  "Confidant preferred / not preferred").
- **Pre-register 2–3 primary metrics** before running the full study —
  recommend: overall human-preference win-rate, hallucination rate, and
  groundedness score. Treat every other dimension in §3 as *secondary/
  exploratory*, reported descriptively without claiming statistical
  significance on all of them individually. With ~13 dimensions and
  multiple conditions, testing every one at α=0.05 without correction
  would produce false positives by chance alone; either apply a multiple-
  comparisons correction (Bonferroni/FDR) across the full set, or (the
  more practical choice here) keep the confirmatory claims limited to the
  pre-registered primary metrics and clearly label the rest as
  hypothesis-generating for future rounds.
- **If more than 2 conditions are compared at once** (e.g. adding
  ablations C/D), either increase N accordingly or restrict formal
  statistical comparison to the primary pairwise contrast (Confidant vs.
  Baseline A) and report the rest as descriptive.

---

## 9. Stretch Goal — Cross-Model Design

Goal: decompose any observed benefit into an **architecture effect**, a
**model effect**, and (importantly) an **architecture × model
interaction** — i.e., does Confidant's benefit hold equally across
models, or does structured input help a weaker model much more than it
helps a strong one? That interaction, if present, would itself be a
significant and useful finding (e.g., "structure is a force-multiplier
for cheaper models" is a real, actionable product insight).

**Staged, not full factorial upfront** — a full grid of (Confidant,
Baseline A, Baseline B2) × (GPT, Claude, Gemini, DeepSeek, Qwen) is 15
conditions, each needing the full conversation set × repeated runs ×
evaluator treatment from the main study. That's not a proportionate next
step before the single-model result is even established.

1. **Stage 1 (this document's main design)**: establish the architecture
   effect with one pinned model — whatever `OPENROUTER_MODEL` already
   defaults to.
2. **Stage 2 (confirmatory generalization check)**: once Stage 1 shows a
   real effect, take the **two most differentiated conditions only**
   (Confidant vs. Baseline A — drop B2/ablations here) and re-run them
   across the additional models, on the **pilot-sized conversation set**
   (20–30, not the full 80–120) rather than repeating the full study per
   model. This checks whether the direction and rough size of the effect
   holds, without paying full-study cost N times.
3. **Effect decomposition**: for each model, compute
   Δ = (Confidant score − Baseline A score) on the pre-registered primary
   metrics. Consistent sign/magnitude across models is strong evidence
   the architecture's value is model-independent; large variation
   signals a real interaction effect worth its own follow-up study.
4. **Analysis**: a two-way ANOVA (architecture × model) if the data are
   well-behaved, or a non-parametric equivalent (e.g. Friedman test)
   given the likely small N per cell at this stage — report effect sizes
   with appropriate uncertainty rather than treating Stage 2 as
   confirmatory in its own right.

This is mechanically executable without new infrastructure: Confidant's
provider layer already resolves `OPENROUTER_MODEL` at call time (see
`src/judgment/providers.py`, `src/interpretation/providers.py`), so
switching models is a config change, not new code.

---

## 10. Open Decisions Before This Is Buildable

Flagging rather than deciding unilaterally, matching how the
Interpretation v1.1 proposal surfaced its own open questions:

1. **Who writes the synthetic conversations and their ground truth?**
   Needs a person (or people) who won't also serve as blind evaluators
   for the same items.
2. **Who are the qualitative evaluators** (general reviewers vs.
   domain-adjacent experts for health/relationship categories), and how
   many are actually available — the §8 numbers assume at least 3 are
   feasible per item across 80–120 conversations × 3 conditions, which is
   a real staffing commitment, not a trivial one.
3. **Automated groundedness/hallucination checking**: using an LLM-judge
   to check evidence citations against source text is far cheaper than
   all-human annotation, but has its own validity concerns (a judge model
   can itself hallucinate a "yes, this is grounded" verdict). Recommend
   spot-checking the LLM-judge against human ratings on a subsample
   before trusting it at scale — not deciding this unilaterally here.
4. **Budget/scale**: pilot (20–30 convos × 3 conditions × 3–5 runs) is a
   few hundred real LLM calls; the full run (80–120 × 3 × 3–5, plus
   Stage 2's cross-model check) is meaningfully more. Worth sizing actual
   cost before committing to the full-run number in §8.

---

## Summary

Pilot first (20–30 conversations, 3 core conditions, validate the
methodology and estimate effect size) → full run (80–120 conversations,
pre-registered primary metrics, proper blind multi-evaluator scoring) →
only then the cross-model generalization check, reusing the pilot-sized
set rather than repeating the full study per model. Ablation baselines
(C/D) are held in reserve, added only if the core result shows an effect
worth decomposing further. Nothing above has been implemented or run.
