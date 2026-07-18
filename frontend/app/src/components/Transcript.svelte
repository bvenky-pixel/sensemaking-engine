<script>
  // No chat bubbles, no alternating background colors -- attribution
  // comes from typography alone (see frontend/specs/screen-design-v1.md):
  // the person's own words in the regular serif body voice; Confidant's
  // turns in the italic "section voice", reusing product-experience-v1's
  // already-validated pattern.
  //
  // Response v3 -- real choice buttons (2026-07-15, see
  // engine/decisions.md): `onOptionSelect` fires with the tapped
  // option's own label (never its description -- see below), exactly as
  // if the person had typed and sent it themselves -- these are a
  // shortcut into Composer's existing send path, not a separate
  // mechanism. Only the LAST message ever renders its buttons: an
  // assistant message's options answer THAT turn's question
  // specifically, so once the conversation has moved past it (a further
  // message exists), tapping an option from an earlier turn no longer
  // means anything -- disabled is left true while a turn is already in
  // flight, matching Composer's own disabled state.
  //
  // Each option is now {label, description} (added same round, direct
  // user request for "reasoning behind each choice") -- label is the
  // clickable reply text; description is 1-2 sentences of display-only
  // support shown under it, never sent anywhere itself. That's enough
  // text per option that a wrapping row of chips (the original design)
  // no longer fits -- stacked one per line instead.
  import { fade, fly } from 'svelte/transition';

  let { messages, onOptionSelect, disabled } = $props();
</script>

<div class="transcript">
  {#each messages as message, i (i)}
    <p class={message.role === 'assistant' ? 'voice' : ''} in:fly={{ y: 8, duration: 280 }}>{message.content}</p>
    {#if message.role === 'assistant' && message.options?.length && i === messages.length - 1}
      <div class="options" role="group" aria-label="Quick replies" in:fade={{ duration: 280, delay: 100 }}>
        {#each message.options as option}
          <button
            type="button"
            class="option"
            disabled={disabled}
            onclick={() => onOptionSelect(option.label)}
          >
            <span class="option-label">{option.label}</span>
            <span class="option-description">{option.description}</span>
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
    flex-direction: column;
    gap: var(--space-1);
    margin: 0 0 var(--space-3);
  }

  /* A scaffold, not a form control -- these still just feed Composer's
     existing free-text send path (see script comment above), so they
     read as a lighter-weight shortcut rather than the one heavyweight
     "Share this" call to action. Warm & Alive redesign: rounded,
     softly-shadowed chip with a real hover lift instead of an instant
     border-color snap. */
  .option {
    display: block;
    width: 100%;
    text-align: left;
    font-family: var(--font-ui);
    color: var(--ink);
    background: var(--paper-raised);
    border: 2px solid var(--line);
    border-radius: var(--radius-sm);
    padding: var(--space-2);
    box-shadow: var(--shadow-soft);
    transition: border-color var(--motion-smooth), transform var(--motion-smooth), box-shadow var(--motion-smooth);
  }

  .option:hover:not(:disabled) {
    border-color: var(--accent);
    transform: translateY(-1px);
    box-shadow: var(--shadow-lifted);
  }

  .option-label {
    display: block;
    font-size: 14px;
    font-weight: 700;
  }

  .option-description {
    display: block;
    font-size: 13px;
    color: var(--ink-muted);
    font-weight: 400;
    margin-top: var(--space-1);
  }
</style>
