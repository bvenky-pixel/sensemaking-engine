# Confidant Architecture Validation -- Experiment Log (Run 2)

Restarted from C01 on 2026-07-07 under the OpenRouter-only config (see
`engine/decisions.md` "Ollama removed, OpenRouter-only"). Run 1
(`run1/log.md`) scored C01-R05 under the old openrouter->ollama fallback
config and is archived -- its findings remain valid for that
configuration, but are not continued here, so this file is never a mix
of two different providers' worth of results. This is otherwise the same
experiment, same 30-test queue (`queue.md`), same rubric, same
discipline.

Append-only. Never overwrite or reorder prior entries. One entry per
completed test, in the order tests were executed (matches queue order
since tests execute strictly top-to-bottom). See `queue.md` in this same
directory for the full test list and completion status.

This experiment validates the frozen Confidant architecture
(Sensemaking Engine v1 + System Architecture v2, see
`engine/decisions.md`) as-is -- it does not modify prompts, architecture,
model choice, provider configuration, or evaluation criteria.

Each test is run once via the `single-turn-smoketest.yml` GitHub Actions
workflow (real LLM calls, `CONFIDANT_TRACK_USAGE=1`), which executes the
real pipeline end to end: Interpretation -> WorldState -> Judgment ->
Planner -> Response Generator. OpenRouter (`openrouter/free`) is the
sole provider -- a failure at any stage now fails that test's run
outright rather than falling back to a local model; a run that doesn't
complete all four stages is not scored here and stays `pending` in
`queue.md` for a retry.

