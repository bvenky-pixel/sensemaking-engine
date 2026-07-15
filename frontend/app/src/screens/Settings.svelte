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
  import { onMount } from 'svelte';
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

  <section>
    <p class="ui-label">Privacy</p>
    <p>Controls for what Confidant remembers and how it's used.</p>
  </section>

  <section>
    <p class="ui-label">Account</p>
    <p>Basic account details.</p>
  </section>

  <section>
    <p class="ui-label">Data</p>
    {#if sessions.length === 0}
      <p>Nothing shared here yet.</p>
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

  section {
    margin-bottom: var(--space-3);
  }

  section p:last-child {
    color: var(--ink-muted);
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
    padding: var(--space-1) 0;
    border-bottom: 1px solid var(--line);
  }

  .journey-row:last-child {
    border-bottom: none;
  }

  .preview {
    font-family: var(--serif);
  }

  .link-button {
    flex-shrink: 0;
    font-family: var(--sans);
    font-size: 14px;
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

  /* No dedicated "danger" color exists in this app's calm, muted
     palette (see frontend/app/src/lib/tokens.css) -- full-contrast ink
     rather than an invented red is enough to mark this as the
     serious, irreversible action among the two choices. */
  .link-button.danger {
    color: var(--ink);
    font-weight: 600;
  }
</style>
