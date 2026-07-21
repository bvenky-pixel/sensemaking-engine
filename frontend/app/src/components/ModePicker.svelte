<script>
  // Shared mode-card list -- originally extracted from a separate
  // screens/ModeSelect.svelte (2026-07-18, see frontend/decisions.md
  // "Home hero: orb + inline modes") once Home needed the identical
  // picker inline for journey-less accounts, not just ModeSelect's own
  // full screen. ModeSelect.svelte itself was later retired entirely
  // (2026-07-21, see engine/decisions.md "Tab order: You, Activity, +,
  // Plans, Settings") once its content and Home's became the same
  // destination -- this component is now only ever mounted from
  // Home.svelte. Fetches GET /modes itself (same "thin reflection of
  // backend truth" principle every other mode-facing screen already
  // follows) -- callers only provide `onChoose`; session creation and
  // navigation stay the caller's own concern.
  import { onMount } from 'svelte';
  import { fly } from 'svelte/transition';
  import { getModes } from '../lib/api.js';
  import { tintFor } from '../lib/modeTints.js';

  let { onChoose, starting = false } = $props();

  let modes = $state([]);

  onMount(async () => {
    modes = await getModes();
  });
</script>

<ul class="modes">
  {#each modes as mode, i (mode.id)}
    <li in:fly={{ y: 12, duration: 320, delay: Math.min(i * 50, 250) }}>
      <button
        type="button"
        class="mode-card card card-interactive"
        style="--mode-tint: {tintFor(mode.id)}"
        disabled={starting}
        onclick={() => onChoose(mode.id)}
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

<style>
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
