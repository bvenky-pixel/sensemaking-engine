# Interpretation Specification — v0.9

**Status:** FROZEN — approved 2026-07-02. Implementation pending: migration document, then prompt/code, in that order.
**Predecessor:** v0.8 (see engine/decisions.md for full v0.1–v0.8 history)
**Methodology:** Schema-first. This document is frozen before a single line of
prompt is written. The prompt v0.9 will *implement* this spec, not define it.

---

## Governing Laws

These have existed implicitly throughout this project's history (see
engine/decisions.md for where each one first emerged from a real failure).
Stated explicitly here, together, so they're the north star for every future
version — including this one. Every field decision below should trace back
to one of these; if it doesn't, that's worth questioning.

1. **Sparse by default.** Missing evidence is better than invented structure. An empty field is a correct, complete answer — not a gap to fill.
2. **Evidence before inference.** Prefer extraction over interpretation. Every tier must know which kind of knowledge it holds — observed, asserted, implied, or inferred — and never blur them together.
3. **Typed over prompted.** Solve failures structurally whenever a prompt-only fix has already been tried and didn't hold. A closed enum beats another paragraph of instructions; a code-level filter beats a stronger-worded rule.
4. **Every field must justify its existence.** If nothing downstream consumes a field, it gets removed or explicitly marked unimplemented — never left silently pretending to work.
5. **Interpret, don't advise.** Interpretation never generates a response, a suggestion, or comfort. It organizes evidence for a judge; it doesn't argue the case.

---

## How to read this document

Every field answers seven questions:
1. **Purpose** — why this field exists at all
2. **Definition** — the operational rule for what belongs in it
3. **Type** — the actual schema type
4. **Allowed values** — constraints, if any
5. **Examples** — good and bad
6. **Validation rule** — what code-level check (if any) enforces this
7. **Downstream consumer** — what breaks if this field disappeared tomorrow

If a field has no honest answer to #7, it is deleted or marked for removal.

---

## Part 1 — Phase 1: Prepare

### `urgency`
1. **Purpose:** gates Judgment's attention_score calculation (Phase 1: understand urgency before reasoning).
2. **Definition:** the pace at which the user needs to act, based on their own stated timeframe or emotional pressure — not the model's opinion of how urgent it "should" be.
3. **Type:** `Literal["low", "medium", "high"]`
4. **Allowed values:** exactly those three. **CHANGE from v0.8:** currently typed as plain `str` with the enum only documented in a comment, not enforced. This is a real, free, structural fix — make it an actual `Literal` so out-of-set values fail validation instead of silently passing through.
5. Example: user says "I need to decide by Friday" → `high`. No timeframe mentioned → `low` unless emotional intensity strongly implies otherwise.
6. **Validation:** Pydantic `Literal` type (was previously unenforced).
7. **Downstream consumer:** `judgment/engine.py` attention_score; `ConversationState.urgency`.
**Decision: KEEP, HARDEN.**

### `stakes` → renamed `impact_domains`
1. **Purpose:** captures WHICH domain(s) of the user's life are affected — not a single category, since real situations often span more than one (e.g. "if I quit, I can't pay rent" is simultaneously professional and financial). This is being designed for Confidant's full future scope (Judgment/Planner reasoning about domain overlap, severity-by-domain, etc.), not optimized around any single test conversation.
2. **Definition (v0.8, why it failed):** an open free-text string with no format constraint. Result: 80% (4/5) corruption rate in real testing — the model used this field as an escape hatch to write therapist-voice prose, in one case a full 10-point advice list. Renaming away from `stakes` too — that name itself invited ambiguity ("what's at stake" reads as open-ended narrative, not a categorical tag).
3. **Type (v0.9):** `List[Literal["personal", "professional", "financial", "health", "legal", "safety", "other"]]` — multi-label, not single-select.
4. **Allowed values:** the 7 above. **Explicitly not included:**
   - `low` — this was in the initial sketch but is an intensity level, not a domain; mixing "which domains" with "how severe" would reintroduce exactly the kind of category-conflation this whole redesign effort exists to eliminate. Severity is a job for `urgency` + `emotional_signals.intensity`, not this field.
   - Casing: lowercase snake_case, matching `urgency`. Standardized schema-wide per explicit decision — scalar values and enum values both lowercase snake_case, to prevent exactly this kind of drift as the schema grows.
   - **`other` reinstated** after initially being cut: an empty list and "other" look similar today, but they mean different things — empty means "no domain identified," `other` means "a domain is clearly present but isn't one of the six named ones" (immigration, education, parenting, spirituality, etc.). Schemas tend to outlive the situations they were designed around, and closed-but-unlabeled situations are exactly where a rigid enum breaks down later. Cheap to keep now, costly to realize is missing once real users hit it.
