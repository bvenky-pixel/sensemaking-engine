<script>
  // Counseling modes (2026-07-15, see engine/decisions.md "Counseling
  // modes"): five frontend-selectable entry points, one chosen per
  // Journey at creation time, each biasing Planner/Response toward one
  // of the five coaching perspectives named in the founder's vision doc
  // -- but presented here as plain, emotive action verbs (Vent,
  // Strategize, ...), never the vision doc's internal coaching jargon.
  // Labels/descriptions are fetched from GET /modes, never hardcoded --
  // this screen is a thin reflection of that endpoint, same principle
  // as every other frontend/api.js call.
  import { onMount } from 'svelte';
  import { getModes, createSession } from '../lib/api.js';

  let { onOpen, onBack } = $props();

  let modes = $state([]);
  let starting = $state(false);

  onMount(async () => {
    modes = await getModes();
  });

  async function choose(modeId) {
    starting = true;
    try {
      const { id } = await createSession(modeId);
      onOpen(id);
    } finally {
      starting = false;
    }
  }
</script>

<div class="mode-select">
  <button type="button" class="back" onclick={onBack}>&larr; Home</button>

  <p class="display">How do you want to start?</p>

  <ul class="modes">
    {#each modes as mode (mode.id)}
      <li>
        <button
          type="button"
          class="mode-card"
          disabled={starting}
          onclick={() => choose(mode.id)}
        >
          <span class="mode-label">{mode.label}</span>
          <span class="voice mode-description">{mode.description}</span>
        </button>
      </li>
    {/each}
  </ul>
</div>

<style>
  .back {
    display: block;
    margin-bottom: var(--space-3);
  }

  .display {
    margin: 0 0 var(--space-4);
  }

  .modes {
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .modes li {
    margin-bottom: var(--space-2);
  }

  /* Same "settled card" recipe as Home.svelte's own .journey-card --
     kept as a local, scoped duplicate rather than a shared class, same
     "no premature abstraction yet" reasoning already documented there. */
  .mode-card {
    display: block;
    width: 100%;
    text-align: left;
    background: var(--paper-raised);
    border-radius: var(--radius);
    box-shadow: 0 1px 0 var(--line);
    padding: var(--space-2) var(--space-3);
  }

  .mode-label {
    display: block;
    font-family: var(--serif);
    font-size: 19px;
    color: var(--ink);
  }

  .mode-description {
    display: block;
    margin-top: var(--space-1);
  }
</style>
