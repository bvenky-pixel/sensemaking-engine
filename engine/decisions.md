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
