<script>
  // Not a dashboard: no counts, no metrics, no activity feed (see
  // information-architecture-v1.md's "Three Spaces" section). A calm
  // list of Journeys and one unforced way to begin a new one.
  import { onMount } from 'svelte';
  import { listSessions, createSession } from '../lib/api.js';

  let { onOpen, onSettings } = $props();

  let sessions = $state([]);
  let starting = $state(false);

  onMount(async () => {
    sessions = await listSessions();
  });

  async function startNew() {
    starting = true;
    try {
      const { id } = await createSession();
      onOpen(id);
    } finally {
      starting = false;
    }
  }
</script>

<div class="home">
  {#if sessions.length === 0}
    <p class="voice">A quiet place to think something through.</p>
  {:else}
    <ul class="journeys">
      {#each sessions as session}
        <li>
          <button type="button" class="journey-row" onclick={() => onOpen(session.id)}>
            {session.surface_complaint || 'A new Journey'}
          </button>
        </li>
      {/each}
    </ul>
  {/if}

  <button type="button" class="start" disabled={starting} onclick={startNew}>
    + Begin something new
  </button>

  <button type="button" class="ui-label settings-link" onclick={onSettings}>Settings</button>
</div>

<style>
  .journeys {
    list-style: none;
    margin: 0 0 var(--space-4);
    padding: 0;
  }

  .journeys li {
    border-bottom: 1px solid var(--line);
  }

  .journey-row {
    display: block;
    width: 100%;
    text-align: left;
    color: var(--ink);
    font-family: var(--serif);
    font-size: 17px;
    padding: var(--space-2) 0;
  }

  .start {
    margin-top: var(--space-3);
  }

  .settings-link {
    display: block;
    margin-top: var(--space-5);
  }
</style>
