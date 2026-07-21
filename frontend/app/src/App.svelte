<script>
  // Five spaces (information-architecture-v2.md, superseding v1's three
  // -- see engine/decisions.md "Frontend IA v2"): Home, Activity,
  // Journey, You, Settings, plus a center navigation action (starts a
  // new Journey) that isn't a sixth space. Local state, not a router
  // library -- still no deep-linking requirement (see
  // frontend/specs/screen-design-v1.md's own "out of scope" note),
  // just more screens than the original three.
  //
  // `tab` vs `screen` (2026-07-21, backlog #261): `tab` is which of the
  // four persistent destinations (home/activity/you/settings) is
  // "underneath" -- it only changes when TabBar's onNavigate fires, so
  // it stays exactly where it was while a Journey or ModeSelect is open
  // on top of it. `screen` is what's actually rendered right now
  // ('tab' meaning "show whichever screen `tab` names", or 'journey'/
  // 'mode-select' for the two full-screen overlays neither counted
  // among the five spaces). Backing out of either overlay is just
  // `screen = 'tab'` -- `tab` was never touched, so this naturally
  // restores wherever the person actually came from, without needing
  // its own bookkeeping.
  import { onMount } from 'svelte';
  import Home from './screens/Home.svelte';
  import Activity from './screens/Activity.svelte';
  import Journey from './screens/Journey.svelte';
  import ModeSelect from './screens/ModeSelect.svelte';
  import You from './screens/You.svelte';
  import Settings from './screens/Settings.svelte';
  import TabBar from './components/TabBar.svelte';
  import { checkAuth, consumeMagicLinkFromUrl } from './lib/auth.svelte.js';

  let tab = $state('home');
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

  function navigateTab(nextTab) {
    tab = nextTab;
    screen = 'tab';
  }

  // Tab bar's center action (backlog #264) -- starts a new Journey via
  // the existing Mentor mode-select flow, reachable from every tab.
  function beginNew() {
    screen = 'mode-select';
  }
</script>

<main>
  {#if screen === 'tab'}
    <div class="tab-content">
      {#if tab === 'home'}
        <Home onOpen={openJourney} />
      {:else if tab === 'activity'}
        <Activity onOpen={openJourney} />
      {:else if tab === 'you'}
        <You />
      {:else if tab === 'settings'}
        <Settings />
      {/if}
    </div>
    <TabBar active={tab} onNavigate={navigateTab} onBeginNew={beginNew} />
  {:else if screen === 'mode-select'}
    <ModeSelect onOpen={openJourney} onBack={backToTab} />
  {:else if screen === 'journey'}
    <Journey {sessionId} onBack={backToTab} />
  {/if}
</main>

<style>
  /* Mobile: TabBar.svelte's own bar is `position: fixed` to the bottom
     of the viewport at this same breakpoint -- extra bottom padding
     here keeps real tab content from sitting underneath it. Desktop:
     TabBar is a plain top row (`position: static`), so no extra
     padding is needed there. */
  @media (max-width: 639px) {
    .tab-content {
      padding-bottom: 72px;
    }
  }
</style>