**Note on model pinning starting at C01 (this run's first entry):** the
standing default (`OPENROUTER_MODEL` = `openrouter/free`) failed
repeatedly earlier on 2026-07-07 (429s and empty-content responses, with
no Ollama fallback left to catch them, per `engine/decisions.md`), so
each test below is triggered with `openrouter_model:
"openai/gpt-4o-mini"` passed as a one-off `workflow_dispatch` input to
`single-turn-smoketest.yml`. This does not touch any file in the repo --
`.env.example`'s default stays `openrouter/free` -- it is purely a
per-invocation override the workflow already supported. Every entry
below states this explicitly in its header so results are never
misread as coming from the standing default.

---

## C01 -- Career -- Missing information

**Timestamp**: 2026-07-07T15:02:02Z - 15:02:38Z
**Git commit**: `81d3ca5ab1b1ec6785a7d711716b05a501a3cfdb`
**Branch**: `feature/interpretation-object`
**GitHub Actions run**: https://github.com/bvenky-pixel/sensemaking-engine/actions/runs/28876373379
**Model / Provider**: openai/gpt-4o-mini (pinned via workflow_dispatch input, not the standing default) throughout
**Provider fallback**: none -- OpenRouter is the sole provider; no fallback exists, and all four stages succeeded on the first attempt (4/4, 100%)

### Input

> I've been trying to move from my current team to the Product team for a few months now.

### Pipeline Outputs

**Interpretation** (verbatim):
```
{'urgency': 'low', 'impact_domains': ['professional'], 'emotional_signals': [], 'surface_complaint': 'User has been trying to move from their current team to the Product team for a few months.', 'core_question': 'What is preventing the move to the Product team?', 'core_question_confidence': 0.6, 'observed_facts': ['User has been trying to move from their current team to the Product team.', 'User has been attempting this for a few months.'], 'claims': ['User wants to move to the Product team.'], 'goals': [], 'decision_options': [], 'assumptions': [], 'inferences': [], 'unknowns': [], 'biases': [], 'entities': [], 'clarity_score': 0.8, 'requires_clarification': False}
```

**World State** (rendered table):
```
surface_complaint        | User has been trying to move from their current team to the Product team for a few months.
core_question            | What is preventing the move to the Product team?
core_question_confidence | 0.6
assumptions              | []
inferences               | []
biases                   | []
clarity_level            | 0.8
phase                    | discover
facts                    | - User has been trying to move from their current team to the Product team. (status=active)
                          | - User has been attempting this for a few months. (status=active)
claims                   | - User wants to move to the Product team. (status=active)
goals                    | []
decisions                | []
unknowns                 | []
entities                 | []
```

**Judgment** (verbatim):
```
{'primary_problem': 'User is unable to move to the Product team despite trying for a few months.', 'primary_goal': '', 'current_focus': 'Identifying what is preventing the move to the Product team.', 'key_blockers': [], 'open_unknowns': [], 'active_decisions': [], 'contradictions': [], 'risks': [], 'opportunities': [], 'confidence': 0.6, 'supporting_evidence': ['User has been trying to move from their current team to the Product team.', 'User has been attempting this for a few months.', 'User wants to move to the Product team.']}
```

**Planner** (verbatim):
```
{'primary_objective': 'clarify uncertainty', 'rationale': 'The primary_problem is that the user is unable to move to the Product team, and understanding the specific barriers to this move is crucial for progress.', 'conversational_strategy': 'ask exploratory questions', 'resolution_blocker': 'missing information', 'priority_topics': ['specific reasons preventing the move', "user's motivations for the move"], 'questions_to_explore': ['What specific challenges have you faced in trying to move to the Product team?', 'Have you received any feedback from your current team or the Product team regarding your move?'], 'assumptions_to_test': [], 'planning_constraints': ['preserve user agency', 'avoid overwhelming the user'], 'desired_outcome': 'user identifies specific barriers to moving to the Product team', 'temporal_horizon': 'immediate', 'confidence': 0.6}
```

**Response** (verbatim, user-facing):
```
To better understand what might be preventing your move to the Product team, could you share what specific challenges you've faced during this process? Additionally, have you received any feedback from either your current team or the Product team regarding your move?
```
`[confidence=0.6]`

### Runtime Metrics

| Stage | Provider (final) | Prompt Tok | Completion Tok | Reasoning Tok | Total Tok | Latency | Reliability |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Interpretation | openai/gpt-4o-mini | 3,368 | 201 | 0 | 3,569 | 5.6s | 1/1 (100%) |
| Judgment | openai/gpt-4o-mini | 1,767 | 114 | 0 | 1,881 | 2.8s | 1/1 (100%) |
| Planner | openai/gpt-4o-mini | 1,974 | 211 | 0 | 2,185 | 3.9s | 1/1 (100%) |
| Response | openai/gpt-4o-mini | 1,572 | 58 | 0 | 1,630 | 2.1s | 1/1 (100%) |
| **Pipeline Total** | -- | 8,681 | 584 | 0 | 9,265 | 14.3s | 4/4 (100%) |

Retry count: 0. Estimated cost: $0.0017 (Interpretation $0.0006, Judgment $0.0003, Planner $0.0004, Response $0.0003).

### Evaluation

| Dimension | Score (1-10) | Notes |
| --- | --- | --- |
| Interpretation | 5 | `surface_complaint`/`core_question` are accurate and appropriately phrased as a genuine open question. But for a test whose Primary Capability is explicitly "missing information," `unknowns=[]` and `entities=[]` are real misses -- the two obvious follow-ups (what response has the user received, what obstacles they've hit) were never surfaced into the structured `unknowns` tier even though the prose `core_question` implies exactly that gap, and neither "current team" nor "Product team" was captured as an entity. `goals=[]` is also a miss -- `claims` states "User wants to move to the Product team" almost verbatim, which is a goal, not just a claim. `requires_clarification=False` sits inconsistently with `clarity_score=0.8`/`core_question_confidence=0.6` given the pipeline's own Response ends up being nothing but a clarifying question. |
| State quality | 7 | Faithful, structurally clean mirror of Interpretation; correctly sparse where Interpretation was sparse. Inherits Interpretation's gaps (empty unknowns/goals/entities) but adds no defects of its own. |
| Judgment quality | 5 | `primary_problem`/`current_focus` correctly name the missing-info nature of the situation in prose. But `key_blockers=[]`, `open_unknowns=[]`, `risks=[]`, and `opportunities=[]` are all empty -- a second, compounding instance of the same structured-field sparseness seen in Interpretation, on a test that specifically exists to check whether the architecture tracks open gaps. `primary_goal=''` likewise never recovers the goal that was visible in Interpretation's `claims`. `supporting_evidence` this run stayed limited to actual facts/claims (no unknowns/inferences blended in), a positive contrast with the scope-creep pattern flagged repeatedly in Run 1's log. |
| Planning quality | 8 | Well-scoped: `desired_outcome` ("user identifies specific barriers...") is concretely achievable this turn rather than a hoped-for future state; `questions_to_explore` are specific and non-leading; `planning_constraints` ("preserve user agency," "avoid overwhelming the user") show real, visible restraint. |
| Response quality | 8 | Natural second-person voice throughout, no third-person leak; faithfully executes both of Planner's `questions_to_explore` entries; appropriately brief and doesn't overstep into premature advice or reassurance. |
| Epistemic discipline | 6 | Confidence held remarkably steady at 0.6 across Interpretation/Judgment/Planner/Response -- no unexplained jump or drift. No fabricated facts anywhere. Deducted for the `requires_clarification=False` inconsistency (the flag says no clarification is needed, but the entire downstream pipeline treats this as a clarification-needed case) and for the structured gap-tracking fields (`unknowns`, `key_blockers`, `open_unknowns`) staying empty despite the prose fields in the same outputs describing exactly the gap those fields exist to hold. |

### Failure Analysis

- **Structured gap-tracking fields left empty on a missing-information test**: `unknowns` (Interpretation), `key_blockers`/`open_unknowns`/`risks`/`opportunities` (Judgment) are all empty, even though `core_question` and `primary_problem` both describe, in prose, exactly the kind of gap these fields exist to capture ("what is preventing the move"). The uncertainty is real and correctly reflected in the prose fields and in the final clarifying-question Response, but it never gets promoted into the structured fields designed to hold it -- a schema-discipline gap rather than a reasoning failure.
- **Goal never captured**: `claims` states "User wants to move to the Product team" almost verbatim, but this never gets promoted to `goals` (Interpretation) or `primary_goal` (Judgment), both of which stay empty throughout.
- **Entities dropped**: `entities=[]` despite "current team" and "Product team" being the two central, named subjects of the complaint (contrast Run 1's C01 on the same input, which captured both).
- **`requires_clarification` flag inconsistency (recurring pattern, same field flagged in Run 1's C01)**: set to `False` even though `core_question_confidence` is only 0.6, no unknowns are populated to justify that confidence, and the system's own Response is entirely a clarifying question -- the flag still doesn't reflect what the pipeline actually does downstream.

### Success Analysis

- All four stages completed on the first attempt with no provider fallback needed (OpenRouter is the sole provider under this configuration, so there is no fallback path to exercise) -- fast (14.3s total pipeline latency) and cheap ($0.0017 total).
- No fabrication: nothing in any stage's output goes beyond what the single input sentence supports.
- Confidence stayed at a single, consistent value (0.6) across all four stages -- a clean, honest calibration signal with no unexplained discontinuity (this exact defect -- Response's confidence jumping unexplained from Planner's value -- was flagged in Run 1's C01 on the same input, and does not recur here).
- Response spoke in natural second person and faithfully executed the Plan's own questions -- correctly recognized this as a missing-information case and asked rather than advised, the core capability C01 targets. This also resolves Run 1 C01's third-person voice-leak defect completely.
- Planner showed genuine, visible restraint (explicit `planning_constraints`) and set a concretely achievable `desired_outcome` rather than a premature hoped-for-future framing.
- Judgment's `supporting_evidence` stayed limited to genuine facts/claims this run, without the non-evidence scope creep (unknowns/inferences blended in) that recurred in every test of Run 1.

### Overall Verdict

**Good.** The architecture correctly recognized this as a missing-information case and produced a clean, well-targeted clarifying question with no fabrication and rock-steady confidence calibration -- a clear improvement over Run 1's C01 on the identical input (which suffered a third-person voice leak and a confidence discontinuity). Held below "Excellent" because the structured gap-tracking fields (`unknowns`, `key_blockers`, `open_unknowns`, `goals`/`primary_goal`, `entities`) stayed empty across Interpretation and Judgment despite this being precisely the test category that exists to exercise them -- the uncertainty was correctly *handled* in the final response, but not correctly *recorded* in the structured state along the way.

---
