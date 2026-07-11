<script>
  import { onMount } from 'svelte';
  import { getMessages, sendMessage, getClarityBrief } from '../lib/api.js';
  import { honestFailureMessage } from '../lib/honestFailure.js';
  import { noteDeepeningClarity } from '../lib/deepeningClarity.js';
  import Transcript from '../components/Transcript.svelte';
  import Composer from '../components/Composer.svelte';
  import AmbientPresence from '../components/AmbientPresence.svelte';
  import Understanding from '../components/Understanding.svelte';

  let { sessionId, onBack } = $props();

  let messages = $state([]);
  let sending = $state(false);
  let brief = $state(null);
  let deepeningClarityNote = $state('');

  async function refreshBrief() {
    const previous = brief;
    const next = await getClarityBrief(sessionId);
    if (next) {
      deepeningClarityNote = noteDeepeningClarity(previous, next);
      brief = next;
    }
  }

  onMount(async () => {
    messages = await getMessages(sessionId);
    await refreshBrief();
  });

  async function handleSend(content) {
    messages = [...messages, { role: 'user', content, created_at: '' }];
    sending = true;
    try {
      const result = await sendMessage(sessionId, content);
      const text = result.response_text || honestFailureMessage(result.failed_stage);
      messages = [...messages, { role: 'assistant', content: text, created_at: '' }];
      if (result.response_text) {
        await refreshBrief();
      }
    } catch (err) {
      messages = [
        ...messages,
        { role: 'assistant', content: "I couldn't reach Confidant just now. Please try again in a moment.", created_at: '' },
      ];
    } finally {
      sending = false;
    }
  }
</script>

<div class="journey">
  <div class="scroll-fade" aria-hidden="true"></div>

  <button type="button" class="back" onclick={onBack}>&larr; Home</button>

  <Transcript {messages} />
  {#if sending}<AmbientPresence />{/if}
  <Composer disabled={sending} onSend={handleSend} />

  <Understanding {brief} {deepeningClarityNote} />
</div>

<style>
  .back {
    display: block;
    margin-bottom: var(--space-3);
  }

  /* Scroll-edge fade (Apple Journal form lesson, not function -- see
     frontend/decisions.md): content dissolves near the top of the
     viewport as the page scrolls, rather than hard-clipping. The whole
     app is one continuously scrolling flow (no fixed inner scroll
     panes), so this is a sticky, pointer-events-none overlay riding the
     viewport's top edge -- real content genuinely scrolls underneath
     it, not a static per-element mask. Matches --paper exactly so it's
     correct in both light and dark automatically, no separate values. */
  .scroll-fade {
    position: sticky;
    top: 0;
    height: var(--space-4);
    margin-bottom: calc(-1 * var(--space-4));
    background: linear-gradient(to bottom, var(--paper) 0%, transparent 100%);
    pointer-events: none;
    z-index: 1;
  }
</style>
