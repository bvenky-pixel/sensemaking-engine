# Insight Engine Cross-Run Merge — Design Proposal

**Status:** DISCUSSION DRAFT (2026-07-19, backlog #293, see
engine/decisions.md "Insight Engine: cross-run merge design proposal
drafted"). Written at the founder's explicit direction, alongside a
separate, already-shipped narrow fix (see engine/decisions.md "Insight
Engine: keep re-offering existing evidence sessions across runs") that
stops an existing Insight's evidence sessions from silently rotating
out of the recency window `get_session_texts_for_insights` reads from.
That fix ensures the SAME evidence keeps getting a chance to be
re-considered every run -- it does NOT address the deeper question this
document is about: deciding whether two SEPARATE runs' output describe
the same underlying theme, so a recurring pattern doesn't flicker
in and out of existence (or get reworded every run) purely from
LLM non-determinism or evidence-window churn.

This is a design document, not a schema specification.

No prompt, schema, or code changes are implied by this document.

---

# Executive Summary

`replace_insights` (`src/api/db.py`) truncates and replaces an
account's entire `insights` table on every `run_insight_detection`
run -- confirmed, there is no merge logic today. Combined with the
LLM call having zero memory of any prior run, two consequences follow:

1. A theme evidenced by a session that ages out of the recency window
   (partially mitigated by the narrow fix referenced above, but not
   eliminated -- grounding can still fail even when the session is
   still offered, if the model doesn't re-cite it) can simply
   disappear between runs.
2. Even with identical input sessions, a temperature=0.15 free-text
   LLM call has no guaranteed wording stability -- the same real
   pattern could be reported as "Decisions paused pending more
   certainty" in one run and "Waiting for outside confirmation before
   committing" in the next, reading to a person as two different
   observations rather than one persistent one.

Given this product's "remembers your patterns" value proposition, an
Insight that silently vanishes or reappears reworded reads as the app
forgetting -- a real trust cost once runs happen often enough for a
person to notice (today latent, since Learning/POM/Insight all stay
`workflow_dispatch`-only per backlog #268's confirmed manual-only
cadence).

---

# Proposed Approach: Feed Prior Themes Back Into the Same Call

Rather than building a second mechanism (fuzzy text matching, embedding
similarity, a session-id-overlap heuristic) OUTSIDE the LLM call to
decide "are these the same theme," this proposal extends the EXISTING
single call to make that decision itself -- same "one call, one schema"
discipline this module's own docstring already commits to, and the same
reasoning `src/pom/engine.py`'s mechanical-over-invented-ML choices
follow elsewhere: the model already has to read and reason over session
content to find themes in the first place; asking it to also compare
against a short list of prior themes is a strictly smaller addition
than building a second matching system.

## Proposed Signature Change

```python
def run_insight_detection(
    session_texts: List[Tuple[str, str, str]],
    prior_insights: Optional[List[Insight]] = None,
    tracker: Optional[UsageTracker] = None,
) -> List[Insight]:
```

`prior_insights` defaults to `None` (a true no-op for every existing
call site until `scripts/run_insight_detection.py` is updated to pass
it) -- same default-argument discipline this codebase uses everywhere
a new parameter is threaded in without breaking existing callers.

## Proposed Prompt Addition (`src/insight/prompt.py`)

A new labeled section in `build_messages`, populated only when
`prior_insights` is non-empty:

```text
PREVIOUSLY IDENTIFIED THEMES (from the last time this was run)
- theme: "Decisions paused pending more certainty"
  detail: "..."
- theme: "..."
  detail: "..."

If a theme you would otherwise report describes the SAME underlying
recurring pattern as one listed above, reuse ITS EXACT theme wording
rather than inventing new phrasing for the same thing -- a person
should see one persistent observation, not two different-sounding ones
for the same real pattern. If a previously identified theme is no
longer supported by the CURRENT session evidence given to you, simply
do not include it -- do not carry it forward out of habit. These prior
themes are context only, never evidence themselves; every theme you
report, prior or new, must still satisfy law 2 (traceable to at least
two of the ACTUAL sessions given to you this run).
```

Deliberately: prior themes are passed as `theme`/`detail` text only,
never their old `evidence_session_ids` -- the model must still ground
every theme (old or new-sounding) against THIS run's real session
content, never trust its own past output as evidence. This preserves
`_enforce_grounding`'s existing, unmodified role as the final,
mechanical safety net: even if the model mishandles the wording-reuse
instruction, an insight that isn't actually grounded in >= 2 real
session ids from THIS run's `known_session_ids` is still dropped,
exactly as today.

## Call Site Change (`scripts/run_insight_detection.py`)

Before recomputing, fetch `db.get_insights(user_id)` and pass the
result as `prior_insights`. `replace_insights` itself needs NO change --
it still truncates and replaces with whatever `run_insight_detection`
returns this run; the merge/carry-forward decision now happens inside
the one LLM call rather than as a separate database operation, so the
existing "latest wins, one account's own share only" truncate-and-
replace semantics stay exactly as documented today.

---

# What This Does NOT Solve

* **Guaranteed wording stability.** This is a prompt instruction, not a
  mechanical guarantee -- an LLM could still reword a theme it should
  have reused verbatim. No proposal here removes that risk entirely;
  it only gives the model the information it needs to avoid it, which
  it doesn't have today.
* **Detecting cross-run duplicates automatically.** This proposal
  deliberately does NOT add a second matching mechanism (embedding
  similarity, fuzzy string match) to independently verify or fall back
  when the model doesn't self-merge correctly -- see Open Questions
  below for why that's deferred, not rejected.
* **Whether two runs' near-identical-but-not-identical wording should
  ever be treated as authoritatively "the same theme" by anything other
  than the model's own judgment.** This proposal accepts the model as
  the sole arbiter, consistent with how this module already trusts the
  model's own theme/detail synthesis (a different question from
  evidence grounding, which IS mechanically enforced).

---

# Open Questions

## Is prompt-level merge instruction reliable enough on its own?

No real multi-run production data exists yet to answer this (Insight
Engine has computed at most once per account in practice so far, per
backlog #268's confirmed manual-only cadence). This proposal recommends
shipping the prompt/signature change and OBSERVING real successive-run
behavior before deciding whether a mechanical fallback matcher is
needed -- same "calibrate against real data, don't guess a threshold"
discipline as backlog #213/#249's own deferred-until-real-data posture.

## Should a mechanical fallback exist at all?

If observed data shows the model reliably reuses wording when
instructed to, a fallback matcher is unnecessary complexity. If not,
the next design pass would need to pick a concrete mechanism (candidates:
normalized-text exact/near match on `theme`; embedding cosine similarity
above a threshold; session-id-overlap ratio between an old and new
insight's evidence sets) -- each is a real, separate design decision
deferred here deliberately, not silently.

## Cost

`prior_insights` adds prompt tokens proportional to how many themes an
account currently has -- in practice small (an account with dozens of
standing Insights would itself be a surprising, probably-wrong outcome
given `MIN_EVIDENCE_SESSIONS=2`'s own restraint). No new LLM call is
introduced.

---

# Success Criteria

If built, this should:

* Never weaken `_enforce_grounding`'s existing mechanical floor -- a
  prior theme carried forward in wording only still needs real,
  current evidence to survive.
* Be observable: `scripts/run_insight_detection.py`'s own printed
  output should make it easy to see, across two successive real runs,
  whether a theme's wording stayed stable when its evidence was still
  present.
* Not require a second matching mechanism until real data shows the
  prompt-only approach insufficient.

# Recommendation

Ship the signature/prompt change above (low risk, no schema change, no
new LLM call, `prior_insights` defaults to a no-op for any caller that
doesn't pass it), then observe at least two successive real
`workflow_dispatch` runs against an account with standing Insights
before deciding whether a mechanical fallback matcher is worth its own
added complexity.
