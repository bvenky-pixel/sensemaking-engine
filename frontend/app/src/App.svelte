<script>
  // Three sanctioned spaces (information-architecture-v1.md): Home,
  // Journey, Settings. Local state, not a router library -- three
  // screens with no deep-linking requirement don't need one yet (see
  // frontend/specs/screen-design-v1.md's own "out of scope" note).
  import { onMount } from 'svelte';
  import Home from './screens/Home.svelte';
  import Journey from './screens/Journey.svelte';
  import ModeSelect from './screens/ModeSelect.svelte';
  import Settings from './screens/Settings.svelte';
  import { checkAuth, consumeMagicLinkFromUrl } from './lib/auth.svelte.js';

  let screen = $state('home');
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

  function goHome() {
    screen = 'home';
    sessionId = null;
  }

  function openSettings() {
    screen = 'settings';
  }

  // Counseling modes (see engine/decisions.md): "+ Begin something new"
  // on Home no longer creates a session directly -- it goes through a
  // mode-select step first, which creates the session itself (with the
  // chosen mode) and hands back here via the same onOpen callback Home
  // already uses.
  function beginNew() {
    screen = 'mode-select';
  }
</script>

<main>
  {#if screen === 'home'}
    <Home onOpen={openJourney} onSettings={openSettings} onBeginNew={beginNew} />
  {:else if screen === 'mode-select'}
    <ModeSelect onOpen={openJourney} onBack={goHome} />
  {:else if screen === 'journey'}
    <Journey {sessionId} onBack={goHome} />
  {:else if screen === 'settings'}
    <Settings onBack={goHome} />
  {/if}
</main>
