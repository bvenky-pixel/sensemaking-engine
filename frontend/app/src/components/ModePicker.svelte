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

  /* Compact mode picker (2026-07-21, direct founder instruction, see
     Home.svelte's own docstring and engine/decisions.md "Compact mode
     picker"): all six cards used to run to roughly 780px total (24px
     padding on all four sides, a 20px label, and descriptions that
     often wrapped two lines) -- taller than most phone viewports on
     their own, before the header above them. Tighter padding/margins/
     font size here, plus clamping the description to one line (below),
     bring six cards down to something that fits alongside a compact
     header without scrolling on standard phone heights. */
  .modes li {
    margin-bottom: 6px;
  }

  /* Shared .card/.card-interactive recipe, plus a per-mode tinted left
     edge -- the one place in this redesign color is used to distinguish
     categories, not just decorate. */
  .mode-card {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    width: 100%;
    text-align: left;
    padding: 8px var(--space-2);
    border-left: 4px solid var(--mode-tint);
  }

  .mode-dot {
    flex-shrink: 0;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--mode-tint);
  }

  .mode-text {
    display: block;
    flex: 1;
    min-width: 0;
  }

  .mode-label {
    display: block;
    font-family: var(--font-display);
    font-weight: 700;
    font-size: 16px;
    color: var(--ink);
  }

  /* Clamped to one line (with an ellipsis for anything longer) rather
     than left free to wrap -- a card's height needs to be predictable
     and small regardless of how long any given mode's description
     text happens to be, not just usually small. */
  .mode-description {
    display: -webkit-box;
    -webkit-line-clamp: 1;
    -webkit-box-orient: vertical;
    overflow: hidden;
    font-size: 13px;
    font-style: italic;
    color: var(--ink-muted);
  }
</style>
