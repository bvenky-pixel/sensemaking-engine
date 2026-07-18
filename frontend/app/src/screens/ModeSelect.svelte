<script>
  // Counseling modes (2026-07-15, see engine/decisions.md "Counseling
  // modes") -- this screen is the fallback, full-screen entry point
  // once Home's own inline picker has collapsed back to a single
  // "+Begin something new" button (see frontend/decisions.md "Home
  // hero: orb + inline modes" -- Home shows the picker inline only
  // while a person has no Journeys yet). Card rendering itself now
  // lives in components/ModePicker.svelte, shared with Home's inline
  // case, so both stay visually identical with no duplicated markup.
  import { createSession } from '../lib/api.js';
  import ModePicker from '../components/ModePicker.svelte';

  let { onOpen, onBack } = $props();

  let starting = $state(false);

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

  <ModePicker onChoose={choose} {starting} />
</div>

<style>
  .back {
    display: block;
    margin-bottom: var(--space-3);
  }

  .display {
    margin: 0 0 var(--space-4);
  }
</style>
