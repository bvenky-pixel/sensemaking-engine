<script>
  import { onMount } from 'svelte';
  import { fade } from 'svelte/transition';
  import {
    getMessages,
    sendMessage,
    getClarityBrief,
    getUnderstanding,
    openStageStream,
    deleteSession,
    getBookmark,
    setBookmark,
  } from '../lib/api.js';
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
  let menuOpen = $state(false);
  let menuEl = $state(null);
  let bookmarked = $state(false);
  let togglingBookmark = $state(false);
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
    const bookmark = await getBookmark(sessionId);
    bookmarked = bookmark.bookmarked;
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

  // Tuck destructive/secondary Journey actions behind an overflow menu
  // (2026-07-18, see frontend/decisions.md): direct founder feedback,
  // raised as a real worry after Delete first moved here from Settings
  // -- "having it during an ongoing journey is too much, I risk losing
  // data every time." A standing red delete link at the bottom of every
  // Journey (see the prior round's own `.journey-footer`) was in view
  // on every scroll-down of every Journey, active or not -- a
  // fundamentally different risk than something a person has to
  // deliberately go looking for. This menu (triggered by a quiet "..."
  // near the back button) requires that deliberate lookup; the delete
  // action itself keeps its own two-step confirm on top, not instead of,
  // this extra layer of "you have to go find it first."
  //
  // Bookmark also lives here now, per the same request ("you can also
  // add other journey level functions like bookmark in the same
  // place") -- Home already has its own bookmark star per row, but a
  // person reading/writing an open Journey had no way to bookmark THIS
  // one without leaving the screen. Non-destructive and reversible, so
  // it toggles immediately on click, no confirm step -- only Delete
  // needs one.
  function toggleMenu() {
    menuOpen = !menuOpen;
    if (!menuOpen) pendingDelete = false;
  }

  function closeMenu() {
    menuOpen = false;
    pendingDelete = false;
  }

  async function toggleBookmark() {
    togglingBookmark = true;
    const next = !bookmarked;
    try {
      await setBookmark(sessionId, next);
      bookmarked = next;
    } finally {
      togglingBookmark = false;
    }
    closeMenu();
  }

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

  // Closes the menu on any click outside it -- standard click-outside
  // pattern, added/removed only while the menu is actually open. Safe
  // against self-triggering on the same click that opened it: this
  // effect only attaches once Svelte re-renders after toggleMenu's own
  // click handler has already finished running, by which point that
  // click event has already fully dispatched.
  $effect(() => {
    if (!menuOpen) return;
    function handleClickOutside(event) {
      if (menuEl && !menuEl.contains(event.target)) {
        closeMenu();
      }
    }
    document.addEventListener('click', handleClickOutside, true);
    return () => document.removeEventListener('click', handleClickOutside, true);
  });
</script>

<div class="journey">
  <div class="scroll-fade" aria-hidden="true"></div>

  <div class="journey-header">
    <button type="button" class="back" onclick={onBack}>&larr; Home</button>

    <div class="menu-wrap" bind:this={menuEl}>
      <button
        type="button"
        class="menu-trigger"
        aria-label="Journey options"
        aria-haspopup="true"
        aria-expanded={menuOpen}
        onclick={toggleMenu}
      >
        &bull;&bull;&bull;
      </button>
      {#if menuOpen}
        <div class="journey-menu" role="menu">
          {#if pendingDelete}
            <p class="voice menu-confirm">Delete this Journey for good? This can't be undone.</p>
            <button type="button" class="link-button danger menu-item" onclick={confirmDelete} disabled={deleting}>
              {deleting ? 'Deleting…' : 'Yes, delete it'}
            </button>
            <button type="button" class="link-button menu-item" onclick={cancelDelete}>Cancel</button>
          {:else}
            <button type="button" class="link-button menu-item" onclick={toggleBookmark} disabled={togglingBookmark}>
              {bookmarked ? '★ Remove bookmark' : '☆ Bookmark this Journey'}
            </button>
            <button type="button" class="link-button danger menu-item" onclick={askToDelete}>
              Delete this Journey
            </button>
          {/if}
        </div>
      {/if}
    </div>
  </div>

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
</div>

<style>
  /* Tuck destructive/secondary Journey actions behind an overflow menu
     (see script comment) -- back button and the menu trigger share one
     row instead of back button alone owning the top of the screen. */
  .journey-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: var(--space-3);
  }

  .back {
    display: block;
  }

  .menu-wrap {
    position: relative;
  }

  /* Deliberately quiet -- three dots, ink-muted, no border or
     background until pressed -- the same "don't compete with the
     conversation" restraint the old bottom-of-screen delete link had,
     now applied to something that has to sit up near the transcript
     instead of below it. */
  .menu-trigger {
    font-size: 20px;
    line-height: 1;
    letter-spacing: 1px;
    color: var(--ink-muted);
    padding: var(--space-1) var(--space-2);
  }

  .journey-menu {
    position: absolute;
    top: 100%;
    right: 0;
    margin-top: var(--space-1);
    min-width: 220px;
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    padding: var(--space-2);
    background: var(--paper-raised);
    border-radius: var(--radius);
    box-shadow: var(--shadow-lifted);
    z-index: 2;
  }

  .menu-item {
    display: block;
    width: 100%;
    text-align: left;
    padding: var(--space-1) 0;
  }

  .menu-confirm {
    font-size: 13px;
    color: var(--ink-muted);
    margin: 0 0 var(--space-1);
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
