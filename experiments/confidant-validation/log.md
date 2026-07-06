# Confidant Architecture Validation -- Experiment Log

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
Planner -> Response Generator.

---

## C01 -- Career -- Missing information

**Timestamp**: 2026-07-06T05:27:38Z - 05:32:48Z
**Git commit**: `0f192cf8656c35c2ef3b5c2d9bd55520883a9d6b`
**Branch**: `feature/interpretation-object`
**GitHub Actions run**: https://github.com/bvenky-pixel/sensemaking-engine/actions/runs/28769896501
**Model / Provider**: openrouter/free (primary), llama3.2:3b via ollama (automatic fallback) -- unmodified default configuration
**Provider fallback**: yes -- Planner and Response each fell back openrouter -> ollama after one failed openrouter attempt each (see Runtime Metrics)

### Input

> I've been trying to move from my current team to the Product team for a few months now.

### Pipeline Outputs

**Interpretation** (verbatim):
```
{'urgency': 'low', 'impact_domains': ['professional'], 'emotional_signals': [], 'surface_complaint': 'User has been trying to move from current team to Product team for a few months.', 'core_question': 'What should the user do regarding their attempt to move to the Product team?', 'core_question_confidence': 0.3, 'observed_facts': ['User has been trying to move from current team to Product team.', 'User has been attempting the move for a few months.'], 'claims': ['User wants to move to the Product team.', 'User has been trying to move for a few months.'], 'goals': ['Move to the Product team.'], 'decision_options': [], 'assumptions': [], 'inferences': [{'reading': "The user's prolonged attempt suggests they may be encountering resistance or lack of progress.", 'confidence': 0.3}], 'unknowns': ['What response has the user received regarding their move attempt?', 'What obstacles have they encountered?'], 'biases': [], 'entities': ['current team', 'Product team'], 'clarity_score': 0.8, 'requires_clarification': False}
```

**World State** (rendered table):
```
surface_complaint        | User has been trying to move from current team to Product team for a few months.
core_question            | What should the user do regarding their attempt to move to the Product team?
core_question_confidence | 0.3
assumptions              | []
inferences               | ["The user's prolonged attempt suggests they may be encountering resistance or lack of progress. (confidence=0.30)"]
biases                   | []
clarity_level            | 0.8
phase                    | discover
facts                    | - User has been trying to move from current team to Product team. (status=active)
                          | - User has been attempting the move for a few months. (status=active)
claims                   | - User wants to move to the Product team. (status=active)
                          | - User has been trying to move for a few months. (status=active)
goals                    | - Move to the Product team. (status=active)
decisions                | []
unknowns                 | - What response has the user received regarding their move attempt? (status=open)
                          | - What obstacles have they encountered? (status=open)
entities                 | - current team (status=active, type=unknown)
                          | - Product team (status=active, type=unknown)
```

**Judgment** (verbatim):
```
{'primary_problem': 'Lack of progress due to unknown response and obstacles in the move attempt.', 'primary_goal': 'Move to the Product team.', 'current_focus': 'Seeking information about the response received and obstacles encountered regarding the move attempt.', 'key_blockers': ['Unknown response from stakeholders about the move attempt', 'Unidentified obstacles encountered in the move process'], 'open_unknowns': ['What response has the user received regarding their move attempt?', 'What obstacles have they encountered?'], 'active_decisions': [], 'contradictions': [], 'risks': ['Continued lack of response may prolong the move attempt, delaying career progression.'], 'opportunities': ['A positive response could enable a swift transition to the Product team.'], 'confidence': 0.3, 'supporting_evidence': ['User has been trying to move from current team to Product team.', 'User has been attempting the move for a few months.', 'Move to the Product team.', 'What response has the user received regarding their move attempt?', 'What obstacles have they encountered?']}
```

**Planner** (verbatim):
```
{'primary_objective': "Provide guidance on how to proceed with the user's move attempt to the Product team.", 'rationale': 'The primary problem identified is a lack of progress due to unknown response and obstacles in the move attempt. The primary goal remains to move to the Product team. The current focus should be on seeking information about the response received and obstacles encountered regarding the move attempt. Key blockers include an unknown response from stakeholders and unidentified obstacles encountered in the move process.', 'conversational_strategy': "Seek clarification on the user's response and obstacles, and provide guidance on how to address these issues.", 'resolution_blocker': 'Unknown response from stakeholders about the move attempt', 'priority_topics': [], 'questions_to_explore': [], 'assumptions_to_test': ['User wants to move to the Product team.', 'User has been trying to move from current team to Product team.'], 'planning_constraints': [], 'desired_outcome': 'A positive response could enable a swift transition to the Product team.', 'temporal_horizon': 'near_term', 'confidence': 0.3}
```

**Response** (verbatim, user-facing):
```
The user has been trying to move from current team to Product team for a few months.

Please provide more context or information about the specific issues you are facing during your transition process.
```
`[confidence=0.5]`

### Runtime Metrics

