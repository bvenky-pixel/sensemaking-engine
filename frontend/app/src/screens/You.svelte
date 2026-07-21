<script>
  // You tab (2026-07-21, backlog #263, see information-architecture-v2.md,
  // engine/decisions.md "Frontend IA v2") -- PersonalOperatingModel.svelte
  // and BehavioralPatterns.svelte, promoted out of Settings into their
  // own top-level space rather than a section a person has to remember
  // exists inside configuration. Both components are already fully
  // self-contained (fetch their own data, render their own card) --
  // this screen only supplies the auth gate and heading, same "thin
  // wrapper" shape Settings.svelte's own former mounting of them had.
  import { authState } from '../lib/auth.svelte.js';
  import LoginGate from '../components/LoginGate.svelte';
  import PersonalOperatingModel from '../components/PersonalOperatingModel.svelte';
  import BehavioralPatterns from '../components/BehavioralPatterns.svelte';
</script>

<div class="you">
  <p class="display">You</p>

  {#if !authState.checked}
    <!-- Waiting on App.svelte's own boot-time auth check -- see
         Settings.svelte's identical comment. -->
  {:else if !authState.authenticated}
    <section class="card setting-section">
      <LoginGate message="Log in to see what Confidant has noticed about you." />
    </section>
  {:else}
    <PersonalOperatingModel />
    <BehavioralPatterns />
  {/if}
</div>

<style>
  .display {
    margin: 0 0 var(--space-4);
  }

  .setting-section {
    padding: var(--space-3);
    margin-bottom: var(--space-2);
  }
</style>
