# Judgment v2 — Calibration & Evaluation Review

**Status:** Review only. No code, prompt, or schema changes made. This
document is the design review requested before any calibration work
begins on Judgment — the objective is to improve Judgment quality before
Planner starts depending on it, without adding features to a
newly-stabilized architecture.

**What this review is based on:**
- `engine/specs/judgment-specification-v2.md` (the frozen spec)
- `src/judgment/prompt.py` (current `SYSTEM_PROMPT`)
- `src/judgment/schema.py` (current `Judgment` model)
- **One genuine, current-code Judgment output** — a real single-turn run
  against `openrouter/free` (this session, `feature/interpretation-object`
  commit `679f8f7`), reproduced in full below. This is the freshest real
  data available: the last CI "WorldState walkthrough" run
  (`worldstate-walkthrough.yml`, run `28741577048`) executed at commit
  `79c31e438c8`, which **predates** the Judgment v2 implementation
  (`40eabaf`) — its logs contain no Judgment output at all and are not
  usable here. **This review is therefore built on n=1 real sample, not a
  multi-turn trace** — a real limitation, flagged explicitly rather than
  papered over with invented turns. A fresh multi-turn walkthrough run
  against the current code would meaningfully strengthen this review;
  I did not run one without asking, given today's free-tier load and the
  explicit "do not implement/run anything yet" scope of this task.

## The evidence sample

Input message: *"I've been trying to move from my current team to the
Product team for a few months now."* (turn 1 of the Sarah/Product-team
scenario.)

Resulting `WorldState` (abbreviated to the fields Judgment reasons over):
- `surface_complaint`: "User is trying to move to the Product team."
- `core_question`: "Can the user successfully transition to the Product
  team?" (confidence 0.6)
- `facts`: "User is currently on a non-Product team"; "User has been
  attempting to move to the Product team for several months"
- `claims`: "User wants to join the Product team"
- `goals`: "Move to the Product team"
- `unknowns`: "What is preventing the user from moving to the Product
  team?"; "Has the user received any feedback or guidance on this
  request?"
- `entities`: "Product team"; "current team"

Resulting `Judgment` (verbatim):

```json
{
  "primary_problem": "Unknown obstacles preventing the user's transition to the Product team",
  "primary_goal": "Move to the Product team",
  "current_focus": "Identify obstacles preventing the user's move to the Product team",
  "key_blockers": [],
  "open_unknowns": [
    "What is preventing the user from moving to the Product team?",
    "Has the user received any feedback or guidance on this request?"
  ],
  "active_decisions": [],
  "contradictions": [],
  "risks": [
    "Lack of information about obstacles could delay transition",
    "Potential lack of feedback may indicate insufficient support for the move"
  ],
  "opportunities": [
    "User's persistence and desire may facilitate transition",
    "Potential feedback could provide guidance on the transition"
  ],
  "confidence": 0.4,
  "supporting_evidence": [
    "User is currently on a non-Product team",
    "User has been attempting to move to the Product team for several months",
    "User wants to join the Product team",
    "Move to the Product team",
    "What is preventing the user from moving to the Product team?",
    "Has the user received any feedback or guidance on this request?",
    "User is trying to move to the Product team.",
    "Can the user successfully transition to the Product team?"
  ]
}
```

---

## 1. Field-by-field review

### `primary_problem`
1. **Meaningful value?** Yes — it correctly synthesizes "why is progress
   blocked" from the unknowns, rather than just restating a fact.
2. **Grounded?** Yes in this sample — every word traces to the two
   unknowns.
3. **Noisy over time?** Real risk once WorldState has multiple candidate
   problems (several open goals/unknowns at once) — nothing in the prompt
   says how to pick *one* "primary" problem when more than one is
   plausible. Untested at that scale.
4. **Constrain more?** Yes — add an explicit tie-breaking rule (see
   §2).
5. **Schema change?** No.

