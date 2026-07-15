<script>
  // No chat bubbles, no alternating background colors -- attribution
  // comes from typography alone (see frontend/specs/screen-design-v1.md):
  // the person's own words in the regular serif body voice; Confidant's
  // turns in the italic "section voice", reusing product-experience-v1's
  // already-validated pattern.
  //
  // Response v3 -- real choice buttons (2026-07-15, see
  // engine/decisions.md): `onOptionSelect` fires with the tapped
  // option's own label, exactly as if the person had typed and sent it
  // themselves -- these are a shortcut into Composer's existing send
  // path, not a separate mechanism. Only the LAST message ever renders
  // its buttons: an assistant message's options answer THAT turn's
  // question specifically, so once the conversation has moved past it
  // (a further message exists), tapping an option from an earlier turn
  // no longer means anything -- disabled is left true while a turn is
  // already in flight, matching Composer's own disabled state.
  let { messages, onOptionSelect, disabled } = $props();
</script>

<div class="transcript">
  {#each messages as message, i}
    <p class={message.role === 'assistant' ? 'voice' : ''}>{message.content}</p>
    {#if message.role === 'assistant' && message.options?.length && i === messages.length - 1}
      <div class="options" role="group" aria-label="Quick replies">
        {#each message.options as option}
          <button
            type="button"
            class="option"
            disabled={disabled}
            onclick={() => onOptionSelect(option)}
          >
            {option}
          </button>
        {/each}
      </div>
    {/if}
    {#if i < messages.length - 1}<hr />{/if}
  {/each}
</div>

<style>
  .transcript p {
    margin: 0 0 var(--space-2);
  }

  .transcript hr {
    margin: var(--space-3) 0;
  }

  .options {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
    margin: 0 0 var(--space-2);
  }

  /* A scaffold, not a form control -- these still just feed Composer's
     existing free-text send path (see script comment above), so they
     read as a lighter-weight shortcut rather than the one heavyweight
     "Share this" call to action. */
  .option {
    font-family: var(--sans);
    font-size: 14px;
    color: var(--ink);
    background: var(--paper-raised);
    border: 1px solid var(--line);
    border-radius: var(--radius);
    padding: var(--space-1) var(--space-2);
  }

  .option:hover:not(:disabled) {
    border-color: var(--accent);
  }
</style>
