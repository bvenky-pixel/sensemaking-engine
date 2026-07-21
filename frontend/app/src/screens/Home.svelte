<script>
  // Home, narrowed (2026-07-21, backlog #265, see
  // information-architecture-v2.md, engine/decisions.md "Frontend IA
  // v2"): with Activity now owning the journey list, filters,
  // bookmarking, and the post-Journey completion nudge (backlog #262),
  // Home goes back to being purely the entry/welcome moment IA v2 calls
  // for -- the BreathingOrb hero, a fresh ZenQuote, and the mode picker,
  // ALWAYS shown, not conditional on whether any Journeys exist yet.
  // The old conditional collapse (a big hero only when sessions.length
  // === 0, a compact orb + list otherwise) existed specifically to make
  // room for the journey list on the same screen -- with that list
  // gone, there's nothing left to make room for, so the full hero is
  // simply always here.
  //
  // The former bottom "Settings"/"Log in" links are gone too -- Settings
  // is now a persistent tab bar destination reachable from every
  // screen (backlog #261), so a dedicated text link to it here would
  // just be the same affordance twice. Signing in still matters, but
  // that's Settings' own gate to prompt, not Home's -- Home's job is
  // now singular: get a person into a Journey.
  //
  // No longer a labeled tab (2026-07-21, direct founder instruction,
  // see engine/decisions.md "Tab order: You, Activity, +, Plans,
  // Settings"): this exact component is now what the tab bar's center
  // + action opens, and also what App.svelte shows by default on first
  // load (`tab = $state('start')`) -- nothing in this file changed for
  // that, since it was already the closest thing this app had to a
  // "start something new" screen; only which App.svelte state value
  // mounts it changed.
  import { fade } from 'svelte/transition';
  import { createSession } from '../lib/api.js';
  import BreathingOrb from '../components/BreathingOrb.svelte';
  import ZenQuote from '../components/ZenQuote.svelte';
  import ModePicker from '../components/ModePicker.svelte';

  let { onOpen } = $props();

  let starting = $state(false);

  async function chooseMode(modeId) {
    starting = true;
    try {
      const { id } = await createSession(modeId);
      onOpen(id);
    } finally {
      starting = false;
    }
  }
</script>

<div class="home">
  <p class="display">A quiet place to think something through.</p>

  <div class="hero" in:fade={{ duration: 320 }}>
    <BreathingOrb />
    <ZenQuote />
    <p class="voice hero-copy">Pick what fits right now.</p>
    <ModePicker onChoose={chooseMode} {starting} />
  </div>
</div>

<style>
  .display {
    margin: 0 0 var(--space-4);
  }

  .hero {
    text-align: center;
  }

  .hero-copy {
    color: var(--ink-muted);
    margin: 0 0 var(--space-3);
  }

  /* The mode cards themselves stay left-aligned (label/description read
     better that way) even though the orb + intro line above them are
     centered. */
  .hero :global(.modes) {
    text-align: left;
  }
</style>
