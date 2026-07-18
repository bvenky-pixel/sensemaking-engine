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
  //
  // Warm & Alive redesign (2026-07-18, see frontend/decisions.md): each
  // mode card gets a distinct soft accent tint, purely presentational
  // (never sent anywhere, never read from the backend) -- a fixed,
  // frontend-only color map keyed by mode id, so a mode this session
  // has never seen (or an id typo) safely falls back to the plain
  // --accent tint rather than breaking.
  import { onMount } from 'svelte';
  import { fly } from 'svelte/transition';
  import { getModes, createSession } from '../lib/api.js';

  let { onOpen, onBack } = $props();

  let modes = $state([]);
  let starting = $state(false);

  const MODE_TINTS = {
    vent: 'var(--accent-2)',
    strategize: 'var(--accent)',
    commit: 'var(--accent-5)',
    explore: 'var(--accent-4)',
    realign: 'var(--accent-3)',
    adaptive: 'var(--accent)',
  };

  function tintFor(modeId) {
    return MODE_TINTS[modeId] || 'var(--accent)';
  }

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
    {#each modes as mode, i (mode.id)}
      <li in:fly={{ y: 12, duration: 320, delay: Math.min(i * 50, 250) }}>
        <button
          type="button"
          class="mode-card card card-interactive"
          style="--mode-tint: {tintFor(mode.id)}"
          disabled={starting}
          onclick={() => choose(mode.id)}
        >
          <span class="mode-dot"></span>
          <span class="mode-text">
            <span class="mode-label">{mode.label}</span>
            <span class="voice mode-description">{mode.description}</span>
          </span>
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

  /* Shared .card/.card-interactive recipe, plus a per-mode tinted left
     edge -- the one place in this redesign color is used to distinguish
     categories, not just decorate. */
  .mode-card {
    display: flex;
    align-items: flex-start;
    gap: var(--space-2);
    width: 100%;
    text-align: left;
    padding: var(--space-3);
    border-left: 4px solid var(--mode-tint);
  }

  .mode-dot {
    flex-shrink: 0;
    width: 10px;
    height: 10px;
    margin-top: 6px;
    border-radius: 50%;
    background: var(--mode-tint);
  }

  .mode-text {
    display: block;
    flex: 1;
  }

  .mode-label {
    display: block;
    font-family: var(--font-display);
    font-weight: 700;
    font-size: 20px;
    color: var(--ink);
  }

  .mode-description {
    display: block;
    margin-top: var(--space-1);
  }
</style>
