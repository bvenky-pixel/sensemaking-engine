<script>
  // Basic auth (2026-07-18, see frontend/decisions.md "Auth, the
  // low-friction way") -- the one login form in the whole app, shared
  // between Settings (gating the entire screen when signed out) and
  // Journey (gating further replies once the anonymous response limit
  // is hit), rather than two copies of the same email input. Magic
  // link only: no password field exists anywhere in this codebase,
  // matching the founder's own "as low friction as possible" brief.
  import { sendLoginLink } from '../lib/auth.svelte.js';

  let { message = 'Log in to continue.' } = $props();

  let email = $state('');
  let sending = $state(false);
  let sent = $state(false);
  let error = $state('');

  async function submit() {
    if (!email.trim()) return;
    sending = true;
    error = '';
    try {
      await sendLoginLink(email.trim());
      sent = true;
    } catch {
      error = "Couldn't send that link. Check the address and try again.";
    } finally {
      sending = false;
    }
  }
</script>

<div class="login-gate">
  {#if sent}
    <p class="voice">Check <strong>{email}</strong> for a login link. It'll bring you right back here.</p>
  {:else}
    <p class="voice gate-message">{message}</p>
    <form class="login-form" onsubmit={(event) => { event.preventDefault(); submit(); }}>
      <input
        type="email"
        bind:value={email}
        placeholder="you@example.com"
        autocomplete="email"
        required
      />
      <button type="submit" class="btn-primary" disabled={sending || !email.trim()}>
        {sending ? 'Sending…' : 'Send me a login link'}
      </button>
    </form>
    {#if error}
      <p class="voice error">{error}</p>
    {/if}
  {/if}
</div>

<style>
  .login-gate {
    text-align: left;
  }

  .gate-message {
    color: var(--ink-muted);
    margin: 0 0 var(--space-3);
  }

  .login-form {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
  }

  input[type='email'] {
    flex: 1;
    min-width: 200px;
    font-family: var(--font-ui);
    font-size: 16px;
    color: var(--ink);
    background: var(--paper-raised);
    border: 1px solid var(--line);
    border-radius: var(--radius-sm);
    padding: var(--space-2);
  }

  input[type='email']:focus {
    outline: 2px solid var(--accent);
    outline-offset: 1px;
  }

  .error {
    color: var(--danger);
    margin: var(--space-2) 0 0;
  }
</style>