| Stage | Provider (final) | Prompt Tok | Completion Tok | Reasoning Tok | Total Tok | Latency | Reliability |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Interpretation | openrouter/free | 3,563 | 1,443 | 1,396 | 5,006 | 23.4s | 1/1 (100%) |
| Judgment | openrouter/free | 2,153 | 908 | 862 | 3,061 | 30.7s | 1/1 (100%) |
| Planner | ollama/llama3.2:3b | 3,324 | 758 | 301 | 4,082 | 117.1s | 1/2 (50%, openrouter attempt failed, fell back) |
| Response | ollama/llama3.2:3b | 3,322 | 148 | 0 | 3,470 | 44.1s | 1/2 (50%, openrouter attempt failed, fell back) |
| **Pipeline Total** | -- | 12,362 | 3,257 | 2,559 | 15,619 | 215.2s | 4/6 (67%) |

Retry count: 2 (one openrouter->ollama fallback each for Planner and Response). Estimated cost: $0.0000 (free-tier models both providers).

### Evaluation

| Dimension | Score (1-10) | Notes |
| --- | --- | --- |
| Interpretation | 7 | Correctly extracted facts/goal/unknowns matching the test's "missing information" nature; inference appropriately hedged with confidence=0.3. Deducted for `requires_clarification=False` sitting inconsistently against `core_question_confidence=0.3` and two open unknowns. |
| State quality | 8 | Faithful, structurally clean reflection of Interpretation; correctly sparse (no invented assumptions/biases). Inherits Interpretation's minor inconsistency, no defects of its own. |
| Judgment quality | 7 | Correctly names the missing-information gap as the primary problem; confidence (0.3) stays consistent with Interpretation's. Deducted for `supporting_evidence` blending the two open unknowns in with actual observed facts -- evidence and gaps are conceptually different things. |
| Planning quality | 6 | `conversational_strategy` correctly aims at clarification (the right move for this test); `assumptions_to_test` is a nice touch. Deducted for `desired_outcome` framing a hoped-for future state ("a positive response could enable...") rather than a concrete near-term conversational outcome -- a mild premature-planning symptom, though it didn't leak into the final response. |
| Response quality | 4 | Correctly chose to ask a clarifying question instead of giving premature advice -- but the reply opens with a leaked third-person restatement ("The user has been trying to move...") instead of speaking to the user directly ("You've been trying..."). A real user would find this reply broken/robotic. |
| Epistemic discipline | 8 | Confidence stayed low and consistent (0.3) through Interpretation/Judgment/Planner; inferences explicitly confidence-scored; no fabricated facts; sparse-by-default held. Response's independent jump to confidence=0.5 has no visible derivation from Planner's 0.3. |

### Failure Analysis

- **Response Generator voice defect (most severe)**: the response opens in third person ("The user has been trying...") instead of addressing the user directly. This is a concrete, user-facing quality bug, not a stylistic nitpick -- a real user would find it strange/broken.
- **Interpretation self-assessment inconsistency**: `requires_clarification=False` alongside `clarity_score=0.8` doesn't square with `core_question_confidence=0.3` and two open unknowns -- and the system ultimately DOES ask a clarifying question anyway, so the flag itself isn't trustworthy signal here.
- **Judgment evidence/gap blending**: `supporting_evidence` includes the two open unknowns themselves, not just observed facts -- conflates "what we know" with "what we don't know yet."
- **Planner's premature-outcome framing**: `desired_outcome` describes a hoped-for external result rather than what this turn itself can accomplish -- a mild version of the premature-planning failure mode this test category watches for, though it stayed contained (didn't surface as premature advice in the actual Response).
- **Confidence discontinuity**: Response's confidence=0.5 is unexplained given upstream confidence was 0.3 throughout.

### Success Analysis

- Correctly recognized this as a missing-information case and chose to ask rather than advise -- the core capability this test targets.
- Confidence stayed low and consistent across Interpretation/Judgment/Planner (0.3), an honest signal given how little the user said.
- Clean epistemic-tier separation held: observed facts vs. claims vs. inferences vs. unknowns stayed distinct, with the one inference explicitly confidence-scored.
- No hallucinated details or fabricated backstory beyond what the single input sentence supports.
- Sparse-by-default held throughout (no invented assumptions/biases).
- The existing provider-fallback mechanism (System Architecture v2's call-level plumbing) worked exactly as designed under real rate-limit pressure -- two stage failures were transparently recovered without the turn failing.

### Overall Verdict

**Acceptable.** The architecture's core targeted capability -- recognizing missing information and asking rather than jumping to advice -- worked, and epistemic discipline (confidence calibration, evidence/inference separation, no fabrication) was strong. It falls short of "Good" because of one concrete, user-facing defect (Response Generator's third-person voice leak) plus two smaller but real cross-stage inconsistencies (Interpretation's `requires_clarification` flag, Judgment's evidence/unknown blending) that don't break this turn but are worth tracking across the dataset if they recur.
