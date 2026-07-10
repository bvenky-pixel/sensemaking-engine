<script>
  // Three sanctioned spaces (information-architecture-v1.md): Home,
  // Journey, Settings. Local state, not a router library -- three
  // screens with no deep-linking requirement don't need one yet (see
  // frontend/specs/screen-design-v1.md's own "out of scope" note).
  import Home from './screens/Home.svelte';
  import Journey from './screens/Journey.svelte';
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
</script>

<main>
  {#if screen === 'home'}
    <Home onOpen={openJourney} onSettings={openSettings} />
  {:else if screen === 'journey'}
    <Journey {sessionId} onBack={goHome} />
  {:else if screen === 'settings'}
    <Settings onBack={goHome} />
  {/if}
</main>
