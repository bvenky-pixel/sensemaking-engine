<script>
  // No chat bubbles, no alternating background colors -- attribution
  // comes from typography alone (see frontend/specs/screen-design-v1.md):
  // the person's own words in the regular serif body voice; Confidant's
  // turns in the italic "section voice", reusing product-experience-v1's
  // already-validated pattern.
  let { messages } = $props();
</script>

<div class="transcript">
  {#each messages as message, i}
    <p class={message.role === 'assistant' ? 'voice' : ''}>{message.content}</p>
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
</style>
