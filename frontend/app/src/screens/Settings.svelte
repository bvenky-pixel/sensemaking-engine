<script>
  // Kept deliberately small (information-architecture-v1.md): privacy
  // controls, account basics, data management -- nothing else belongs
  // here. Privacy/Account still have no backend endpoints -- those
  // stay structural placeholders until they exist.
  //
  // Data (added 2026-07-15, see engine/decisions.md "Frontend UX
  // pass"): the first of the three sections to get a real control --
  // removing a Journey. Two-step confirm inline (click "Remove" once to
  // ask, again to actually delete) rather than a native `confirm()`
  // dialog, matching this app's own calm, custom-styled aesthetic
  // rather than a browser chrome interruption. Irreversible, same as
  // the backend's own delete_session -- no undo exists yet.
  //
  // Warm & Alive redesign, organizing pass (2026-07-18, see
  // frontend/decisions.md): the three sections previously ran together
  // as loose, unbordered paragraphs -- "messy," per direct founder
  // feedback. Now each is its own card with a small color-coded marker
  // dot, same scannability device ModeSelect already established for
  // its six modes, so a person can tell the three sections apart at a
  // glance rather than reading every label.
  import { onMount } from 'svelte';
  import { fade } from 'svelte/transition';
  import { listSessions, deleteSession } from '../lib/api.js';

  let { onBack } = $props();

  let sessions = $state([]);
  let pendingDeleteId = $state(null);

  onMount(async () => {
    sessions = await listSessions();
  });

  function askToRemove(sessionId) {
    pendingDeleteId = sessionId;
  }

  function cancelRemove() {
    pendingDeleteId = null;
  }

  async function confirmRemove(sessionId) {
    await deleteSession(sessionId);
    sessions = sessions.filter((s) => s.id !== sessionId);
    pendingDeleteId = null;
  }
</script>

<div class="settings">
  <button type="button" class="back" onclick={onBack}>&larr; Home</button>

  <p class="display">Settings</p>

  <section class="card setting-section">
    <div class="setting-heading">
      <span class="dot" style="--dot-tint: var(--accent-2)"></span>
      <p class="ui-label">Privacy</p>
    </div>
    <p class="setting-body">Controls for what Confidant remembers and how it's used.</p>
  </section>

  <section class="card setting-section">
    <div class="setting-heading">
      <span class="dot" style="--dot-tint: var(--accent-3)"></span>
      <p class="ui-label">Account</p>
    </div>
    <p class="setting-body">Basic account details.</p>
  </section>

  <section class="card setting-section">
    <div class="setting-heading">
      <span class="dot" style="--dot-tint: var(--accent)"></span>
      <p class="ui-label">Data</p>
    </div>
    {#if sessions.length === 0}
      <p class="setting-body">Nothing shared here yet.</p>
    {:else}
      <ul class="journey-list">
        {#each sessions as session (session.id)}
          <li class="journey-row">
            <span class="preview">{session.preview_text || 'A new Journey'}</span>
            {#if pendingDeleteId === session.id}
              <span class="confirm">
                <span class="voice">Remove this Journey for good?</span>
                <button type="button" class="link-button danger" onclick={() => confirmRemove(session.id)}>
                  Yes, remove it
                </button>
                <button type="button" class="link-button" onclick={cancelRemove}>Cancel</button>
              </span>
            {:else}
              <button type="button" class="link-button" onclick={() => askToRemove(session.id)}>
                Remove
              </button>
            {/if}
          </li>
        {/each}
      </ul>
    {/if}
  </section>
</div>

<style>
  .back {
    display: block;
    margin-bottom: var(--space-3);
  }

  .display {
    margin: 0 0 var(--space-4);
  }

  .setting-section {
    padding: var(--space-3);
    margin-bottom: var(--space-2);
  }

  .setting-heading {
    display: flex;
    align-items: center;
    gap: var(--space-1);
  }

  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--dot-tint);
    flex-shrink: 0;
  }

  .setting-body {
    color: var(--ink-muted);
    margin: var(--space-1) 0 0;
  }

  .journey-list {
    list-style: none;
    margin: var(--space-2) 0 0;
    padding: 0;
  }

  .journey-row {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: var(--space-2);
    padding: var(--space-2) 0;
    border-bottom: 1px solid var(--line);
  }

  .journey-row:last-child {
    border-bottom: none;
  }

  .preview {
    font-family: var(--font-body);
    color: var(--ink);
  }

  .link-button {
    flex-shrink: 0;
    font-family: var(--font-ui);
    font-size: 14px;
    font-weight: 700;
    color: var(--ink-muted);
    background: none;
    border: none;
    cursor: pointer;
    padding: 0;
  }

  .confirm {
    display: flex;
    align-items: baseline;
    gap: var(--space-1);
    flex-shrink: 0;
  }

  .confirm .voice {
    color: var(--ink-muted);
    font-size: 14px;
  }

  /* Warm & Alive redesign (see frontend/decisions.md): a real --danger
     color now exists in the palette, so this uses it directly rather
     than v1's ink-weight-only signal. */
  .link-button.danger {
    color: var(--danger);
  }
</style>
