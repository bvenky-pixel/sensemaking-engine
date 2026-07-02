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
