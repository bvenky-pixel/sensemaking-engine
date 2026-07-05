Every major product insight gets one entry. For example:
Why understanding comes before reasoning.
Why judgment is owned by the user.
Why Confidant models thinking instead of generating advice.
Why conversation is the interface, not the product.

---

**2026-07-02 — Interpretation schema mirrors the constitution's Method vocabulary**

The Interpretation schema was previously generic NLP terms (propositions,
hypotheses, salience). Rewrote it so every field maps to a specific line
in The Constitution of Confidant's Thinking Method: urgency/stakes
(Phase 1 Prepare), surface_complaint/core_question (Phase 2 Discover),
facts/assumptions/interpretations/unknowns/biases (Phase 3 Discern). If a
field can't be traced to the doc, it doesn't belong in the schema. This
also closed a real gap: `assumptions` existed on ConversationState but
was never populated, because Interpretation had nowhere to put it, and
`biases` (Principle 8) had no representation anywhere in the code.

**2026-07-02 — State merges, never overwrites**

`update_state` was replacing facts/assumptions/interpretations/unknowns
wholesale on every turn instead of accumulating them. This directly
undercut Principle 4 and Phase 3's success criterion, which depend on a
person being able to look back at an assumption they raised turns ago.
Fixed to merge-append with dedup, and to reconcile unknowns against newly
stated facts. The unknown-reconciliation is a naive substring check for
now -- flagged as likely too blunt once real conversations hit it.

**2026-07-02 — Ollama stays for MVP, Claude swap deferred deliberately**

Chose Ollama (llama3.2:3b) over the Claude API for now to keep iteration
free while the schema is still moving. Because a 3B local model is much
less reliable at nuanced extraction (bias detection, fact-vs-assumption
separation) than Claude's structured outputs, hardened the interpretation
call: switched from the flat-string /api/generate hack to real
/api/chat with a proper system field, forced `format: json`, low
temperature (0.15), and explicit error handling instead of a bare
json.loads(). Added few-shot examples in the prompt for assumption/bias
extraction specifically because those are the hardest catches and the
constitution itself gives us near-verbatim example phrasing to use.
`engine/state_updater.py` (Claude + structured outputs) is being kept in
sync with ConversationState's fields as the intended swap target -- when
we move off Ollama, that's the pattern to extend rather than rebuild.

**2026-07-02 — Added `phase` to ConversationState**

The Method is staged (Prepare -> Discover -> Discern -> Challenge ->
Resolve -> Commit) with named success criteria per stage. Without a
`phase` field there was no way to know where a conversation stood or
whether it should move forward. `run_judgment` now recommends phase
transitions based on those success criteria (e.g. Discover -> Discern
once core_question_confidence clears a threshold). Challenge/Resolve/
Commit are undrafted in the constitution (Draft 0.1) -- state supports
those phase values so we don't have to touch the schema again later, but
no transition logic was written for them. Don't build that logic ahead of
the doctrine that's supposed to define it.

**2026-07-02 — Ollama format param: pass the real JSON schema, not just "json"**

`"format": "json"` only forces syntactically valid JSON -- it has no idea
what shape we want, so llama3.2:3b was free to invent its own keys (we
saw it return a single sentence-as-key mapped to 1.1). Since Ollama
0.3.0, `format` accepts a full JSON schema and constrains generation via
grammar, the same idea as Claude's structured outputs already used in
engine/state_updater.py. Switched to `format: Interpretation.model_json_schema()`.
Worth watching for: small models can still struggle with schemas nested
3+ levels deep (ours nests one level -- EmotionalSignal/Assumption/Bias
lists inside Interpretation -- which should be within llama3.2:3b's
range, but if extraction quality stays poor even with grammar
constraints, the schema itself may need flattening, not just constraining).

**2026-07-02 — Interpretation redesigned as strictly evidence-based (forensic analyst, not therapist)**

First real end-to-end run surfaced the core failure mode: Interpretation
was leaking advice, generic self-help content, world knowledge, and
unstated psychoanalysis into facts/interpretations ("Toxic bosses can
have serious negative impacts on mental health", "Consider speaking with
HR", literal stray labels like 'supporting_resources' and 'next_steps'
showing up as list items). This directly violates constitution
Principles 10 and 14 -- and it was happening in the one layer whose job
is explicitly to not do that.

Redesigned around one architectural tenet, which should be treated as
foundational going forward: **the quality of Judgment is bounded by the
quality of Interpretation.** Judgment should never have to ask "did this
come from the user or from the model?" -- Interpretation's contract is
to have already resolved that distinction.

Concrete changes:
- `interpretations` changed from List[str] to List[InferredReading],
  each with a required confidence. An interpretation without a
  confidence is treated as a fact wearing a costume.
- Facts and interpretations must be phrased as evidence statements about
  what the user said/did ("User describes boss as toxic"), never as
  claims about the world ("toxic bosses hurt mental health").
