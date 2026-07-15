<script>
  // Three sanctioned spaces (information-architecture-v1.md): Home,
  // Journey, Settings. Local state, not a router library -- three
  // screens with no deep-linking requirement don't need one yet (see
  // frontend/specs/screen-design-v1.md's own "out of scope" note).
  import Home from './screens/Home.svelte';
  import Journey from './screens/Journey.svelte';
  import ModeSelect from './screens/ModeSelect.svelte';
  import Settings from './screens/Settings.svelte';

  let screen = $state('home');
  let sessionId = $state(null);

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