5. Examples (from the actual worked cases given):
   - "I'm thinking of quitting my job." → `["professional"]`
   - "If I quit, I won't be able to pay rent." → `["professional", "financial"]`
   - "My spouse wants a divorce." → `["personal"]`
   - "My doctor says I need surgery." → `["health"]`
   - "My manager asked me to falsify numbers." → `["professional", "legal"]`
   - "Someone is threatening me." → `["safety"]`
6. **Validation:** Pydantic `Literal` inside a `List`. Same empirical bet as before (enum/closed-set constraints are a structural JSON-grammar feature, unlike the numeric ranges we confirmed aren't enforced) — still needs live testing once implemented, not assumed.
7. **Downstream consumer:** currently `ConversationState.impact_domains` (renamed from `stakes`, and now `List[str]` not `str` — this changes the merge logic in `builder.py` from overwrite to append/union, same pattern as `observed_facts`/`claims`). Real future consumer: Judgment reasoning about domain-specific severity (e.g. `SAFETY` or `LEGAL` present might always force `high` attention regardless of stated urgency) — not implemented yet, but this is the field that would carry it.
**Decision: CHANGE (free string → multi-label closed enum, field renamed).**

### `emotional_signals`
1. **Purpose:** feeds Judgment's `dominant_emotion` and `attention_score`; feeds `ConversationState.emotion`/`emotion_intensity`. Designed for Confidant's future reasoning needs, not simplified around what a 3B model currently finds easy — per explicit decision: the domain model doesn't get simplified to accommodate the current model's limitations; the prompt/examples get improved instead.
2. **Definition (v0.8, why it failed):** nested `List[EmotionalSignal]` with 3 sub-fields (emotion, intensity, confidence), but with no worked examples anywhere in the prompt showing what a correctly-populated entry looks like. Result: **5/5 runs returned an empty list**, even against maximally explicit input ("I am stressed out"). Diagnosis, per explicit decision: this is a specification/example gap, not a shape problem — fix by making the field more precisely defined and demonstrating it, not by flattening it.
3. **Type (v0.9):** kept as `List[EmotionalSignal]`, with the object itself made richer:
   ```
   class EmotionalSignal:
       emotion: str            # e.g. "stress", "frustration", "fear"
       intensity: float        # 0.0-1.0
       confidence: float       # 0.0-1.0 -- how sure this reading is correct
       source: Literal["explicit", "inferred"]
   ```
   One field added beyond v0.8: `source` distinguishes "the user named this emotion directly" from "the model read this from tone/context without it being named" — these are genuinely different epistemic situations (mirrors the observed_fact-vs-inference distinction already used elsewhere in this schema) and collapsing them into one `confidence` number was throwing away real information.

   **Removed from this draft: `subject` (who is experiencing the emotion).** Originally added to future-proof for reasoning about a third party's emotional state, but applying the document's own governing test honestly: nobody consumes it today — there's no relationship modeling, attribution reasoning, or multi-agent state anywhere in this pipeline for it to plug into. That makes it speculative, and "every field must justify its existence" doesn't get suspended for fields I add myself. Reintroduce when multi-agent/attribution reasoning is actually being built (v1.2/v2 territory), not before.
4. **Allowed values:** `emotion` stays free text (a short emotion word/phrase) rather than a closed enum — emotional vocabulary is genuinely open-ended in a way domains aren't, and forcing it into a fixed list would lose real signal. `source` is a hard `Literal`.
5. **Worked examples (new — this was the actual gap in v0.8):**
   - User: "I am stressed out and don't know what to do." →
     `{emotion: "stress", intensity: 0.7, confidence: 0.95, source: "explicit"}`
     (explicit because the user used the literal word "stressed" — when source is explicit, confidence should almost always be high, since there's little ambiguity about what emotion is present, even if its exact intensity still takes some judgment.)
   - User: "He keeps shouting at me every day and I don't know what to do." →
     `{emotion: "distress", intensity: 0.5, confidence: 0.4, source: "inferred"}`
     (inferred — the user didn't name an emotion here, but repeated shouting plus "don't know what to do" supports a moderate-confidence reading. Uses the same confidence calibration bands already established for the `inferences` tier: 0.7+ requires near-direct statement, 0.4-0.6 a clear pattern, 0.1-0.3 a weak cue.)
   - Do NOT infer a third party's emotional state ("he seemed angry") — `emotional_signals` is scoped to the user's own emotions only in this version, since there's no `subject` field to attribute it elsewhere.
6. **Validation:** existing 0-10-scale rescale validator stays on `intensity`/`confidence`. No hard structural validator planned for `source` consistency (e.g. flagging "explicit but confidence=0.2" as contradictory) — worth considering later if it turns out to be a real pattern, not built preemptively.
7. **Downstream consumer:** real, active — `judgment/engine.py`'s `dominant_emotion`/`attention_score`, `ConversationState.emotion`/`emotion_intensity`. Not a candidate for deletion; broken, not unused.
**Decision: CHANGE (richer object, NOT flattened) — add `source` only (not `subject` — see above), add worked examples to the prompt.**

---

## Part 2 — Phase 2: Discover

### `surface_complaint`
1. **Purpose:** anchors Phase 2 (distinguish symptom from real question).
2. **Definition (v0.8, why it failed):** undefined length/format. Result: ranged from a 2-word phrase ("toxic boss") to a full paragraph carrying the user's entire emotional register, across the same 5 runs on identical input. The field's definition isn't operational enough to converge.
3. **Type:** `str`
4. **Allowed values (v0.9):** a **concise** compressed restatement of the user's own stated problem — never an emotional summary, never a question back to the user, never the input restated at length. Deliberately NOT a hard word-count rule (e.g. "≤ 12 words") — word counting gets awkward fast across punctuation, contractions, and languages, and a rigid number invites exactly the kind of brittle parser-rule thinking this document is trying to move away from. Treat conciseness as a prompt objective demonstrated through examples, not a rule a validator enforces.
5. Examples: GOOD: "Boss won't approve move to product team." BAD: "I'm feeling overwhelmed and stressed about my job situation and don't know where to start."
6. **Validation:** none planned — this is a prompt-quality objective, not a parser rule. If it doesn't converge through examples alone, revisit with something more structural (e.g. a max character budget, not a word count) rather than a fragile counting heuristic.
7. **Downstream consumer:** `ConversationState.surface_complaint`, debug display, future Planner input.
**Decision: CHANGE (define as a concise-restatement objective, not a hard length rule).**

### `core_question` / `core_question_confidence`
1. **Purpose:** Phase 2's actual output — the real question beneath the symptom.
2. **Definition:** unchanged from v0.8 — this field performed reasonably consistently (4/5 runs at a stable, sensible reading) in the latest test.
3. **Type:** `str` / `float` (0.0–1.0)
4. No change to allowed values.
5. N/A — no new examples needed.
6. **Validation:** existing rescale-from-0-10 validator stays.
7. **Downstream consumer:** `ConversationState.core_problem`/`core_problem_confidence`, phase-transition logic in `judgment/engine.py`.
**Decision: KEEP. Defer calibration work — re-test after `impact_domains` is fixed**, since the one 0.0-confidence outlier in the 5-run data co-occurred with the worst `stakes` corruption in the same generation. Real possibility this resolves as a side effect rather than needing its own fix.

---

## Part 3 — Phase 3: Discern (epistemic tiers)

### `observed_facts`
1. **Purpose:** meta-level record of what was explicitly said — the most trustworthy tier.
2. **Definition:** unchanged — this has been the most stable-performing field across every version since v0.5.
3. **Type:** `List[str]`
7. **Downstream consumer:** `ConversationState.observed_facts`, unknowns-reconciliation logic in `builder.py`.
**Decision: KEEP, unchanged.**

### `claims`
1. **Purpose:** propositions the user asserts as true.
2. **Definition:** unchanged from v0.8 — the tier-confusion failures (options-as-claims, emotion-as-claims) that plagued earlier versions did not reappear in the latest 5-run test.
3. **Type:** `List[str]`
7. **Downstream consumer:** `ConversationState.claims`.
**Decision: KEEP, unchanged.**

### `goals`
1. **Purpose:** what the user is trying to achieve.
2. **Definition (v0.8 issue):** goals are being captured (real improvement from earlier versions) but drifting toward abstraction — "I want to change jobs" became "Address the toxic work situation" / "Escape the toxic work environment" in 2 of 5 runs. Not fabrication, but generalization away from the user's literal words.
3. **Type:** `List[str]` (unchanged)
4. **Allowed values (v0.9):** explicit instruction to stay as close to the user's own phrasing as the evidence allows — generalizing "change jobs" into "escape the toxic environment" reframes a concrete goal as an abstract one and should be avoided.
6. **Validation:** existing word-overlap grounding filter (threshold 0.4) stays; consider raising slightly given the drift pattern, pending a test.
7. **Downstream consumer:** `ConversationState.goals`.
**Decision: KEEP, TIGHTEN definition + reconsider threshold.**

### `decision_options`
1. **Purpose:** choices the user is explicitly weighing (strictly extractive, per explicit product decision).
2. **Definition:** unchanged — the v0.8 grounding filter (threshold 0.5) is working cleanly; zero fabricated options survived in the latest test.
3. **Type:** `List[str]` (unchanged)
7. **Downstream consumer:** `ConversationState.decision_options`; intended future Planner input.
**Decision: KEEP, unchanged.**

### `assumptions`
1. **Purpose:** unstated beliefs the user is implicitly relying on.
2. **Definition (v0.8 issue):** the causal-permission fix worked — zero invented third-party motives in the latest 5-run test, a real, confirmed win. But a **new, different failure shape** appeared: in one run, the user's own full question ("I want to change jobs but don't know where to start... Can you help me?") was dumped whole into `assumptions`. This isn't fabrication — the existing grounding filter would score it as ~100% grounded (it's literally the user's words) and let it through, because the filter checks *is this grounded*, not *is this in the right tier*.
3. **Type:** `List[str]` (unchanged)
4. **Allowed values (v0.9):** an assumption must be a single implicit belief statement — never a question (must not end in `?`), never identical or near-identical to content already present in `observed_facts` or `surface_complaint`.
6. **Validation (new):** cross-field dedup check — if an assumption string is near-identical to an existing `observed_facts` or `surface_complaint` entry, or ends in `?`, drop it. This is a new code-level filter, same pattern as the existing bias/goal/decision-option filters, targeting a gap those filters don't cover.
7. **Downstream consumer:** `ConversationState.assumptions`, `judgment/engine.py`'s `assumptions_surfaced` count.
**Decision: KEEP, ADD cross-field dedup validator.**

**REOPENED (2026-07-09, see engine/decisions.md):** A04 (Primary Capability
"Hidden assumptions") repeatedly produced `assumptions=[]` even on a test
whose own framing ("I think I'm making the wrong decision") embeds an
obvious implicit belief (a right decision exists to find). A prompt-only
fix (a worked example distinguishing this exact case) was tried first per
governing law 3 and confirmed, on re-test against the real pipeline, NOT
to hold -- `assumptions` stayed empty. **Decision: CHANGE — add a
mandatory `assumption_check` field** (a required, non-empty reasoning
string immediately preceding `assumptions`) that forces the model to
explicitly state whether the user's own phrasing embeds an unstated
belief before finalizing the list, rather than allowing the check to be
silently skipped. This is the structural escalation governing law 3
calls for once a prompt-only fix has failed, not a further prompt-wording
attempt.

**REOPENED AGAIN (2026-07-09, see engine/decisions.md):** three further
prompt-only attempts to get `assumption_check`'s finding propagated into
`assumptions` (a cross-field consistency rule, then explicit
non-redundancy framing plus a paired worked example) all failed
identically on A04, and a full 30-test re-validation showed the same
propagation gap recurring in roughly half of ALL tests where
`assumption_check` found something -- not an A04-specific quirk.
**Decision: CHANGE — add `has_assumption: bool`**, ordered before
`assumption_check`, so the model commits to a low-entropy yes/no answer
before writing the free-text justification or the list. Paired with a
code-level auto-repair validator (`_clean_up_cross_field_issues`,
`src/interpretation/schema.py`): if `has_assumption` is `True` and
`assumptions` is still empty, `assumption_check`'s own sentence is
relocated into `assumptions` rather than left contradicting it. This
doesn't invent content (it's the model's own text) and doesn't parse or
guess at the free-text field's meaning (gated purely on the boolean).

### `inferences`
1. **Purpose:** the model's own read on what the evidence means — the one tier deliberately allowed to go beyond exactly what was said.
2. **Definition:** unchanged — hedge-word confidence cap (fixed this round to catch "possible" as well as "possibly") is the intended control here; no evidence this round of new leaks beyond what's already being managed.
3. **Type:** `List[Inference]` (unchanged)
7. **Downstream consumer:** `ConversationState.inferences`.
**Decision: KEEP, unchanged (re-verify hedge-cap fix on next test).**

### `unknowns`
1. **Purpose:** genuine information gaps preventing full understanding of the situation.
2. **Definition (v0.8, why it failed):** every unknown produced across all 5 runs read like a career coach brainstorming next-step questions ("What kind of job would be a good fit?", "How can I prioritize my wellbeing?") rather than a gap in understanding *what already happened*. This is the mirror image of the assumptions problem — instead of hallucinating causes, the model hallucinates forward-looking planning questions.
3. **Type:** `List[str]` (unchanged)
4. **Allowed values (v0.9):** an unknown must be phrased as a gap in facts about the situation as it currently stands — never a "what should I do" / "how do I" / "what steps" planning question. Those belong to a future Planner layer, not Interpretation.
5. Examples: GOOD: "Has the boss given any reason for the delay?" BAD: "What kind of job would be a good fit?" (this is coaching, not a gap in the evidence).
6. **Validation:** possible cheap heuristic — flag/reject unknowns starting with "how can I," "what should I," "what steps" as a pattern-match backstop, similar in spirit to the hedge-word check.
7. **Downstream consumer:** `ConversationState.unknowns`, unknown-reconciliation logic in `builder.py`.
**Decision: CHANGE (redefine + add pattern-based backstop).**

### `biases`
1. **Purpose:** rare, evidence-backed cognitive bias flags.
2. **Definition:** unchanged — working as intended (mostly empty, existing evidence-grounding + dedup filters holding).
3. **Type:** `List[Bias]` (unchanged)
7. **Downstream consumer:** `ConversationState.biases`, `judgment/engine.py`'s `biases_surfaced` count.
**Decision: KEEP, unchanged.**

### `entities`
1. **Purpose:** people/orgs/stakeholders mentioned.
2. **Definition (v0.8 issue):** no grounding filter at all — only possessive-stripping and pronoun-exclusion. Latest test showed fabricated entities ("career coach," "therapist," "self-care") pulled directly from a corrupted `stakes` field in the same generation.
3. **Type:** `List[str]` (unchanged)
6. **Validation (new):** add the same word-overlap grounding filter already used for goals/decision_options/biases. **But test this AFTER the `impact_domains` fix**, since the contamination may have been fully caused by the old free-text `stakes` field leaking prose — now that it's a closed enum, that specific contamination vector should be structurally impossible. If fixing `impact_domains` also cleans up `entities`, a separate filter may be unnecessary complexity.
7. **Downstream consumer:** `ConversationState.stakeholders`.
**Decision: CHANGE — add grounding filter, but sequence the test after `impact_domains` to isolate cause.**

### `clarity_score` / `requires_clarification`
No issues observed this round. **Decision: KEEP, unchanged.**

**REOPENED (2026-07-09, see engine/decisions.md):** the 30-test `gpt-4o-mini`
validation run (`experiments/confidant-validation/log.md`, Run 2) directly
contradicts the "no issues observed" call above. This was the single most
repeated defect pattern across the entire 30-test log (C01, C02, C03, E03,
X04), with X04 the worst case: `clarity_score=0.0` (the lowest, most honestly
calibrated clarity signal in the whole run) paired with
`requires_clarification=False` — the starkest, most indefensible instance of
the pattern. Root cause: zero prompt guidance existed for either field (no
definition, no threshold, no example) and no cross-field validator connects
them. **Decision: CHANGE — add explicit prompt guidance defining the
relationship between the two fields, with a concrete threshold anchor and a
worked example.** No code-level validator yet, per this codebase's own
"typed over prompted, once a prompt-only fix has failed" discipline — this is
the first prompt attempt on this specific pair, so try that first and
re-test against C01/X04 before considering a structural backstop.

---

## Part 4 — Cross-cutting finding (not an Interpretation field, but surfaced by this audit)

### `ConversationState.agency_level`
Applying the "what breaks if this disappears" test to the surrounding state, not just Interpretation: `agency_level` is declared in `engine/state.py`, defaults to `0.0`, and **is never written to anywhere in the pipeline** — confirmed by direct code search, not inference. No field in `Interpretation` maps to it, `builder.py` never touches it. Displaying `0.0` in every state table implies a computed value where none exists — this is a minor but real honesty problem in the tool's own output.
**Recommendation:** either remove it until agency-scoring is actually designed, or leave it but rename/comment it explicitly as `# NOT YET IMPLEMENTED` so it doesn't read as a working, if-currently-zero, signal. Not urgent, but cheap to fix alongside this version and worth doing while we're here.

(`ConversationState.decision` was checked too and is *not* the same kind of issue — it's an intentionally deferred field tied to the not-yet-drafted Commit phase, already documented as such in `state.py`'s comments.)

---

## Summary table

| Field | Decision | Confidence this fixes it |
|---|---|---|
| `urgency` | Harden to real `Literal` | High — free, structural |
| `stakes` → `impact_domains` | Free string → multi-label closed enum, renamed | High — structural, but enum-enforcement itself is a testable bet |
| `emotional_signals` | Keep structured object; add `source` field + worked examples (not `subject` — see field detail) | Medium — addresses the diagnosed gap (no examples), not yet proven |
| `surface_complaint` | Define as concise-restatement objective (not word-count rule) | Medium |
| `core_question(_confidence)` | No change; re-test after `impact_domains` fix | N/A |
| `observed_facts` | No change | — |
| `claims` | No change | — |
| `goals` | Tighten definition, reconsider threshold | Medium |
| `decision_options` | No change | — |
| `assumptions` | Add cross-field dedup filter; **REOPENED 2026-07-09** — add mandatory `assumption_check` reasoning field, then (after 3 prompt-only attempts to propagate its finding all failed) **REOPENED AGAIN** — add `has_assumption: bool` + code-level auto-repair validator | High for this specific new failure shape; boolean-gate fix not yet re-tested |
| `inferences` | No change | — |
| `unknowns` | Redefine + pattern backstop | Medium |
| `biases` | No change | — |
| `entities` | Add grounding filter, sequenced after `impact_domains` fix | Medium — may be redundant if `impact_domains` fix resolves it |
| `clarity_score` / `requires_clarification` | **REOPENED 2026-07-09** — add prompt guidance connecting the two fields | Medium — first prompt attempt on this pair; re-test before considering a structural backstop |
| *(state)* `agency_level` | Remove or mark unimplemented | — |

---

## Schema-wide conventions (new, standardized this round)

- **All scalar and enum values are lowercase snake_case** (`urgency: "high"`, `impact_domains: ["professional", "financial"]`, `source: "explicit"`). Standardized explicitly now, while the schema is still small, specifically to prevent per-field casing drift as more fields get added over time.

All open questions from the previous draft (`emotional_signals` shape, `impact_domains` category design, enum casing) are now resolved.

Next step per the agreed process: write the v0.8→v0.9 migration document, then and only then write the new prompt.
