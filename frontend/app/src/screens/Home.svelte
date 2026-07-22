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
  //
  // All six modes visible with no scrolling, on mobile (2026-07-21,
  // direct founder instruction, see engine/decisions.md "Compact mode
  // picker"): the previous full-size hero (108px orb + enso, a ZenQuote
  // that can run to 2-3 lines depending which quote gets picked, a
  // redundant "Pick what fits right now" line, plus six full-padding
  // cards) added up to roughly 780px of cards alone before the header --
  // taller than most phone viewports. Founder's own choice, from three
  // options offered, was "compact list, tighter everything" over a
  // grid layout or dropping descriptions -- BreathingOrb's own
  // `compact` prop (already existed for Journey's idle-orb use) shrinks
  // it to 72px with no enso ring; the redundant intro line is gone
  // entirely (the cards are self-explanatory); title and quote margins
  // are tightened; ModePicker.svelte's own cards got the matching
  // compaction (see that file's own docstring). Still not a hard
  // guarantee on the smallest phones (iPhone SE-class, ~667px tall) --
  // see that same decisions.md entry for the honest caveat.
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
    <BreathingOrb compact />
    <ZenQuote />
    <ModePicker onChoose={chooseMode} {starting} />
  </div>
</div>

<style>
  .display {
    font-size: 22px;
    margin: 0 0 var(--space-2);
  }

  .hero {
    text-align: center;
  }

  /* BreathingOrb's own `compact` variant zeroes its own margin entirely
     (see that component's docstring), including the horizontal `auto`
     the base (non-compact) rule relies on to center a fixed-width block
     box -- `.hero`'s own `text-align: center` above only centers inline
     content, never a block box, so without this the orb sits flush left
     inside `body`'s own centered 60ch column. Invisible on mobile (that
     column fills the whole viewport there, so there's no room to the
     side for the misalignment to show); visible on desktop, where the
     column is narrower than the viewport (2026-07-22, direct founder
     report: "the orb is left aligned in the + screen for desktop").
     `margin: 0 auto` restores horizontal centering while keeping the
     smaller bottom gap this rule already wanted. */
  .hero :global(.hero-orb) {
    margin: 0 auto var(--space-1);
  }

  /* The mode cards themselves stay left-aligned (label/description read
     better that way) even though the orb + quote above them are
     centered. */
  .hero :global(.modes) {
    text-align: left;
  }
</style>
