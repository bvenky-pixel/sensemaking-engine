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

---
