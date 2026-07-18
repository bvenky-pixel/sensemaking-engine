<script>
  // "Handing the page over" (v4's most protected interaction): writing
  // and indicating readiness to be heard are two separate, deliberately
  // distinct actions. Bare Enter is never wired to submit -- a textarea
  // already inserts a newline on Enter by default, so simply not adding
  // a submit-on-Enter handler is the correct, complete implementation
  // of that rule, not an oversight to fix later.
  let { disabled, onSend } = $props();
  let content = $state('');

  async function share() {
    const text = content.trim();
    if (!text) return;
    content = '';
    await onSend(text);
  }
</script>

<div class="composer">
  <textarea
    bind:value={content}
    disabled={disabled}
    placeholder="What's on your mind?"
    rows="3"
  ></textarea>
  <div class="actions">
    <button type="button" class="btn-primary share" disabled={disabled || !content.trim()} onclick={share}>
      Share this
    </button>
  </div>
</div>

<style>
  .composer {
    margin-top: var(--space-4);
  }

  .actions {
    display: flex;
    justify-content: flex-end;
    margin-top: var(--space-2);
  }

  /* Real visual weight for "handing the page over" -- v4's most
     protected interaction deserves more presence than a plain text
     link the same weight as "Settings". Warm & Alive redesign (see
     frontend/decisions.md): now the shared .btn-primary pill recipe,
     explicit reversal of v1's anti-pill-button stance. */
  .share {
    padding: var(--space-2) var(--space-4);
  }
</style>
