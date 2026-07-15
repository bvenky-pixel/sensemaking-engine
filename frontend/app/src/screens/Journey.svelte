<script>
  import { onMount } from 'svelte';
  import { getMessages, sendMessage, getClarityBrief, getUnderstanding, openStageStream } from '../lib/api.js';
  import { honestFailureMessage } from '../lib/honestFailure.js';
  import { noteDeepeningClarity } from '../lib/deepeningClarity.js';
  import Transcript from '../components/Transcript.svelte';
  import Composer from '../components/Composer.svelte';
  import AmbientPresence from '../components/AmbientPresence.svelte';
  import Understanding from '../components/Understanding.svelte';

  // Major update (2026-07-11, see engine/decisions.md): a visible opening
  // prompt for a brand-new Journey, distinct from Composer's own
  // placeholder (which vanishes on focus and many people never read).
  // One is chosen at component creation, not re-randomized on re-render,
  // so it doesn't change mid-conversation once it's stopped being shown.
  const OPENING_PROMPTS = [
    "What's keeping you up at night?",
    "What's been sitting with you lately?",
    "What's on your mind that you haven't said out loud yet?",
    "What's been on repeat in your head this week?",
    "What feels unresolved right now?",
  ];
  const openingPrompt = OPENING_PROMPTS[Math.floor(Math.random() * OPENING_PROMPTS.length)];

  let { sessionId, onBack } = $props();

  let messages = $state([]);
  let loaded = $state(false);
  let sending = $state(false);
  let brief = $state(null);
  let tier2 = $state([]);
  let deepeningClarityNote = $state('');
  // Incremented once per real backend stage-completion event during a
  // turn (see AmbientPresence.svelte, engine/decisions.md "Major
  // update" Part 5) -- a plain counter, not the stage names themselves,
  // is all the presentational component needs.
  let pulseCount = $state(0);

  async function refreshBrief() {
    const previous = brief;
    const next = await getClarityBrief(sessionId);
    if (next) {
      deepeningClarityNote = noteDeepeningClarity(previous, next);
      brief = next;
    }
  }

  // GET /understanding never 404s (unlike Clarity Brief above) -- Tier 1
  // computes unconditionally every turn, but this component only renders
  // tier2 (see Understanding.svelte's own docstring for why tier1 isn't
  // surfaced here yet), which is often still empty (computed only
  // conditionally -- see src/understanding/tier2_engine.py).
  async function refreshUnderstanding() {
    const next = await getUnderstanding(sessionId);
    tier2 = next?.tier2 ?? [];
  }

  onMount(async () => {
    messages = await getMessages(sessionId);
    loaded = true;
    await refreshBrief();
    await refreshUnderstanding();
  });

  async function handleSend(content) {
    messages = [...messages, { role: 'user', content, created_at: '' }];
    sending = true;
    // Opened synchronously, in the same call as the POST below -- see
    // AmbientPresence.svelte's own docstring for why this can't live
    // inside that component (Svelte's re-render happens on a later
    // microtask than this function's own next line, which would risk
    // missing the "interpretation" stage's event on every turn).
    const closeStream = openStageStream(sessionId, () => {
      pulseCount += 1;
    });
    try {
      const result = await sendMessage(sessionId, content);
      const text = result.response_text || honestFailureMessage(result.failed_stage);
      messages = [...messages, { role: 'assistant', content: text, created_at: '' }];
      if (result.response_text) {
        await refreshBrief();
      }
      // Unlike refreshBrief above, not gated behind response_text --
      // Tier 2 (src/understanding/tier2_engine.py) runs before Planner/
      // Response in the pipeline, so it can have updated even on a turn
      // where Response Generator itself failed.
      await refreshUnderstanding();
    } catch (err) {
      messages = [
        ...messages,
        { role: 'assistant', content: "I couldn't reach Confidant just now. Please try again in a moment.", created_at: '' },
      ];
    } finally {
      sending = false;
      closeStream();
    }
  }
</script>

<div class="journey">
  <div class="scroll-fade" aria-hidden="true"></div>

  <button type="button" class="back" onclick={onBack}>&larr; Home</button>

  <Transcript {messages} />
  {#if loaded && messages.length === 0}
    <p class="voice opening-prompt">{openingPrompt}</p>
  {/if}
  {#if sending}<AmbientPresence {pulseCount} />{/if}
  <Composer disabled={sending} onSend={handleSend} />

  <Understanding {brief} {tier2} {deepeningClarityNote} />
</div>

<style>
  .back {
    display: block;
    margin-bottom: var(--space-3);
  }

  .opening-prompt {
    color: var(--ink-muted);
    margin: var(--space-3) 0;
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
