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