### `primary_goal`
1–2. **Value / grounded?** Yes, but note this field is a near-verbatim
   copy of `WorldState.goals[0].content`, not a synthesis. That's
   *correct* per the spec — this is an observation field ("select the
   highest-priority active goal"), not an assessment — so a copy is the
   right behavior, not a symptom of laziness.
3. **Noisy?** Low risk while WorldState has ≤1 active goal. Untested with
   multiple concurrent active goals (no rule yet for which one is
   "primary" — see `key_blockers` discussion, same gap pattern).
4. **Constrain more?** Only once multi-goal WorldStates are tested.
5. **Schema:** No.

### `current_focus`
1. **Value?** Marginal in this sample — compare it to `primary_problem`:

   > `primary_problem`: *"Unknown obstacles preventing the user's
   > transition to the Product team"*
   > `current_focus`: *"Identify obstacles preventing the user's move to
   > the Product team"*

   These are the same idea stated twice with different verbs
   ("obstacles preventing transition" / "identify obstacles preventing
   move"). The spec defines `current_focus` as "narrower and more
   immediate than primary_goal" — but nothing distinguishes it from
   `primary_problem`, which is exactly where it collapsed here.
2. **Grounded?** Yes, but redundantly with `primary_problem`.
3. **Noisy?** This *is* the noise, concretely observed, not
   hypothetical.
4. **Constrain more?** Yes — this is the clearest, best-evidenced
   candidate for a prompt fix in this whole review (see §2).
5. **Schema change?** Possibly — see §3 (merge candidate).

### `key_blockers`
1–2. **Value / grounded?** Correctly empty here — no Fact yet
   establishes a concrete blocker, only two open *unknowns* about why
   there might be one. The model did **not** manufacture a blocker out
   of the unknowns. This is the "sparse by default" principle working
   exactly as intended — a genuinely good sign, not a gap.
3. **Noisy?** Untested on a WorldState with real Facts describing an
   actual blocker (e.g. later turns in this same scenario, once Sarah's
   "team is frozen" fact lands) — that's the real test of whether this
   field stays disciplined.
4. **Constrain more?** No — current behavior is already correct;
   don't fix what isn't broken.
5. **Schema:** No.

### `open_unknowns` / `active_decisions`
Both are observation fields and both behaved correctly here — exact
copies of the two real `Unknown`s, empty `active_decisions` because no
`Decision` objects exist yet. No issues in this sample.

### `contradictions`
Correctly empty — no conflicting Facts exist in this WorldState.
**Important known gap, not this field's fault**: `src/state/builder.py`
has no contradiction *detection* at the State Builder layer (documented,
deliberate — see `engine/decisions.md`), so Judgment's contradictions
field can only ever be as good as WorldState's raw material. If two
literally-contradictory Facts both land in WorldState (e.g. "team is
frozen" vs. "team is not frozen"), whether Judgment actually flags that
as a contradiction is genuinely untested — this sample never exercised
it. **Recommend testing this specifically** before trusting the field.

### `risks` and `opportunities`
See the dedicated section below — this is where the sample shows the
clearest signal.

### `confidence`
See dedicated section below.

### `supporting_evidence`
See dedicated section below — the single biggest finding in this
review.

---

## 2. Supporting Evidence — deep dive

**The user's question, confirmed against real data**: "Currently it
often includes nearly every relevant object" — in this one sample, **all
8 pieces of WorldState content appear in `supporting_evidence`**, and
WorldState only *had* 8 pieces of content (2 facts, 1 claim, 1 goal, 2
unknowns, plus the `surface_complaint` and `core_question` text fields).
Every single thing Judgment could have cited, it did cite. That's not
"selective evidence for specific conclusions" — that's a transcript dump
dressed as a citation list.

**Why this happens, structurally**: `supporting_evidence` is a single
flat `List[str]`, **global to the whole Judgment object** (see
`src/judgment/schema.py`). The model has no structural slot to say
"*this* risk is justified by *that* fact" — its only way to show its
work is to append everything relevant anywhere in the response to one
undifferentiated list. Given that shape, "cite everything" is the path
of least resistance, not a prompting failure.

**Would per-conclusion evidence attachment help? Yes, directly.** Right
now a reader cannot tell whether `opportunities[0]` ("User's persistence
and desire may facilitate transition") is backed by anything at all, or
whether it's backed by the same two Facts that also back
`primary_problem`. Attaching evidence per-field would force the model to
show *which* conclusion each citation supports — and an empty evidence
list on a given conclusion becomes a legible, visible signal ("this
opportunity has no real support") instead of being invisible inside one
big undifferentiated bucket.

**Recommendation**: restructure `supporting_evidence` from a flat list
into a mapping (or list of `{claim, evidence}` pairs) keyed to the
specific conclusion field each entry supports. See §3 (schema) for the
concrete shape.

---

## 3. Risks — deep dive

Both risks in the sample are real content, but they illustrate two
different failure directions the user asked about:

> *"Lack of information about obstacles could delay transition"*

This is a **tautological restatement** of `unknowns[0]`, reworded as a
"risk." It adds essentially zero new information — "we don't know X" and
"not knowing X could delay things" are the same fact wearing a different
hat. It isn't wrong, but it's dead weight: a reader gains nothing they
didn't already have from `open_unknowns`.

> *"Potential lack of feedback may indicate insufficient support for the
> move"*

This is a **genuine speculative leap**. Nothing in WorldState says
anything about organizational "support" for the move — that's an
inference stacked on top of an unknown ("has the user received
feedback?"), not a conclusion drawn from evidence. This is precisely the
"drift toward plausible guesses" the user flagged, caught concretely, not
hypothetically.

**Recommendation**: the prompt should require every risk to name the
*specific* WorldState content (a Fact, Claim, or Unknown) it's derived
from, and explicitly reject "risk = an unknown restated with an anxious
tone." A risk should describe a plausible *negative consequence* of
something Facts/Claims establish, not restate the unknown itself, and not
speculate about causes (organizational support, feelings, motives) that
nothing in WorldState actually asserts.

---

## 4. Opportunities — deep dive

Same pattern, mirrored:

> *"User's persistence and desire may facilitate transition"*

"Persistence" is a generous read of "has been attempting for several
months" (a Fact) and "desire" a generous read of "wants to join" (a
Claim) — technically traceable, but this is character-attribution
("persistence") layered on top of neutral facts, not something WorldState
actually states.

> *"Potential feedback could provide guidance on the transition"*

Same tautological-restatement issue as the parallel risk — this just
flips `unknowns[1]` from "we don't know if feedback came" into an
optimistic frame instead of a pessimistic one, with the same emptiness on
both sides.

**Answering the user's direct question — "should opportunities require
explicit supporting evidence, or disappear entirely when unsupported?"**:
require explicit evidence, don't force disappearance. An early,
sparse WorldState *should* often have zero well-grounded opportunities —
per the "sparse by default" principle already working correctly
elsewhere (`key_blockers` in this same sample) — so forcing the field to
always contain something is the wrong direction. The fix is the same one
as for risks: require each opportunity to name the specific WorldState
content it derives from, and let the list come back empty when nothing
qualifies, exactly like `key_blockers` already does correctly.

---

## 5. Confidence — deep dive

The user asked whether the prompt should explicitly define what
confidence *represents* (completeness of evidence vs. certainty of
conclusions vs. confidence in WorldState itself).

**Current prompt text** (`src/judgment/prompt.py`):
> *"confidence: your overall confidence (0.0-1.0) in this assessment as a
> whole, given how much WorldState actually supports it. Sparse,
> early-conversation WorldState should produce a LOW confidence, not a
> falsely reassuring one."*

This is already closer to "**completeness of evidence**" than to "model
certainty" — and the one real data point is consistent with that
reading: a genuinely sparse WorldState (2 facts, 1 claim, 1 goal, 2
unknowns, nothing resolved) produced 0.4, a properly humble score, not a
falsely confident one. That's a good sign, but it's **n=1** — nowhere
near enough to call this calibrated.

**The gap**: the definition is directionally right but not explicit. It
doesn't rule out the other two readings, and a model can drift toward
"how certain do I feel" under different phrasing pressure or a different
underlying model. **Recommendation**: make the definition unambiguous and
exhaustive — state plainly that confidence measures *evidentiary
completeness of the WorldState*, not the model's own certainty, and not a
judgment about whether WorldState itself is trustworthy (that's a
different, currently-unmeasured question this schema doesn't ask about).
See §2 in the prompt recommendations below for exact wording.

---

## 6. Conciseness / information density

Counting the sample: the *evidence list* (8 quoted strings, largely
reproducing WorldState content verbatim) is the single largest chunk of
the output by content volume — larger than the combined
problem/goal/focus/risks/opportunities text that represents the actual
new synthesis. Put another way: a large fraction of every Judgment call's
output tokens are spent re-stating things the caller already has (it's
the one that built WorldState in the first place), not adding
information.

This matches the earlier evaluation-smoke-test finding (word-overlap
groundedness heuristic on Baseline A's evidence scored 0.85–0.89 —  i.e.
near-verbatim copies) and is structurally the same root cause as the
Supporting Evidence finding above: a global evidence bucket rewards
volume over selectivity. Fixing evidence attachment (§2/§3) should also
directly improve information density, since evidence would then need to
be *specific enough to point at one conclusion* rather than
*comprehensive enough to cover everything*.

---

## Recommended prompt improvements

Ordered roughly by expected impact, all targeting `src/judgment/prompt.py`:

1. **Differentiate `current_focus` from `primary_problem` explicitly.**
   Add a line making the distinction operational, not just descriptive:
   *"current_focus must describe an ACTION or INQUIRY the user is
   currently engaged in (e.g. 'waiting to hear back,' 'deciding between
   X and Y') — never restate primary_problem in different words. If there
   is no distinct current activity beyond the problem itself, leave
   current_focus as a shorter pointer to the same idea rather than a full
   restatement."** (Concrete, testable — a future test can check
   `current_focus != primary_problem` under paraphrase-similarity, not
   just string equality.)

2. **Make confidence's definition unambiguous.** Replace the current
   single sentence with something like: *"confidence measures how
   COMPLETE the evidentiary basis in WorldState is for this assessment —
   not how certain you personally feel, and not whether WorldState
   itself is trustworthy (a separate question this schema doesn't ask).
   A WorldState with few Facts/Claims and many open Unknowns should
   produce LOW confidence regardless of how confidently-worded the
   available content is."*

3. **Require risks/opportunities to cite specific WorldState content
   inline, and explicitly forbid restating an Unknown as a Risk or
   Opportunity without adding anything.** E.g.: *"Every risk/opportunity
   must name the specific Fact, Claim, or Unknown it is derived from. Do
   NOT restate an Unknown as a Risk by simply adding 'this could cause a
   delay' — that adds no information. A Risk/Opportunity must describe a
   plausible CONSEQUENCE of something WorldState actually asserts, not a
   rephrasing of the gap itself. If no risk/opportunity meets this bar,
   leave the list empty — an empty list is correct, not a gap to fill."*
   This is the same "sparse by default" principle Interpretation and
   State Builder already enforce elsewhere — Judgment currently doesn't
   apply it to these two fields as strictly as it should.

4. **Add a primary_problem/primary_goal tie-breaking rule** for when
   WorldState has multiple candidates (untested in the current sample,
   but a predictable failure mode once conversations get busier): *"If
   multiple issues/goals are plausible candidates for 'primary', prefer
   the one most directly blocking the others, or (if none blocks another)
   the most recently introduced one."*

## Recommended schema improvements

**One change, contingent on the prompt fix above actually landing
first**: restructure `supporting_evidence` from a flat `List[str]` into
something that ties each entry to the conclusion it supports. Two
concrete shapes, in order of preference:

- **Option A (minimal, no new types)**: keep it a list, but each entry
  becomes `"<field_name>: <quote>"` (e.g. `"risks[0]: User has been
  attempting to move to the Product team for several months"`). Cheapest
  migration, no new Pydantic model, but string-parsing the field name
  back out is fragile.
- **Option B (typed, recommended)**: a small `EvidenceEntry(field: str,
  content: str)` model, `supporting_evidence: List[EvidenceEntry]`. Same
  "content-based, not ID-based" philosophy already documented in
  `schema.py` (WorldState objects still have no stable IDs), just
  attached to a field name instead of floating free. This makes "does
  this specific opportunity have real support" a structural question
  (`any(e.field == "opportunities" for e in evidence)`), not something a
  human has to eyeball.

**Do not schema-change `risks`/`opportunities` themselves** (e.g. into
typed objects with confidence sub-scores) yet — the prompt fix in §3
above should be tried first, since the finding here is about prompting
discipline (the model isn't being told to ground these fields tightly
enough), not a shape the current `List[str]` can't express. Adding
structure before confirming the prompt fix doesn't already solve it would
be exactly the kind of premature complexity this codebase has avoided
elsewhere.

**Everything else in the schema (`primary_problem`, `primary_goal`,
`current_focus`, `key_blockers`, `open_unknowns`, `active_decisions`,
`contradictions`, `confidence`) stays as-is** — no evidence in this
review supports changing their shape, only their prompt guidance.

---

## Prioritized list of changes

Not implemented — for discussion before any work begins, per the task's
explicit scope.

1. **[Prompt]** Fix `current_focus` vs. `primary_problem` redundancy —
   clearest, most concretely-observed issue in the whole review.
2. **[Prompt]** Require risks/opportunities to cite specific WorldState
   content and forbid unknown-restatement — directly addresses the
   "drift toward speculation" the user raised, with two confirmed
   real examples.
3. **[Prompt]** Make confidence's definition explicit and exhaustive —
   low-risk, high-clarity change; current behavior is likely already
   close to correct, this just removes ambiguity.
4. **[Schema]** Restructure `supporting_evidence` to attach evidence
   per-field (Option B above) — the single highest-leverage structural
   change, but sequence it *after* item 2 lands, since better-grounded
   risks/opportunities will change what "good" per-field evidence should
   even look like.
5. **[Prompt]** Add a primary_problem/primary_goal tie-breaking rule —
   lower priority; no evidence yet that this is actually failing, just a
   predictable gap once conversations have competing goals.
6. **[Process]** Run a fresh multi-turn walkthrough against the *current*
   Judgment v2 code (the last real walkthrough predates it) before
   trusting any conclusion in this review beyond n=1 — especially the
   `contradictions` field, which this sample never exercised at all.

No changes have been made to `src/judgment/prompt.py` or
`src/judgment/schema.py`. Awaiting direction on which of the above to
implement, and in what order.