- Rewrote prompt.py entirely around a forensic-analyst frame with an
  explicit golden rule ("can this be reasonably supported by evidence in
  the conversation?"), an allowed list, a forbidden list with bad/good
  examples, and instructions to leave a field empty rather than fill it
  with something generically true or generically helpful.
- Added a confidence floor (0.5) in state/builder.py: interpretations
  below it don't get promoted into ConversationState at all. This is a
  real design bet, not a formality -- worth revisiting once real
  conversations show whether 0.5 is too aggressive or too permissive.

Judgment, Planner, and Response as named layers (Planner/Response don't
exist yet) are referenced in this framing for future work -- don't build
them ahead of a spec for them the way we're deliberately not building
Challenge/Resolve/Commit phase logic ahead of the constitution drafting
them.

**2026-07-02 — Epistemic tiers: split "facts" into Observed Facts, Claims, Assumptions, Inferences, Unknowns**

Testing surfaced a subtler version of the earlier advice-leakage problem:
even with the evidence-first prompt, a single "facts" bucket let the
model collapse different kinds of knowledge into one representation --
e.g. the user saying "toxic" got silently upgraded to a fact called
"emotional abuse." A single bucket has no way to represent "this is what
the user said" vs "this is what the user believes" vs "this is my read
on it" as different things, so the model kept finding ways to blur them.

Restructured Phase 3 into five explicit tiers instead of one:
  Evidence -> Observed Facts -> Claims -> Assumptions -> Inferences -> Unknowns
- Observed Facts: meta-level record of what was explicitly said
  ("User says boss is 'toxic.'")
- Claims: the user's asserted belief, stripped of the "user says"
  wrapper but never escalated beyond their actual words ("Boss is
  toxic." -- not "boss is abusive")
- Assumptions: beliefs implied but NOT stated outright (this used to
  overlap with a `stated_as_fact` flag on the old Assumption model;
  dropped that flag since the tier itself now carries the distinction)
- Inferences (renamed from "interpretations" to match this framing):
  the model's own read, always with confidence
- Unknowns: unchanged

Architectural principle worth keeping going forward: **Interpretation
must never flatten different kinds of knowledge into the same
representation.** A user statement, a user belief, and a model inference
are different epistemic categories and the schema should make that
structurally impossible to blur, not just discourage it via prompt
wording.

Real risk flagged, not hidden: five tiers is a meaningfully harder
extraction task for llama3.2:3b than two. If quality degrades (tiers
start overlapping, or the model stops populating some tiers reliably),
that's a sign this schema may have outgrown what a 3B local model can
do well, and is a legitimate trigger to reconsider the Claude swap
timeline rather than a code bug to keep patching around.

**2026-07-02 — Confidence/intensity values need before-validation normalization, not just prompt instructions**

Even with `Field(ge=0.0, le=1.0)` present in the schema passed to
Ollama's `format` param, the model returned 0-10 scale integers (6, 8,
etc.) that sailed past grammar constraints and only failed at Pydantic
validation. This confirms Ollama's schema-constrained generation enforces
type/structure but not numeric min/max bounds -- worth remembering for
any future numeric field. Added `field_validator(mode="before")` on every
confidence/intensity field that rescales any value >1 by /10, plus an
explicit "SCALE: decimal 0.0-1.0, not 0-10" line in the prompt as
reinforcement. The validator is the real fix; the prompt line just
reduces how often it has to fire.

**2026-07-02 — Prompt hardening pass: fabricated claims, veiled advice in assumptions, padded inferences, bias-evidence fabrication**

A real test transcript ("should I leave or stay" re: a boss blocking a
team move) surfaced four new leaks, all variations on the same root
problem from earlier passes -- the model finding a new tier to hide
unearned content in once the previous leak was closed:
- Claims tier: the model's own opinion ("pivoting is a good idea for
  your career") asserted as if the user said it.
- Assumptions tier: speculative forecasts in second person ("if you
  leave, you will find a better opportunity") -- this is advice wearing
  an Assumption costume, arguably worse than the original leak since
  Assumptions is a tier meant to be trustworthy by construction.
- Inferences tier: restating an observed fact with a confidence number
  stapled on, adding no actual interpretive value.
- Biases: evidence field was a model-composed paraphrase, not the user's
  actual words, and the identical evidence string was reused for two
  different biases -- a structural tell of fabrication.

Fixed with two layers, matching the pattern established for the
confidence-scale bug (prompt + code, not prompt alone):
- Prompt: added the specific bad/good pairs above, pulled directly from
  the failing transcript rather than invented examples.
- Code (Interpretation.model_validator, mode="after"): dedupe biases
  that share identical evidence text (keep first occurrence only), and
  strip possessive pronouns from entities ("your boss" -> "boss"). These
  hold regardless of whether the model follows the prompt.

Noting explicitly for the record, since it matters for the eventual
Claude-swap decision: this is now the third consecutive round of
"harden the prompt, a new leak appears in a different tier." That
pattern itself is informative -- see decisions.md 2026-07-02 "Ollama
stays for MVP" for the plan to keep iterating here until output quality
is trusted, at which point the Claude swap should be evaluated against
these exact same failure modes as the test suite, not just vibes.

**2026-07-02 — v0.6: Intent/Goals tier, confidence calibration, bias rarity, "empty over invented"**

Direct feedback on a real test transcript (framed as architecture
guidance, credited to the person's own review process alongside ChatGPT
as philosophy/architecture guide) drove this round:

- **New tier: Goals** (`goals: List[str]`), inserted between Claims and
  Assumptions. Motivations ("user wants to move to the product team")
  are a genuinely distinct epistemic category from facts, claims, or
  assumptions -- they answer "what is the user trying to achieve," not
  "what do they believe" or "what did they say." This is expected to
  become useful for a future Planner layer.
- **Claims tightened on two axes**, not just one: don't convert a
  preference into an objective value judgment ("user wants to move" not
  "moving is a good idea"), AND don't round specific evidence down to
  something vaguer than what was said ("boss keeps sidestepping" ->
  "repeatedly avoided giving a clear answer," not "unknown reasons").
  Both are the same underlying rule -- match the evidence exactly, don't
  add or subtract from it -- but the first failure mode was escalating
  and the second was flattening, so both directions needed examples.
- **Assumptions**: replaced the forecast-based bad examples with a
  clearer positive example grounded in causal belief ("he's blocking my
  career" -> "user believes boss is intentionally preventing career
  growth") alongside the existing "no future-branch speculation" rule.
- **Biases made deliberately rare**: explicit guidance that biases=[] is
  the correct, expected output ~95% of the time, and that reaching for a
  named bias because a situation "sounds like" a textbook case (e.g.
  optimism/hindsight bias from one paragraph) is exactly the pattern-
  matched labeling to avoid. Single-turn text rarely has the
  longitudinal evidence a real bias claim needs.
- **Confidence calibration got explicit bands** (0.7-1.0 direct
  statement, 0.4-0.6 clear pattern, 0.1-0.3 weak/ambiguous cue) instead
  of just "be honest." A plausible-sounding psychological read from one
  paragraph is evidence-thin by definition and belongs at 0.2-0.3, not
  0.9 -- confidence reflects evidence strength, not how convincing the
  guess sounds.
- **Stakes**: short grounded category labels ("career transition"), not
  narrative elaboration ("career advancement and job satisfaction") that
  smuggles in unevidenced implications.
- **Golden Rule 2 added**: an empty field is preferable to an invented
  one, stated explicitly rather than left implicit, since the model's
  default "try to be helpful by filling every field" impulse is the root
  cause underneath every leak we've hit so far, across every tier.

**Follow-on bug this surfaced and fixed**: the v0.4 inference confidence
floor (0.5, for promoting inferences into ConversationState) was set
when the problem was over-confident fabrication. Under v0.6's proper
calibration, a correctly-scored weak read (0.2-0.3) is now the CORRECT
output for thin evidence -- but the 0.5 floor would have silently
discarded exactly that signal, working against Golden Rule 2 instead of
with it. Lowered to 0.15 (filters near-zero noise, trusts the model's
own inclusion decision as the real filter). Worth remembering as a
pattern: a threshold tuned to fix one failure mode can become wrong once
a later fix changes what "correct" output looks like -- revisit
thresholds whenever the thing they're filtering changes meaning.

**Framing worth keeping**: this session's characterization of what's
being built -- "preserving the epistemic provenance of every piece of
information, not flattening everything into context" -- is a good
compact description of why this schema is shaped the way it is, and
worth keeping in mind for any future layer (Planner, Response) so they
don't quietly re-flatten what Interpretation worked to keep separate.

**2026-07-02 — v0.7: Decision Options tier, "sparse by default" as governing law, code-level backstops for bias fabrication and confidence calibration**

Joint review (this codebase's own testing + external architecture review,
both converging independently on the same diagnosis) identified a
pattern across three consecutive rounds: prompt tightening was
demonstrably NOT holding for two specific failures -- bias-evidence
fabrication and inference confidence calibration -- even when the prompt
included an almost word-for-word negative example of the exact failure
(e.g. "optimism bias" named as the textbook bad example, then produced
anyway on the next real run). That's meaningfully different information
than earlier rounds, where tightening visibly narrowed the leaks. When a
prompt fix demonstrably fails to hold across repeated identical tests,
the fix belongs in code, not in more words.

**New tier: Decision Options** (`decision_options: List[str]`). The
prior version's Claims tier was absorbing the options a user is
literally weighing ("should I leave or do something else?" -> claims:
["leaving the company", "doing something else"]) -- but an option under
consideration is not an assertion of truth, it's a different epistemic
category entirely. Added as its own tier, grouped with Observed
Facts/Claims/Goals under "Evidence" conceptually (all four are directly
traceable to what the user said), distinct from the "Reasoning" tier
(Assumptions/Inferences) and "Metacognition" (Biases).

**"Sparse by default" elevated to an explicit governing law**, stated at
the top of both the schema docstring and the prompt: every tier starts
empty; a good Interpretation object has the LEAST unjustified
information, not the most. This reframes what "correct" looks like --
previously the prompt only said "don't invent," which still frames
empty as a failure to fill in. Stating sparsity as the default,
not a fallback, is a different instruction than "try not to guess."

**Two code-level backstops added**, because prompt-only versions of both
had already failed repeatedly:
- `Inference` model_validator: if the reading itself contains hedge
  language ("might", "may", "could", "possibly"...), confidence is
  capped at 0.4 regardless of what the model output. The model's own
  word choice is treated as more reliable evidence of its actual
  uncertainty than its confidence number.
- `engine.py` bias-evidence grounding filter: after parsing, any bias
  whose evidence string doesn't have at least 60% word-overlap with the
  user's actual text gets dropped before the Interpretation is returned.
  Tested against the two real fabricated evidence strings from the
  previous failing run: a composed summary sentence ("you've been trying
  to pivot for a while, and it's not working out yet") is correctly
  rejected, while a close paraphrase of what was actually said ("your
  boss keeps side stepping the conversation" vs. the user's "he keeps
  side stepping it") is correctly kept. This is deliberately a blunt
  instrument (word-overlap, not semantic verification) -- it will not
  catch every fabrication, but it reliably catches the specific pattern
  observed repeatedly: a fluent, invented summary standing in for a
  quote.

**Also fixed**: entities never include the user themself ("you" is not
a stakeholder in their own conversation) -- added to the existing
possessive-stripping validator as a straight exclusion list. Claims,
Goals, Assumptions, and Unknowns all got tightened prompt examples
pulled directly from the failing transcript (see the "problem 1-5"
review this entry responds to), same pattern as v0.5's hardening pass.

**Standing note on method, worth keeping**: the right response to a
prompt instruction not holding isn't always a better-worded prompt. Once
a specific failure mode survives an explicit, concrete negative example
and still recurs on the next test, that's a signal to move the fix into
code if the failure is structurally detectable (as bias-evidence
fabrication and confidence-hedging both are) -- reserving prompt
iteration for failures that are genuinely about judgment rather than
about a checkable pattern.

**2026-07-02 — v0.8: causal permission rule + code-level grounding filters for assumptions/goals/decision_options, calibrated against the 5-run dataset**

Direct product decisions from the end-of-day recap, both binding:
1. Multi-pass architecture (Option B) is OFF THE TABLE unless explicitly
   approved -- it has real pricing/cost implications once this moves off
   free local inference, so it's a business decision, not just an
   engineering one. This version stays single-pass (Option A: tighten
   priors on the existing architecture).
2. Decision Options must be STRICTLY EXTRACTIVE -- only choices the user
   actually named, minimal room for hallucination.

**Root-cause diagnosis, converged on independently by this session and
external review**: a "causal permission" problem. Whenever another
person is mentioned, the model treats reconstructing their hidden motive
as mandatory, regardless of evidence. This is sharper than the earlier
generic "admission control" framing -- it's specific enough to write a
targeted rule and a targeted code filter against, both added this round.

**The 5-run same-input experiment (this session's key empirical result)
directly calibrated every threshold below** rather than guessing:

- **Assumption fabrication is a majority, reproducible behavior**: 4/5
  runs, same handful of invented motives recurring near-verbatim
  ("boss doesn't value my skills," "boss is afraid of confrontation").
  100% of assumptions produced across all 5 runs were fabricated -- zero
  legitimate ones to calibrate a true-positive rate against.
- Naive whole-sentence word-overlap grounding (the technique that
  already worked for bias evidence) FAILED for assumptions: fabricated
  ones scored 0.67-0.71 because the model prefixes the invented reason
  with a restated version of the input ("my boss is not willing to grant
  me the move because [fabrication]") -- the preamble inflates the
  score. Fix: when a causal connector ("because"/"since"/"due to") is
  present, only the clause AFTER it is checked for grounding -- this
  isolates the actual fabrication and dropped scores to 0.00-0.43,
  cleanly separable at a 0.45 threshold. Validated against all 9
  assumptions across all 5 runs: 9/9 correctly dropped.
- Goals and Decision Options: plain whole-string overlap worked cleanly
  (0.4 and 0.5 thresholds respectively) -- validated against the full
  real dataset: Decision Options kept exactly the 3 genuinely extractive
  options across all 5 runs, dropped all 9 invented expansions
  (negotiate again, HR mediation, internal roles, industry search...).
  Goals: 5/10 kept (2 defensible borderline drops, e.g. "get a new role
  in the product team" — erring toward dropping matches the "sparse by
  default" philosophy), zero fabricated ones slipped through.
- Confirmed a real regex gap: the v0.7 hedge-word cap matched "possibly"
  but not "possible" -- missed "it's possible that..." which was the
  construction behind several of the highest remaining confidence scores
  (0.7-0.9) in the 5-run data. Fixed.
- Confirmed entities weren't stripping "the" ("The company", "the
  product team") -- possessive-strip regex extended.

**New in prompt.py**: CAUSAL PERMISSION section, placed prominently near
the top, with the exact four recurring fabricated motives from the real
data marked as forbidden examples. Decision Options tightened to
"STRICTLY EXTRACTIVE" with explicit instruction that a vague second
option ("or do something else") should stay vague in the output, not
get expanded into a menu. Claims tightened again for a new leak found
this round (emotional content and garbled fact/goal fusions leaking into
Claims). Inferences got an explicit anti-generic-truism example (the
real "pivoting to a new team can be challenging" leak from run 1).

**Deliberately did NOT add a grounding filter to Inferences.** Unlike
assumptions/goals/decision_options, Inferences are explicitly designed
to go beyond exactly what was said -- that's the tier's whole purpose.
A hard grounding filter there would defeat it. Confidence calibration
(hedge-cap, now fixed) and the causal-permission prompt rule are the
intended controls for this tier; if generic-truism leakage or causal
fabrication persists in Inferences specifically after this round, that's
a signal this tier needs its own targeted mechanism, not a blanket
grounding filter borrowed from a different tier's fix.

**Also NOT fixed this round, logged as an accepted residual risk given
the Option-A cost constraint**: bias LABEL mislabeling (evidence is real
and grounded, but the bias name doesn't actually match what the
evidence shows, e.g. "optimism bias" applied to a complaint about being
sidestepped). The existing evidence-grounding filter can't catch this --
it verifies the quote is real, not that the label is a true description
of it. Would need either a small fixed vocabulary + rule-based label
matching, or a second LLM call to verify -- the latter is exactly the
kind of cost increase Option A rules out, so this stays prompt-only
(reinforced guidance to only use well-understood terms) for now.

**2026-07-02 — v0.9 Interpretation Specification frozen (schema-first, before any prompt written)**

Per explicit process decision: v0.9 is being designed schema-first rather
than as another round of prompt patching, specifically to avoid the
"prompt accretion" problem (15 more instructions, more "don't do X"
rules, becoming impossible to reason about) that the v0.5-v0.8 cycle was
starting to exhibit. Full spec lives at
`engine/specs/interpretation-spec-v0.9.md` -- every field justified
against "what breaks if this disappears," five Governing Laws stated
explicitly at the top (sparse by default, evidence before inference,
typed over prompted, every field must justify its existence, interpret
don't advise) rather than left scattered implicitly across prior
decisions.md entries.

Headline changes locked into the frozen spec (not yet implemented):
- `stakes` (free string, 80% corruption rate in testing) renamed to
  `impact_domains`: multi-label closed enum
  (personal/professional/financial/health/legal/safety/other).
- `emotional_signals` kept as a structured object (explicitly NOT
  flattened to accommodate the 3B model's current limitations -- per
  direct instruction, the domain model doesn't get simplified for the
  model's sake, the prompt/examples get improved instead); added a
  `source` field (explicit vs inferred). A `subject` field was proposed,
  then removed after failing its own "what breaks if this disappears"
  test -- nobody consumes it yet, no multi-agent reasoning exists for it
  to plug into.
- `surface_complaint` redefined as a concise-restatement objective,
  deliberately NOT a hard word-count rule (word counting is fragile
  across punctuation/contractions/languages) -- conciseness taught via
  worked examples instead.
- `assumptions` gets a new cross-field dedup validator (catches a new
  failure shape found in testing: the user's own question dumped whole
  into assumptions -- passes existing grounding filters since it's
  technically "grounded," just in the wrong tier).
- `unknowns` redefined away from "assistant brainstorming next steps"
  toward genuine gaps in the situation as stated.
- Schema-wide casing convention adopted: all scalar/enum values lowercase
  snake_case, stated explicitly now while the schema is still small.

Status: FROZEN. Next steps in order: migration document (v0.8 -> v0.9
diff with rationale), then and only then the new prompt/code.

**2026-07-02 — v0.9 implemented (from the frozen spec, not another prompt patch)**

`schema.py`, `prompt.py`, `engine.py`, `state.py`, `state_updater.py`,
`builder.py`, `debug.py`, `judgment/engine.py` (comment only) all updated
to implement engine/specs/interpretation-spec-v0.9.md. Every change here
traces to a specific line in that spec -- no new instructions were added
that weren't already decided during spec design.

Verified offline before shipping (all passed):
- `urgency` and `impact_domains` correctly reject out-of-enum values
  (Pydantic ValidationError) -- structural guarantee, not prompt-dependent.
- Confirmed `model_json_schema()` encodes both as proper JSON Schema
  `enum` -- the actual mechanism Ollama's grammar needs to honor. This
  is still the one thing that can only be confirmed live: grammar
  enforcing `enum` membership is a different (and more standard) kind of
  constraint than the numeric `ge`/`le` ranges we already confirmed
  Ollama does NOT enforce, but "different kind of constraint" is a
  reasoned bet, not a guarantee -- first thing to check once real
  Ollama output comes back.
- New `assumptions` filters (ends-with-"?" check, cross-tier duplicate
  check against observed_facts/surface_complaint) correctly reject the
  exact real failure from the last test run (user's own full question
  dumped into assumptions) -- confirmed it would have passed the old
  grounding-only filter (100% word overlap, it's literally their words)
  and is now caught by the new checks specifically.
- New `unknowns` planning-question filter: first version missed two real
  fabricated examples ("What are the best steps..." / "What are the
  potential risks...") because the regex only caught "how can I"/"what
  should I" openers, not "what are the best/potential X" phrasing.
  Broadened and re-verified against all 5 real fabricated unknowns from
  the last test batch -- all correctly caught, both legitimate unknowns
  from that batch correctly kept.
- New `entities` grounding filter: correctly drops all 5 real fabricated
  entities from the last test ("career coach," "therapist," etc.,
  pulled from the corrupted stakes-field leak) while keeping the 3 real
  ones (boss, HR, job market).
- Full state pipeline re-tested end to end: `impact_domains` correctly
  ACCUMULATES across turns (list union) rather than overwriting -- same
  merge-not-overwrite discipline established back in v0.1-v0.4, now
  applied to a list-typed field for the first time.
- `agency_level` removed from both `ConversationState` and the Claude-path
  mirror; `state_inspector.render()` re-verified to still work cleanly
  with the field gone.

Not yet tested: live behavior against llama3.2:3b. Everything above is
either a structural guarantee (Pydantic validation, which cannot fail
regardless of model behavior) or a code-level filter tested against
already-known real failure text -- but whether the PROMPT changes (the
worked examples, the Governing Laws framing, the redefined unknowns/
assumptions instructions) actually change what the model generates in
the first place is still an open, real question. Next step: n=10 live
test against the same test-case-2 input used for the v0.8 baseline, for
a direct comparison.

**2026-07-02 — v1.0 exit criteria set (Interpretation layer freeze point)**

Explicit decision: one more iteration after the current n=10 v0.9 test,
then Interpretation freezes at v1.0 and work moves to Judgment/Planner.
Not chasing perfection past this point -- deliberate stopping discipline,
consistent with the whole day's approach of measuring rather than
guessing when something is "done."

Interpretation v1.0 exit criteria (all six must hold):
1. Stable across repeated runs on the fixed benchmark conversations
   (TC1: boss/product-team pivot; TC2: toxic boss/HR/weak job market).
   "Stable" means no field flips between fundamentally different SHAPES
   across runs (e.g. a field corrupting into prose vs. staying a clean
   list) -- not zero wording variance, which is expected and fine.
2. Zero major role violations across all runs on both benchmarks. Hard
   zero, not a rate -- one instance of advice/comfort/therapist-voice
   content anywhere in the output fails this criterion.
3. No systematic fabrication -- and specifically, no NEW leak relocation
   to an unguarded field. The recurring pattern all day has been "fix one
   tier, fabrication moves to a different one" -- this criterion is about
   confirming that stopped, not just that the old, already-fixed leaks
   stay fixed.
4. Schema frozen except bug fixes after v1.0 -- no new tiers/fields
   without deliberately reopening the full spec process again.
5. Good enough for Judgment to consume without defensive prompting --
   concretely: judgment/engine.py should never need to duplicate a
   grounding/sanity check that Interpretation is already supposed to
   guarantee. If Judgment ever wants its own such filter, that's a sign
   Interpretation isn't actually done.
6. Every field justifies its existence -- final full pass, same test that
   caught `agency_level` during v0.9 spec design ("what breaks if this
   disappears?"), applied one more time across the WHOLE schema right
   before freezing, not just the fields touched this round.

**2026-07-03 — Final v1.0 iteration: "would a larger model still benefit" filter applied**

n=10 test on TC2 scored against the v1.0 exit criteria. Result: strong
confirmation of two structural fixes (impact_domains: 0/10 corruption,
zero role violations across all 10 runs -- criterion #2 passed as a hard
zero), plus two new real findings. Explicit decision on what to fix,
using the rule: "would a larger model still benefit from this
improvement? If yes, fix it. If no, don't optimize around today's
implementation." This is the LAST iteration before freeze -- see the
2026-07-02 "v1.0 exit criteria" entry for what freeze means.

**Fixed (passes the test -- structural, benefits any model size):**
- Unknowns planning-question regex: n=10 found 5 more real leak shapes
  the v0.9 pattern missed ("how to X", "what kind of X would be a good
  fit", "what to do next"). Regression-tested against all 17 real
  examples seen across every test today (both TC1 and TC2 batches) --
  all correctly classified after the fix, zero false positives on
  legitimate unknowns.
- Claims/assumptions cross-tier duplication: n=10 showed the SAME
  directly-stated content ("the job market is weak," "HR has not been
  supportive") landing in `claims` in some runs and `assumptions` in
  others, on identical input. Root cause: the tier definitions never
  explicitly ruled out directly-stated content from `assumptions` -- an
  ambiguity in OUR instructions, not a 3B-specific limitation, so a
  larger model would hit the same ambiguity (just guess right more
  often by luck). Fixed two ways: (1) explicit prompt rule -- "if the
  user stated something directly, it is NEVER an assumption," with a
  worked bad example; (2) extended the existing cross-tier duplicate
  filter (previously only checked observed_facts/surface_complaint) to
  also check against `claims`. Threshold lowered 0.8 -> 0.7 after real
  near-duplicate rewordings ("job market is weak" vs a claim reading
  "weak job market") scored 0.75, just under the original threshold.
  Verified the lowered threshold still correctly KEEPS a genuine
  legitimate assumption (the "boss blocking career" example from the
  spec itself) despite sharing vocabulary with an observed fact --
  confirms the filter discriminates on real duplication, not just topic
  overlap.

**Explicitly NOT fixed (fails the test -- would be optimizing around
today's specific model, not a structural gap):**
- `emotional_signals` staying empty 10/10 despite explicit worked
  examples and "if the user expresses ANY emotional content, this list
  should not be empty." The "add examples, don't flatten" bet from the
  v0.9 spec design did not pay off empirically. But flattening the
  object now would be optimizing the domain model around a 3B model's
  current capability ceiling -- exactly what the governing principle
  ("never simplify the domain model to accommodate the current model's
  limitations") exists to prevent. Explicitly deferred, not silently
  dropped: documented here as a KNOWN, ACCEPTED limitation of the
  Ollama/3B provider specifically. Revisit when the Claude swap happens
  -- if a larger model still fails to populate this field given the
  same schema and examples, that would be new information suggesting an
  actual design problem; until then, this is provider-quality
  variance, not an architecture defect.

**Scoring against the six v1.0 exit criteria after this round:**
1. Stable across runs -- impact_domains and surface_complaint fully
   stable at n=10; claims/assumptions routing addressed above.
2. Zero role violations -- PASSED, hard zero at n=10.
3. No systematic fabrication -- PASSED for fabrication; the
   claims/assumptions issue was misrouting of true content, not
   invention, and is now addressed.
4. Schema frozen except bug fixes -- this entry IS that freeze point,
   pending final field-justification pass (#6) and live re-test.
5. Judgment-ready without defensive prompting -- PASSED for every field
   except emotional_signals, which is a known, documented, accepted gap
   (see above), not a silent one.
6. Every field justifies its existence -- final pass still pending
   before formal freeze declaration.

Next: apply this patch, re-run n=10 on TC2 (and ideally TC1) live to
confirm the two fixes hold against real model output, do the final
field-justification pass, then declare v1.0.

**2026-07-03 — v1.0 declared. Assumptions bare-restatement fix applied (final iteration).**

Second n=10 batch on TC2 refined the diagnosis from the first: the
claims/assumptions duplicate-tier fix (previous entry) only caught
same-turn duplication. The dominant real pattern was different -- in 5
of 6 misfiled cases, there was no matching claims/observed_facts entry
that turn AT ALL to deduplicate against. The model just picked
`assumptions` outright for directly-stated content, nothing to compare
it to.

**Fix**: `_is_bare_restatement()` -- an assumption with NO causal
connector (no "because"/"since"/"due to", i.e. not actually making an
inference) that scores >=0.7 word-overlap against the RAW user text
directly (not sibling fields) is a bare restatement of a stated fact,
not an implied belief, regardless of what's in claims/observed_facts
this turn. Threshold started at 0.8, lowered to 0.7 after the same
near-miss pattern as the earlier duplicate-tier fix ("HR was not
supportive" vs the user's "have not been very supportive" scored 0.75).
Regression-tested against every real assumption from both n=10 batches
(11 total): all 4 real bare-restatement cases correctly dropped, all 5
genuinely fabricated assumptions (a different, deliberately UNFIXED
problem -- see below) correctly left alone.

**Correction to a claim in this session's discussion, worth having on
record precisely**: emotional content was characterized as "the model
recognizes the evidence but fails to instantiate the object" (i.e.
consistently captured in claims as a fallback). Checked against the
actual 10-run data: emotional content landed in claims in only 5 of 10
runs -- the other 5 don't capture it anywhere at all. Roughly a coin
flip between misfiled and genuinely lost, not a consistent fallback.
Doesn't change the decision (emotional_signals stays unflattened, fails
the "would a larger model benefit" test to fix further) but the
optimistic framing didn't hold up against the numbers and is corrected
here rather than left standing.

**Real finding, explicitly NOT fixed, logged for the record**: while
building the bare-restatement fix, testing the spec's own "good"
assumption worked example ("User believes boss is intentionally
preventing their career growth," paired with "He's blocking my
career.") against the actual filter chain showed it would be REJECTED
by `_is_assumption_grounded` -- a filter that has existed since v0.8.
Root cause: that filter requires 0.45 literal word-overlap even for
non-causal-connector assumptions, but a legitimate PARAPHRASED inference
("preventing career growth" for "blocking career") naturally has low
literal overlap despite being well-grounded. This is a real gap in the
original grounding design, not something introduced this round -- it
was never caught because no real test conversation happened to produce
a legitimate non-causal assumption phrased distinctly enough to trigger
it. Not fixed now: it didn't surface in any of the 20 real runs across
both n=10 batches, and chasing it now would be reopening scope past the
agreed stopping point. Documented here so it's known, not silently
carried forward as an undiscovered bug.

**FINAL SCORING against the six v1.0 exit criteria:**
1. Stable across runs -- PASS. impact_domains/surface_complaint fully
   stable at n=20 (both batches); claims/assumptions routing addressed.
2. Zero role violations -- PASS, hard zero across n=20 total runs now.
3. No systematic fabrication -- PASS for genuine fabrication. Misrouting
   of true content addressed; unknowns regex backstop accepted as
   imperfect-by-design (see entry below), not fabrication.
4. Schema frozen except bug fixes -- IN EFFECT AS OF THIS ENTRY.
5. Judgment-ready without defensive prompting -- PASS except
   emotional_signals (documented, accepted gap, not silent).
6. Every field justifies its existence -- CONFIRMED. Re-checked against
   the full field list from engine/specs/interpretation-spec-v0.9.md;
   no field added since that audit lacks a downstream consumer. No
   changes needed.

**DECISION: Interpretation is v1.0.** Not complete, not perfect --
stable, grounded, typed, and safe for Judgment to build on without
defensive prompting except for the one documented emotional_signals
gap. Remaining known limitations (unknowns regex coverage,
emotional_signals recall, the pre-existing paraphrase-grounding gap
above) are extraction-quality and small-model-capability issues, not
architectural flaws, and are explicitly not being chased further per
the "would a larger model still benefit" rule agreed this session.

Schema changes from here require deliberately reopening this process
(spec update -> migration doc -> prompt), not ad hoc prompt patches.
Next: State Builder.

**2026-07-03 — Known limitation logged (post-v1.0): negation-blind grounding**

Live n=10 re-test of the v1.0 assumptions fix confirmed the fix itself
holds (zero recurrence of the bare-restatement pattern across 10 runs,
30/30 zero role violations across all three n=10 batches today). But it
surfaced a new, distinct gap: one run produced the assumption "HR will
be supportive" -- directly contradicting the user's actual statement
("they have not been very supportive"). This passed every existing
filter because word-overlap grounding checks WHICH words appear, never
whether polarity/negation matches -- "HR," "will," "supportive" all
score as grounded even though the claim is inverted. Different failure
class from anything fixed today: not a restatement (bare-restatement
filter correctly ignored it) and not unrelated fabrication (which at
least invents new content) -- it's wrong in a way that looks
well-grounded by every current metric.

One occurrence in 30 live runs today. Evaluated against this session's
"would a larger model still benefit" rule: yes in principle, but a real
fix needs actual negation/polarity detection, not a threshold
adjustment -- materially larger scope than anything else patched today.

**Decision: logged as a known, accepted v1.0 limitation, not fixed.**
Consistent with the emotional_signals and paraphrase-grounding gaps
already accepted in the v1.0 declaration above -- extraction-quality
issue, not an architectural flaw, and out of scope for further patching
under the agreed stopping discipline. Revisit if this pattern recurs at
meaningful frequency in future testing, or when the Claude swap happens.

**2026-07-05 — OpenRouter made primary provider, Ollama kept as fallback (unvalidated swap, logged explicitly)**

Practical trigger: `conversation_runner.py` failed in a Codespace with no
local Ollama running (`Connection refused` on `localhost:11434`).
Direct product decision, explicitly made aware of the tradeoff below:
OpenRouter (env-configurable model, `src/interpretation/providers.py`) is
now the primary provider; Ollama (unchanged native `/api/chat` call,
same `format`-as-schema grammar constraint) is kept as an automatic
fallback if the OpenRouter call fails.

**Flagging explicitly, per this file's own stated methodology**: every
grounding-filter threshold in `engine.py` (bias-evidence 0.6,
decision-option 0.5, goal 0.4, assumption 0.45, bare-restatement 0.7,
etc.) was calibrated via live n=10/n=20 testing against Ollama's
llama3.2:3b specifically. This change means the provider most turns
actually run against (OpenRouter's configured model, default
`openai/gpt-4o-mini`) has NOT been through that same validation, and the
v1.0 exit criteria are strictly only confirmed for the Ollama path.
Per the "would a larger model still benefit" rule used throughout the
v1.0 freeze: a materially more capable model is likely to fabricate
*less*, not more, so the existing filters should if anything over-reject
rather than under-reject against the new default -- but this is a
reasoned bet, not a confirmed result the way every Ollama-path number
above is.

**Not done, and deliberately flagged as the real next step**: re-running
the n=10 methodology (same TC1/TC2 benchmark conversations, same six exit
criteria) against whatever `OPENROUTER_MODEL` ends up configured, the
same rigor originally reserved for the eventual Claude swap this entry
effectively front-runs. Until that happens, the OpenRouter path should be
treated as MVP-quality, not v1.0-validated -- same status the Ollama path
had before its own testing rounds.

**2026-07-05 — OpenRouter call fixed: strict json_schema mode isn't viable, switched to json_object + text schema hint**

First real CI run of the OpenRouter path (n=1 smoke test via the new
benchmark workflow) failed both benchmark cases with the same error:
`OpenRouter returned 400: "Invalid schema for response_format
'Interpretation': 'additionalProperties' is required to be supplied and
to be false."` -- OpenAI's `strict: true` json_schema mode requires every
object in the schema, including nested ones (EmotionalSignal, Bias,
Inference, ...), to explicitly declare `additionalProperties: false`.
Pydantic's `model_json_schema()` doesn't set that, and fixing it properly
would mean either touching the frozen `schema.py` (adding
`model_config = ConfigDict(extra="forbid")` everywhere) or
recursively rewriting the generated schema before every call.

Took the simpler, already-proven path instead: dropped `strict`/
`json_schema` entirely in favor of plain `response_format: {"type":
"json_object"}`, with the schema appended as a text hint on the system
message rather than passed as a real constraint. This is the same
pattern `engine/state_updater.py` already uses on the main-line branch --
JSON mode only guarantees syntactically valid JSON, not shape, so
`engine.py`'s existing full Pydantic validation (already there
regardless of provider) is the real enforcement, same as it's always
been for the Ollama path when grammar constraints don't cover something
(e.g. the confidence 0-10 vs 0-1 scale bug logged earlier, which grammar
constraints didn't catch either).

Practical effect: the OpenRouter path now has weaker structural
constraints than Ollama's grammar-constrained `format` param -- worth
factoring into the eventual n=10 validation pass, since a higher rate of
shape drift (not just content fabrication) is plausible until/unless
this gets upgraded to a properly `additionalProperties`-compliant schema.

**2026-07-05 — WorldState v1: ConversationState replaced with typed, lifecycle-aware state**

User supplied `WorldState_Specification_v1.md` (Facts/Claims/Goals/Open
Decisions/Open Unknowns/Entities as the Core Structure, plus provenance,
turn numbering, conversation summary, emotional history trend, and a
project graph as cross-cutting sections). Explicit scope decision, made
after an initial "build everything" answer was walked back: **implement
WorldState v1, not WorldState Ultimate** -- prove the new data model and
merge semantics first, since that's what's orthogonal to everything else
(Judgment, the inspector, the whole pipeline shape) and worth stabilizing
before layering more onto it. Staged as:
- **v1 (this entry)**: typed `WorldState` (`src/state/world_state.py`),
  typed `Fact`/`Claim`/`Goal`/`Decision`/`Unknown`/`Entity` objects with
  lifecycle status fields, per-type merge policies, a rewritten
  `src/state/builder.py`, and `src/judgment/engine.py` updated to consume
  `WorldState`.
- **v1.1 (deferred)**: provenance (source/first_seen/last_updated/
  supporting_evidence), turn numbering, stable object IDs.
- **v1.2 (deferred)**: conversation_summary, emotional_history (trend
  computation).
- **v1.3 (deferred)**: project graph, cross-links between entities and
  goals.

Every stage is meant to leave the system runnable -- v1 fully replaces
`ConversationState` in the live pipeline (`conversation_runner.py`,
`src/judgment/engine.py`, `engine/state_inspector.py`) rather than
running the two in parallel.

**Design choices made without an explicit spec answer, flagged rather
than silently decided:**
- **Decision modeling**: the spec's "Open Decisions" section implies one
  named decision with options, but `Interpretation.decision_options` is
  an untitled flat list (see `src/interpretation/schema.py`). Rather than
  invent a grouping/title the evidence doesn't support, kept one
  `Decision` object per option string -- consistent with this codebase's
  standing rule (epistemic tiers are never merged/clustered beyond what
  the model actually output).
- **Phase 2 tracking carried forward**: the spec's Core Structure has no
  slot for "what's the real question" (the old `core_problem`/
  `surface_complaint`/`core_problem_confidence` fields). Dropping it
  would have silently regressed behavior the inspector and Judgment
  already depend on, so it's kept on `WorldState` as an explicit
  extension beyond the literal spec text, same "never regress on lower
  confidence" merge rule as before.
- **Entity/Goal/Decision lifecycle**: statuses beyond the initial one
  (`paused`/`completed`/`abandoned` for Goals, `resolved`/`expired` for
  Decisions, attribute/relationship enrichment for Entities) never fire
  in v1 -- `Interpretation` has no signal for any of these transitions
  today. Fields exist per spec; nothing invents the missing signal.
- **Unknown resolution -> Fact promotion**: ported the existing
  substring-based reconciliation heuristic unchanged from the old
  `update_state` (already documented there as "good enough for MVP,
  revisit if it proves too blunt") and added the one genuinely new piece
  the spec calls for: a resolved Unknown's content is now promoted into
  `Facts` rather than just discarded.

**Left untouched, confirmed dead in this branch's live path**:
`engine/state.py` (`ConversationState`), `engine/state_updater.py`
(Anthropic-based, superseded by `src/interpretation/providers.py`'s
pattern), and `engine/mock_state_updater.py` -- none are imported by
`conversation_runner.py` or anything it calls. Left in place rather than
deleted since nothing forced the choice either way; worth a deliberate
cleanup pass later if they're confirmed to have no future use (e.g. as
reference material for a different future swap).

**2026-07-05 — WorldState v1 follow-up: standardized KnowledgeItem shape, logged WorkingMemory/Knowledge split as a deferred TODO**

Direct feedback on the v1 entry above, explicit decision on what to do
next and what to explicitly NOT do yet: "a good architecture isn't one
where every future feature is built today -- it's one where those
features have an obvious place to go when you need them." Two concrete
changes, everything else deliberately left to evolve based on what
Judgment actually needs:

1. **Standardized shape**: added a `KnowledgeItem` base class
   (`src/state/world_state.py`) that `Fact`/`Claim`/`Goal`/`Decision`/
   `Unknown`/`Entity` all inherit from, guaranteeing every durable
   knowledge object carries `status` (each subtype narrows the Literal
   and default), plus `confidence`/`provenance` placeholder fields
   (`Optional[..] = None`, nothing populates them yet -- real shapes land
   in v1.1). `Unknown` and `Entity` didn't have a `status` field at all
   before this -- added (`open`/`resolved` and `active`/`retracted`
   respectively) purely for shape consistency; `_reconcile_unknowns` in
   `src/state/builder.py` still removes a resolved Unknown outright
   rather than marking it resolved and retaining it, which is arguably
   inconsistent with Design Principle 3 -- logged as a TODO at that
   function rather than changed, since fixing it is a merge-behavior
   change, not a shape change.

2. **Logged, not built**: a design-note TODO in `world_state.py`'s module
   docstring that `WorldState` currently conflates two different kinds of
   state -- durable Knowledge (Facts/Claims/Goals/Decisions/Unknowns/
   Entities) and Working Memory (phase, core_question tracking,
   assumptions/inferences/biases, clarity_level -- reasoning scaffolding
   about where the CONVERSATION stands, not facts about the user's
   world). `phase` and core_question tracking are clearly the latter;
   assumptions/inferences/biases are deliberately left unclassified since
   an assumption surfaced today could turn out to be durable knowledge,
   not just scratchpad -- forcing that split now would be guessing ahead
   of evidence, the same mistake this codebase has repeatedly corrected
   for elsewhere (see every "don't invent structure the evidence doesn't
   support" entry above). Split WorkingMemory out into its own container
   once Judgment's actual usage patterns make the right split obvious.

**2026-07-05 — WorldState v1 tested in isolation: state evolution test suite, 3 confirmed gaps, proposed fixes not yet implemented**

Explicit ask: validate the State Builder / WorldState layer in isolation
NOW, before Judgment starts depending on it -- once that dependency exists,
a failure could originate in Interpretation, the State Builder, WorldState,
or Judgment, and isolating the cause gets much harder. Added
`tests/test_world_state_evolution.py` (pytest, new `requirements-dev.txt`):
5 tests built from hand-constructed `Interpretation` objects (no LLM calls),
run turn-by-turn through `update_state()`. All 6 assertions (one test split
into two) PASS -- but "pass" means "asserts real, verified behavior," not
"confirms everything works as hoped." Per explicit instruction: document and
propose fixes for confirmed gaps, do not implement any fix without
discussing and confirming first.

**Confirmed working (validates intended behavior):**
- Cross-tier accumulation (goal/fact/unknown from different turns coexist
  correctly) and exact-repeat dedup (verbatim-restated goal doesn't
  duplicate).
- Unknown resolution fires correctly on real word/substring overlap, and
  the resolved content is genuinely promoted into Facts (not just
  discarded) -- this was the one new behavior added this round, confirmed
  working.
- Entity dedup by name (case-insensitive) -- "Rahul" mentioned twice stays
  one Entity, not two.

**Confirmed gap 1 -- contradiction is never detected.** "Boss denied the
transfer" then "Boss approved the transfer" produces two `active` Facts;
`FactStatus.superseded` exists in the schema but no code path ever sets it.
*Proposed fix (not implemented, for discussion)*: the "typed over prompted"
principle already established for Interpretation (see multiple 2026-07-02
entries above) argues for having Interpretation itself flag contradictions
explicitly -- e.g. a `supersedes: Optional[str]` hint on new facts/claims --
rather than trying to detect contradiction post-hoc from two arbitrary
strings. That requires deliberately reopening the Interpretation spec
(schema change), the same discipline already applied to every prior
schema change on this branch. A cheaper but weaker alternative (keyword/
antonym heuristics) would inherit the same class of fragility as the
already-logged "negation-blind grounding" limitation and isn't recommended.

**Confirmed gap 2 -- unknown resolution is real-substring-only, doesn't
catch realistic paraphrasing.** "Why HR rejected the application" is not
resolved by "HR said the role was frozen" -- confirms the "too blunt"
limitation already flagged in `_reconcile_unknowns`'s docstring, now with a
concrete reproducible example. *Proposed fix (not implemented)*: swap the
strict substring check for the same word-overlap scoring already proven
in `src/interpretation/engine.py` (`_word_overlap`, used for bias-evidence
and assumption grounding) -- lower risk than a schema change since it
reuses an existing, tested pattern in place rather than adding new
Interpretation fields.

**Confirmed gap 3 -- Goal/Decision lifecycle never advances.** "Build
Confidant" then "launched the MVP" leaves the goal `active` forever, with
no link from the new fact back to the goal. Matches the KNOWN LIMITATION
already documented in `world_state.py`. *Proposed fix (not implemented)*:
this one genuinely needs an Interpretation-level signal (there's no
existing field to reuse, unlike gap 2) -- e.g. a
`goal_status_signals: List[...]` field pairing a goal reference with an
observed status change. Bigger lift than gap 2's fix; would need to go
through the same spec-reopening process as any other Interpretation schema
change.

**Confirmed gap 4 -- Entity attribute enrichment has no data source.**
"Rahul now heads Product" never becomes a structured attribute on the
`Rahul` Entity -- `Interpretation.entities` is a flat list of name strings
only. *Proposed fix (not implemented)*: same shape as gap 3 -- requires
extending `Interpretation`'s entity extraction to emit structured
attributes, not just names. No in-place fix available without touching
Interpretation's schema.

**Not done this round, deliberately**: implementing any of the four
proposed fixes above. Per explicit instruction, this entry is the
discussion document; next step is confirming which (if any) to build.

**2026-07-05 — Confidence-formatting fix implemented; unknown resolution swapped to word-overlap; contradiction/lifecycle/entity-enrichment fixes explicitly declined**

Direct decision on the four proposed fixes above, after reviewing the live
10-turn walkthrough transcript:

**Implemented:**
1. **Confidence-formatting bug** (`src/state/builder.py`): the walkthrough's
   turn 5 showed a real doubled annotation --
   `"...situation (confidence=0.5) (confidence=0.50)"` -- because the model
   sometimes writes its own `(confidence=X)` directly into an Inference's
   `reading` text, and `update_state` then appended its own canonical one on
   top. Fixed with `_clean_reading()`, a regex strip of any model-embedded
   `(confidence=...)` before formatting. Covered by
   `test_inference_embedded_confidence_annotation_is_stripped`.
2. **Unknown resolution: substring -> word-overlap.** Replaced the exact
   substring check in `_reconcile_unknowns` with `_is_resolved_by()`, using
   a word-overlap scorer (same set-intersection-ratio algorithm as
   `src/interpretation/engine.py`'s `_word_overlap`, deliberately
   DUPLICATED rather than imported -- that module is the frozen v1.0
   Interpretation layer, and this avoids taking any dependency on / risk to
   frozen code for a one-line algorithm; the two use cases -- grounding a
   model's own extraction against raw user text, vs. matching two model
   outputs against each other across turns -- may reasonably diverge later
   anyway). Threshold (0.5, either direction) is a first cut, NOT
   empirically calibrated the way Interpretation's own thresholds were
   (those went through live n=10/n=20 testing) -- revisit once real
   conversations show whether it's too strict or too loose.
   `test_unknown_resolution_word_overlap_catches_reordered_phrasing`
   confirms a real improvement (a reordered-phrasing case the old exact
   substring check would have missed now resolves correctly).
   **Explicitly NOT claimed to fix the deep semantic-gap case**
   ("why HR rejected me" vs "role was frozen" -- no shared content
   vocabulary) --
   `test_unknown_resolution_still_misses_deep_semantic_gap_by_design`
   confirms it still doesn't resolve, deliberately: that gap needs a real
   signal from a richer Interpretation schema or from Judgment, not a
   better string-matching trick in the State Builder.

**Explicitly declined, not deferred-as-in-forgotten but deferred-as-in-decided-against-for-now:**
- Contradiction detection, Goal/Decision lifecycle advancement, and Entity
  attribute enrichment (gaps 1, 3, 4) all stay as documented gaps. Explicit
  standing principle from this round, worth keeping for any future work on
  these: **the State Builder must not compensate for a missing semantic
  signal with a heuristic.** Word-overlap for unknown resolution was
  approved because it's a real, if partial, improvement over strictly worse
  string matching and doesn't pretend to solve semantic understanding it
  can't do -- but contradiction/lifecycle/entity-attribute detection would
  require guessing at meaning (is this new fact really the same thing
  changing state, or a different thing?) that only a richer Interpretation
  schema or Judgment can legitimately provide. When these are eventually
  built, they belong in one of those two layers, not as State Builder
  heuristics.
- **Cross-tier duplication (the "goal recorded independently as a Fact, a
  Claim, and a Goal" pattern from the walkthrough) is explicitly NOT
  considered a modeling problem.** Reversing an earlier framing: this
  reflects genuinely different epistemic categories (what was observed,
  what was asserted, what's being pursued), which is the whole point of
  keeping the tiers separate (see every "never flatten epistemic tiers"
  entry above). If the rendered output reads as redundant, that's a
  presentation concern for a future WorldState rendering layer to solve
  (e.g. grouping/cross-referencing related items across tiers for display),
  not a reason to collapse the underlying knowledge model.

**2026-07-05 — WorldState v1 and Interpretation v1 declared FROZEN; Interpretation v1.1 design proposal added (not implemented)**

Final pass before moving on to Judgment. Confirmed the two implemented
fixes from the prior entry (confidence-formatting, word-overlap unknown
resolution) are both in place and covered by the 8-test suite --
re-verified, not redone. No further code changes this round: WorldState
schema, merge semantics, Judgment, and Planner are all explicitly
untouched, per instruction.

Standing architectural principle restated and now formally the freeze
condition for both layers: **Interpretation extracts structured meaning.
State Builder maintains durable knowledge. WorldState stores knowledge.
Judgment performs reasoning.** The State Builder must never become smarter
by adding heuristics that compensate for a missing Interpretation signal --
every gap identified this round (contradiction, goal/decision lifecycle,
entity enrichment) stays open specifically because closing it properly
requires a real signal from Interpretation, not a better guess downstream.

Added `engine/specs/interpretation-v1.1-proposal.md` -- a discussion draft
(explicitly not the full per-field format `interpretation-spec-v0.9.md`
uses, since nothing here is being implemented yet), proposing three typed
additions to eventually close the three declined gaps: Decision Events,
Goal Updates, Entity Attribute Updates. Recommends against a single
generalized "Knowledge Update Operation" schema in favor of three distinct
typed fields, for the same reason the original single `facts` bucket was
split into five epistemic tiers back in v0.5 -- collapsing genuinely
different update semantics into one shape reintroduces the exact
flattening mistake this project already learned from once.

**Key finding surfaced while writing the proposal, not previously
noticed**: Interpretation is currently stateless per turn --
`build_messages(user_text)` takes only the raw message, with no view into
existing WorldState. This means every proposed "update" field can describe
*that* something changed but can't cleanly reference *which* existing
Fact/Goal/Decision/Entity it applies to without either (a) accepting
text-matching at the reference-resolution step (a narrower, more bounded
problem than the heuristics already declined, but not fully eliminating
string-matching), or (b) giving Interpretation limited read access to
current open Goals/Decisions/Entities as prompt context, a materially
bigger pipeline change. Flagged as the central open question in the
proposal document rather than decided unilaterally.

**Status**: WorldState v1 and Interpretation v1 are FROZEN as of this
entry. Any further change to either requires deliberately reopening this
process (spec update -> migration doc -> prompt/code), the same discipline
already applied to every prior version. Next: Judgment v2, informed by
whichever Interpretation v1.1 fields (if any) get approved from the
proposal.
