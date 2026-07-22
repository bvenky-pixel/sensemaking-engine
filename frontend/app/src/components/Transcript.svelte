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

  // Only the last exchange visible by default, older turns reachable
  // (2026-07-21, backlog #237, see engine/decisions.md and
  // engine/specs/latency-northstar-v1.md's own "needs a real
  // interaction-design decision" flag) -- a collapse/expand affordance,
  // deliberately NOT a fixed-height scrollable pane: the app has no
  // nested scroll regions anywhere else (see Journey.svelte's own
  // .scroll-fade comment, "the whole app is one continuously scrolling
  // flow"), and this keeps that principle intact rather than
  // introducing a new one just for this screen.
  //
  // "Last exchange" = the most recent user message and everything from
  // that point on (normally just its one assistant reply, but also
  // correctly covers the mid-flight case where a user message has been
  // sent and nothing has answered it yet). Recomputed from `messages`
  // on every render, not frozen at mount, so a freshly-sent turn is
  // always what's shown without the person having to manually
  // re-collapse anything. `showEarlier` stays a simple, un-persisted
  // $state -- defaults closed on every fresh open of a Journey, and
  // once a person opens it within one visit it stays open rather than
  // silently re-collapsing under them as further turns arrive.
  let showEarlier = $state(false);

  let lastExchangeStart = $derived.by(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'user') return i;
    }
    return 0;
  });
  let earlierMessages = $derived(messages.slice(0, lastExchangeStart));
  let lastExchangeMessages = $derived(messages.slice(lastExchangeStart));
</script>

{#snippet messageRow(message, showOptions)}
  <p class={message.role === 'assistant' ? 'voice' : ''} in:fly={{ y: 8, duration: 280 }}>{message.content}</p>
  {#if message.role === 'assistant' && message.options?.length && showOptions}
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
{/snippet}

<div class="transcript">
  {#if earlierMessages.length > 0}
    {#if showEarlier}
      {#each earlierMessages as message, i (i)}
        {@render messageRow(message, false)}
        <hr />
      {/each}
    {:else}
      <button type="button" class="link-button show-earlier" onclick={() => (showEarlier = true)}>
        Show earlier in this Journey
      </button>
    {/if}
  {/if}
  {#each lastExchangeMessages as message, i (i)}
    {@render messageRow(message, i === lastExchangeMessages.length - 1)}
    {#if i < lastExchangeMessages.length - 1}<hr />{/if}
  {/each}
</div>

<style>
  .transcript p {
    margin: 0 0 var(--space-2);
  }

  .transcript hr {
    margin: var(--space-3) 0;
  }

  /* Last-exchange-only collapse affordance (see script comment) --
     deliberately quiet, matching every other "reveal more" tap target
     in this codebase (Journey.svelte's own menu trigger): plain
     .link-button styling, no card or border, sits above the hidden
     history rather than calling attention to itself. */
  .show-earlier {
    display: block;
    margin: 0 0 var(--space-3);
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
