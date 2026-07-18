<script>
  import { onMount } from 'svelte';
  import { fade } from 'svelte/transition';
  import { getMessages, sendMessage, getClarityBrief, getUnderstanding, openStageStream, deleteSession } from '../lib/api.js';
  import { honestFailureMessage } from '../lib/honestFailure.js';
  import { noteDeepeningClarity } from '../lib/deepeningClarity.js';
  import Transcript from '../components/Transcript.svelte';
  import Composer from '../components/Composer.svelte';
  import AmbientPresence from '../components/AmbientPresence.svelte';
  import BreathingOrb from '../components/BreathingOrb.svelte';
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

  // Poignant per-stage loading text (2026-07-18, see frontend/decisions.md
  // "The orb stays, and it tells you what it's doing"): direct founder
  // ask -- "poignant loading text corresponding to the backend process
  // running... to reduce latency friction." This is a deliberate,
  // explicit override of v1's "no stage labels, no text of any kind"
  // principle (see AmbientPresence.svelte's own "Round 2" comment) --
  // the founder is asking for exactly the thing that principle was
  // written to avoid, so the override is intentional, not a lapse.
  // What's KEPT from that principle's spirit: no raw backend vocabulary
  // (see Understanding.svelte's own docstring on this) -- the real
  // stage ids ("interpretation"/"judgment"/"planner"/"response", from
  // src/orchestrator/engine.py) never reach the screen; each maps to a
  // short, human phrase instead. Keyed by the stage that JUST finished
  // (openStageStream's own contract), so each phrase describes the
  // stage that starts next, not the one that just completed.
  const STAGE_LABELS = {
    interpretation: 'Sitting with it for a moment.',
    judgment: 'Thinking through what might help.',
    planner: 'Finding the words.',
  };
  const INITIAL_STAGE_LABEL = 'Taking in what you shared.';

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
  let stageLabel = $state('');
  let pendingDelete = $state(false);
  let deleting = $state(false);

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
    stageLabel = INITIAL_STAGE_LABEL;
    // Opened synchronously, in the same call as the POST below -- see
    // AmbientPresence.svelte's own docstring for why this can't live
    // inside that component (Svelte's re-render happens on a later
    // microtask than this function's own next line, which would risk
    // missing the "interpretation" stage's event on every turn).
    const closeStream = openStageStream(sessionId, (stage) => {
      pulseCount += 1;
      if (STAGE_LABELS[stage]) stageLabel = STAGE_LABELS[stage];
    });
    try {
      const result = await sendMessage(sessionId, content);
      const text = result.response_text || honestFailureMessage(result.failed_stage);
      // Response v3 -- real choice buttons: only a genuine response_text
      // carries real, grounded options -- a failed turn's honest-failure
      // message never gets buttons attached to it.
      const options = result.response_text ? result.options || [] : [];
      messages = [...messages, { role: 'assistant', content: text, created_at: '', options }];
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
      stageLabel = '';
      closeStream();
    }
  }

  // Delete a Journey, from the Journey itself (2026-07-18, see
  // frontend/decisions.md): moved here from Settings' own Data section
  // per direct founder feedback -- a person deciding to delete a
  // Journey is looking at that Journey, not digging through Settings
  // to find it again in a second, duplicate list. Same two-step-confirm
  // pattern Settings' Data section (and now Privacy's own "Forget
  // everything") already established, using the same shared
  // .link-button/.confirm recipe (now in tokens.css). Navigates back to
  // Home on success -- there's nothing left here to show.
  function askToDelete() {
    pendingDelete = true;
  }

  function cancelDelete() {
    pendingDelete = false;
  }

  async function confirmDelete() {
    deleting = true;
    try {
      await deleteSession(sessionId);
      onBack();
    } finally {
      deleting = false;
    }
  }
</script>

<div class="journey">
  <div class="scroll-fade" aria-hidden="true"></div>

  <button type="button" class="back" onclick={onBack}>&larr; Home</button>

  <Transcript {messages} disabled={sending} onOptionSelect={handleSend} />
  {#if loaded && messages.length === 0}
    <div class="opening-hero" in:fade={{ duration: 320 }}>
      <BreathingOrb />
      <p class="voice opening-prompt">{openingPrompt}</p>
    </div>
  {:else if loaded}
    <div class="orb-companion">
      {#if sending}
        <AmbientPresence {pulseCount} />
        {#key stageLabel}
          <p class="voice stage-label" in:fade={{ duration: 220 }}>{stageLabel}</p>
        {/key}
      {:else}
        <BreathingOrb compact />
      {/if}
    </div>
  {/if}
  <Composer disabled={sending} onSend={handleSend} />

  <Understanding {brief} {tier2} {deepeningClarityNote} />

  <div class="journey-footer">
    {#if pendingDelete}
      <span class="confirm">
        <span class="voice">Delete this Journey for good? This can't be undone.</span>
        <button type="button" class="link-button danger" onclick={confirmDelete} disabled={deleting}>
          {deleting ? 'Deleting…' : 'Yes, delete it'}
        </button>
        <button type="button" class="link-button" onclick={cancelDelete}>Cancel</button>
      </span>
    {:else}
      <button type="button" class="link-button danger" onclick={askToDelete}>
        Delete this Journey
      </button>
    {/if}
  </div>
</div>

<style>
  .back {
    display: block;
    margin-bottom: var(--space-3);
  }

  /* Empty-Journey opening hero (2026-07-18, see frontend/decisions.md
     "Orb, round two"): same BreathingOrb centerpiece Home shows on a
     journey-less account, now also filling a fresh Journey's own empty
     space above the Composer, not just the opening-prompt text alone. */
  .opening-hero {
    text-align: center;
    margin: var(--space-4) 0;
  }

  .opening-prompt {
    color: var(--ink-muted);
    margin: 0;
    padding: var(--space-3);
    background: var(--paper-raised);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-soft);
    text-align: left;
  }

  /* The orb stays (2026-07-18, see frontend/decisions.md "The orb
     stays, and it tells you what it's doing"): direct founder
     feedback -- "once the first response comes in the chat window the
     orb suddenly disappears, this is jarring." The old markup only
     ever rendered AmbientPresence while `sending` was true and nothing
     otherwise, so the orb vanished the instant every turn finished.
     This slot now always renders SOMETHING once the opening hero has
     passed: AmbientPresence (full mechanic, unchanged) while a turn is
     in flight, a small idle BreathingOrb the rest of the time, both at
     AmbientPresence's own 72px sizing so swapping between them reads
     as a change in intensity, not a size jump or a disappearance. */
  .orb-companion {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    min-height: 72px;
    padding: var(--space-1) 0;
  }

  /* Poignant per-stage loading text (see script comment on
     STAGE_LABELS) -- muted and smaller than .voice's usual size so it
     reads as a quiet caption next to the orb, not a second heading. */
  .stage-label {
    font-size: 15px;
    color: var(--ink-muted);
    margin: 0;
  }

  /* Delete a Journey, from the Journey itself (see script comment) --
     tucked at the very bottom, past Understanding, same "destructive
     action stays out of the way of the actual conversation" placement
     Settings gives its own Privacy actions. */
  .journey-footer {
    margin-top: var(--space-4);
    padding-top: var(--space-2);
    border-top: 1px solid var(--line);
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
