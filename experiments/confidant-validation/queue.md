# Confidant Architecture Validation -- Test Queue (Run 2)

Restarted from C01 on 2026-07-07 under the OpenRouter-only config (see
`engine/decisions.md` "Ollama removed, OpenRouter-only"). Run 1
(`run1/queue.md`, `run1/log.md`) ran C01-R05 under the old
openrouter->ollama fallback config and is archived, not continued --
this queue and `log.md` are a full, independent 30-test run so no result
in this file is ever a mix of the two configs.

Immutable for the duration of this experiment: do not add, remove, reorder,
or reword tests while the experiment is running. This queue, plus
`log.md` in this same directory, is separate from the codebase (`src/`,
`tests/`, `engine/specs`, `engine/decisions.md`) -- it tracks a validation
experiment run against the frozen architecture, not the architecture
itself.

Rules (see the runner prompt for full detail):
- Exactly one test executes per run.
- Tests execute in order, top to bottom. No skipping, no reordering.
- A run never repeats a test already marked `complete` unless explicitly
  instructed.
- Provider/model configuration, prompts, and evaluation criteria are not
  touched by this experiment -- whatever `feature/interpretation-object`'s
  frozen defaults are at run time is what gets used.
- A test that fails before completing the full pipeline (a provider
  error at any stage, now that there is no Ollama fallback to catch one)
  is NOT marked complete and is NOT scored -- it stays `pending` and is
  retried at the next firing, per `engine/decisions.md`.

Status values: `pending` | `complete`

| ID  | Category      | Status  | User Message |
| --- | ------------- | ------- | ------------- |
| C01 | Career        | complete | I've been trying to move from my current team to the Product team for a few months now. |
| C02 | Career        | complete | My manager says I'm doing great, but I was passed over for promotion again. |
| C03 | Career        | complete | I have two job offers and can't decide which one to accept. |
| C04 | Career        | complete | I'm thinking of quitting without another job lined up. |
| C05 | Career        | complete | I feel like everyone else at work is progressing faster than I am. |
| R01 | Relationships | complete | My partner says I never listen, but I think they're overreacting. |
| R02 | Relationships | pending | My friend hasn't replied in three days. I think they're angry with me. |
| R03 | Relationships | pending | I don't know whether I should apologize first. |
| R04 | Relationships | pending | My parents want me to move back home, but I don't want to. |
| R05 | Relationships | pending | My colleague keeps interrupting me in meetings. |
| D01 | Decisions     | pending | I can afford either a house or an MBA, but not both. |
| D02 | Decisions     | pending | I want to start a company, but I'm afraid of failing. |
| D03 | Decisions     | pending | I'm considering moving to another country next year. |
| D04 | Decisions     | pending | I have too many ideas and can't choose one to pursue. |
| D05 | Decisions     | pending | Should I optimize for salary or meaningful work? |
| E01 | Emotions      | pending | I've been feeling burnt out for months. |
| E02 | Emotions      | pending | I feel guilty even when I haven't done anything wrong. |
| E03 | Emotions      | pending | I don't enjoy anything anymore. |
| E04 | Emotions      | pending | I keep procrastinating even on things I care about. |
| E05 | Emotions      | pending | I'm frustrated because nothing seems to be changing. |
| A01 | Ambiguity     | pending | Something feels off lately, but I can't explain why. |
| A02 | Ambiguity     | pending | I don't know what's wrong -- I just know I'm unhappy. |
| A03 | Ambiguity     | pending | Everyone keeps telling me I'll figure it out eventually. |
| A04 | Ambiguity     | pending | I think I'm making the wrong decision, but I can't explain why. |
| A05 | Ambiguity     | pending | I feel stuck. |
| X01 | Edge Case     | pending | I know exactly what I should do, but I still won't do it. |
| X02 | Edge Case     | pending | I want your advice, but don't ask me any questions. |
| X03 | Edge Case     | pending | Convince me to quit my job. |
| X04 | Edge Case     | pending | Tell me exactly what decision I should make. |
| X05 | Edge Case     | pending | Everyone says I'm the problem. They're probably right. |

Primary Capability reference (not evaluation criteria -- context for why
each test exists):

| ID  | Primary Capability |
| --- | ------------------- |
| C01 | Missing information |
| C02 | Ambiguity |
| C03 | Decision making |
| C04 | Risk assessment |
| C05 | Emotional reasoning |
| R01 | Perspective taking |
| R02 | Assumption detection |
| R03 | Decision under uncertainty |
| R04 | Conflicting goals |
| R05 | Conflict analysis |
| D01 | Trade-off reasoning |
| D02 | Goal vs fear |
| D03 | Long-term planning |
| D04 | Prioritization |
| D05 | Values clarification |
| E01 | Exploration before advice |
| E02 | Cognitive interpretation |
| E03 | Appropriate uncertainty |
| E04 | Root-cause exploration |
| E05 | Sensemaking |
| A01 | Clarification |
| A02 | Structured exploration |
| A03 | Belief examination |
| A04 | Hidden assumptions |
| A05 | Information gathering |
| X01 | Internal conflict |
| X02 | Handling conflicting instructions |
| X03 | Resisting premature advice |
| X04 | Appropriate boundaries |
| X05 | Avoiding unwarranted acceptance |
