<script>
  // Five spaces (information-architecture-v2.md, superseding v1's three
  // -- see engine/decisions.md "Frontend IA v2"): originally Home,
  // Activity, Journey, You, Settings, plus a center navigation action.
  // Local state, not a router library -- still no deep-linking
  // requirement (see frontend/specs/screen-design-v1.md's own "out of
  // scope" note), just more screens than the original three.
  //
  // Tab order + Home retirement (2026-07-21, direct founder
  // instruction, see engine/decisions.md "Tab order: You, Activity, +,
  // Plans, Settings"): You, Activity, [+], Plans, Settings. Home is no
  // longer a tab -- its content (BreathingOrb hero + ModePicker,
  // Home.svelte, unchanged) is now what the center + action opens, AND
  // what's shown by default on first load, per the founder's own call
  // ("+ becomes the default and has the home screen"). This also
  // retires ModeSelect.svelte as a separate screen -- it was a
  // full-screen wrapper around the exact same ModePicker Home.svelte
  // already rendered inline, so once that content becomes a normal
  // named destination (`tab === 'start'`) rather than a modal reached
  // only via +, the separate overlay (and its own "back" affordance)
  // has nothing left to do that TabBar navigation doesn't already
  // cover.
  //
  // `tab` vs `screen`: `tab` is which of the five destinations
  // (start/activity/you/plans/settings) is "underneath" -- it only
  // changes when TabBar's onNavigate fires, so it stays exactly where
  // it was while a Journey is open on top of it. `screen` is what's
  // actually rendered right now ('tab' meaning "show whichever screen
  // `tab` names", or 'journey' for the one remaining full-screen
  // overlay). Backing out of a Journey is just `screen = 'tab'` --
  // `tab` was never touched, so this naturally restores wherever the
  // person actually came from, without needing its own bookkeeping.
  import { onMount } from 'svelte';
  import Home from './screens/Home.svelte';
  import Activity from './screens/Activity.svelte';
  import Journey from './screens/Journey.svelte';
  import You from './screens/You.svelte';
  import Plans from './screens/Plans.svelte';
  import Settings from './screens/Settings.svelte';
  import TabBar from './components/TabBar.svelte';
  import { checkAuth, consumeMagicLinkFromUrl } from './lib/auth.svelte.js';

  let tab = $state('start');
  let screen = $state('tab');
  let sessionId = $state(null);

  // Basic auth (2026-07-18, see frontend/decisions.md "Auth, the
  // low-friction way"): a clicked magic link lands back on this exact
  // page as `/?token=...` (there's no separate frontend route for it --
  // see src/api/server.py's /auth/request-link docstring for why the
  // link points at the plain root). If a token is present this
  // exchanges it for a real session cookie and strips it from the
  // address bar; either way, checkAuth() is skipped in that case since
  // consumeMagicLinkFromUrl already updated the same shared auth state
  // directly from its own response -- a second /auth/me round trip
  // right after would be redundant.
  //
  // Response-limit login UX gap fix (2026-07-18, see
  // frontend/decisions.md "Return to the same Journey after
  // magic-link verify"): when `returnSessionId` comes back set, open
  // that Journey directly instead of landing on Home -- the whole
  // point of threading it through was that "It'll bring you right
  // back here" (LoginGate's own copy) should actually be true.
  onMount(async () => {
    const consumed = await consumeMagicLinkFromUrl();
    if (!consumed) {
      await checkAuth();
    } else if (consumed.returnSessionId) {
      openJourney(consumed.returnSessionId);
    }
  });

  function openJourney(id) {
    sessionId = id;
    screen = 'journey';
  }

  function backToTab() {
    sessionId = null;
    screen = 'tab';
  }

  // Single navigation function for every TabBar button, center action
  // included -- the center "+" is just `onNavigate('start')` now that
  // its destination is a normal tab rather than a modal overlay (see
  // this file's own top docstring).
  function navigateTab(nextTab) {
    tab = nextTab;
    screen = 'tab';
  }
</script>

<main>
  {#if screen === 'tab'}
    <div class="tab-content">
      {#if tab === 'start'}
        <Home onOpen={openJourney} />
      {:else if tab === 'activity'}
        <Activity onOpen={openJourney} />
      {:else if tab === 'you'}
        <You />
      {:else if tab === 'plans'}
        <Plans />
      {:else if tab === 'settings'}
        <Settings />
      {/if}
    </div>
    <TabBar active={tab} onNavigate={navigateTab} />
  {:else if screen === 'journey'}
    <Journey {sessionId} onBack={backToTab} />
  {/if}
</main>

<style>
  /* Mobile: TabBar.svelte's own bar is `position: fixed` to the bottom
     of the viewport at this same breakpoint -- extra bottom padding
     here keeps real tab content from sitting underneath it. Desktop:
     TabBar is a plain top row (`position: static`), so no extra
     padding is needed there.

     88px, not just the bar's own ~72px height (2026-07-21, found while
     verifying the compact mode picker -- see engine/decisions.md
     "Compact mode picker"): TabBar.svelte's own `bottom: var(--space-2)`
     (16px) lifts it off the true viewport edge, so its full footprint
     from the bottom is 72 + 16 = 88px, not 72 alone. The 16px shortfall
     was invisible before now because content never reached this
     boundary closely enough to matter -- packing six mode cards tight
     enough to fit on a small phone's screen was what finally exposed
     it (the last card rendered partly underneath the fixed bar). */
  @media (max-width: 639px) {
    .tab-content {
      padding-bottom: calc(72px + var(--space-2));
    }
  }
</style>
