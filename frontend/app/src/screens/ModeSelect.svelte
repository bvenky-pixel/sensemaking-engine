<script>
  // Counseling modes (2026-07-15, see engine/decisions.md "Counseling
  // modes") -- reached via the tab bar's center action (backlog #264,
  // see information-architecture-v2.md), not from Home anymore: Home
  // now always shows ModePicker inline (see Home.svelte's own
  // docstring, backlog #265), so this full-screen version only ever
  // gets used from Activity/You/Settings (or redundantly from Home
  // itself, tapping the same center action). Card rendering itself
  // lives in components/ModePicker.svelte, shared with Home's inline
  // case, so both stay visually identical with no duplicated markup.
  // `onBack` returns to whichever tab was active before the center
  // action was tapped (App.svelte's own concern, not this screen's) --
  // the back label below is deliberately generic ("Back", not "Home")
  // since that destination varies.
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
  <button type="button" class="back" onclick={onBack}>&larr; Back</button>

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
