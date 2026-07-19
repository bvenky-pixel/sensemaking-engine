<script>
  // Light affirm/correct affordance on POM's "You" section (2026-07-19,
  // backlog #209, see engine/decisions.md) -- one small reaction control
  // per rendered POM statement. Extracted as its own component because
  // PersonalOperatingModel.svelte mounts one of these per statement
  // across all eight sub-systems -- real, identical reuse, not a
  // premature abstraction for a single call site.
  //
  // Deliberately no read-back of prior feedback: this only ever POSTs,
  // never fetches, so a person can react again on a later visit without
  // this component needing to know what they said last time. "done" is
  // local, transient UI state for this one render, not a persisted
  // status -- confirmed with the founder as the "light" reading of this
  // affordance (see decisions.md for the alternative -- a persisted,
  // displayed-back status -- that was considered and not chosen).
  import { submitPomFeedback } from '../lib/api.js';

  let { system, statement } = $props();

  let mode = $state('idle'); // 'idle' | 'correcting' | 'done'
  let correctionText = $state('');
  let submitting = $state(false);
  let failed = $state(false);

  async function affirm() {
    submitting = true;
    failed = false;
    try {
      await submitPomFeedback(system, statement, 'affirm');
      mode = 'done';
    } catch {
      failed = true;
    } finally {
      submitting = false;
    }
  }

  function startCorrecting() {
    mode = 'correcting';
    failed = false;
  }

  function cancelCorrecting() {
    mode = 'idle';
    correctionText = '';
    failed = false;
  }

  async function submitCorrection() {
    submitting = true;
    failed = false;
    try {
      await submitPomFeedback(system, statement, 'correct', correctionText.trim() || null);
      mode = 'done';
    } catch {
      failed = true;
    } finally {
      submitting = false;
    }
  }
</script>

{#if mode === 'done'}
  <span class="pom-feedback-done voice">Noted, thanks.</span>
{:else if mode === 'correcting'}
  <div class="pom-feedback-correcting">
    <textarea
      class="pom-feedback-input"
      bind:value={correctionText}
      placeholder="Optional -- what's actually true?"
      rows="2"
      disabled={submitting}
    ></textarea>
    <div class="pom-feedback-actions">
      <button type="button" class="link-button" onclick={cancelCorrecting} disabled={submitting}>Cancel</button>
      <button type="button" class="link-button" onclick={submitCorrection} disabled={submitting}>
        {submitting ? 'Sending…' : 'Send'}
      </button>
    </div>
    {#if failed}<span class="pom-feedback-error">Couldn't send -- try again.</span>{/if}
  </div>
{:else}
  <div class="pom-feedback-row">
    <button type="button" class="link-button" onclick={affirm} disabled={submitting}>Sounds right</button>
    <button type="button" class="link-button" onclick={startCorrecting} disabled={submitting}>Not quite</button>
    {#if failed}<span class="pom-feedback-error">Couldn't send -- try again.</span>{/if}
  </div>
{/if}

<style>
  .pom-feedback-row {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-top: var(--space-1);
  }

  .pom-feedback-row .link-button {
    font-size: 12px;
  }

  .pom-feedback-done {
    display: block;
    color: var(--ink-muted);
    font-size: 12px;
    margin-top: var(--space-1);
  }

  .pom-feedback-correcting {
    margin-top: var(--space-1);
  }

  .pom-feedback-input {
    display: block;
    width: 100%;
    font-family: var(--font-ui);
    font-size: 13px;
    color: var(--ink);
    background: var(--paper-raised);
    border: none;
    border-radius: var(--radius-sm);
    padding: var(--space-1) var(--space-2);
    resize: vertical;
    box-sizing: border-box;
  }

  .pom-feedback-actions {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: var(--space-2);
    margin-top: var(--space-1);
  }

  .pom-feedback-actions .link-button {
    font-size: 12px;
  }

  .pom-feedback-error {
    color: var(--danger);
    font-size: 12px;
  }
</style>
