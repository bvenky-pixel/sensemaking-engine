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
    getPrivacySettings,
    submitJourneyReflection,
    ApiError,
  } from '../lib/api.js';
  import { honestFailureMessage } from '../lib/honestFailure.js';
  import { noteDeepeningClarity } from '../lib/deepeningClarity.js';
  import Transcript from '../components/Transcript.svelte';
  import Composer from '../components/Composer.svelte';
  import AmbientPresence from '../components/AmbientPresence.svelte';
  import BreathingOrb from '../components/BreathingOrb.svelte';
  import Understanding from '../components/Understanding.svelte';
  import LoginGate from '../components/LoginGate.svelte';
  import { authState } from '../lib/auth.svelte.js';
  import { markJourneyCompleted } from '../lib/loginNudge.svelte.js';

  // Proximity login nudge (2026-07-18, see frontend/decisions.md "Two
  // earlier login nudges"): a soft, dismissible note ahead of the hard
  // response-limit wall, not just at it. 7 is deliberately below
  // ANONYMOUS_MESSAGE_LIMIT (10, src/api/server.py) -- not fetched from
  // the backend (this codebase has no shared-constants mechanism
  // between the two), so keep this in sync by hand if that number ever
  // changes.
  const PROXIMITY_NUDGE_THRESHOLD = 7;

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
  // Understanding panel collapsed by default (2026-07-22, direct founder
  // feedback, screen overhaul round) -- see the template's own comment
  // on the toggle for why this reverses backlog #236's earlier
  // always-visible placement.
  let understandingExpanded = $state(false);
  // Streamed Response text (2026-07-22, backlog #233, see
  // engine/decisions.md "Stream Response text token-by-token") --
  // accumulates raw response_text fragments as openStageStream's onToken
  // callback delivers them. Rendered as a provisional last message
  // (see displayMessages below) while `sending` is still true; cleared
  // the instant the REAL response is appended so there's never a tick
  // where both the provisional and the real message are visible at once.
  let streamingText = $state('');
  // Only shows the provisional streaming bubble once there's something
  // to show -- before the first token arrives, the existing stageLabel
  // ("Sitting with it for a moment.", etc.) is still the only signal,
  // unchanged from before #233.
  let displayMessages = $derived(
    sending && streamingText
      ? [...messages, { role: 'assistant', content: streamingText, created_at: '', options: [] }]
      : messages,
  );
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
  // Basic auth (2026-07-18, see frontend/decisions.md "Auth, the
  // low-friction way") -- set when the backend turns away a message
  // with `detail: "response_limit_reached"` (ANONYMOUS_MESSAGE_LIMIT,
  // src/api/server.py). Replaces the Composer with a login prompt
  // rather than disabling it silently -- the whole point of the limit
  // is to ask for a login, not to just stop working.
  let responseLimitReached = $state(false);
  // Bookmark/delete require login too (2026-07-18, direct founder
  // follow-up): the overflow menu shows a "log in" prompt instead of
  // the two actions themselves when signed out, and this flips on when
  // that prompt is tapped -- rendered as its own small card rather than
  // replacing the Composer, since being signed out doesn't stop the
  // conversation itself, only these two actions.
  let showActionsLoginGate = $state(false);
  // Same proximity-nudge feature as PROXIMITY_NUDGE_THRESHOLD above --
  // dismissing just hides it for the rest of THIS Journey (in-memory
  // only, not persisted); a later Journey that also gets close to the
  // limit shows it again, since it's a factually true, non-repeating-
  // within-one-conversation note, not a nagging global gate.
  let proximityNudgeDismissed = $state(false);
  let showProximityLoginForm = $state(false);
  let userMessageCount = $derived(messages.filter((m) => m.role === 'user').length);

  // Journey-close reflection question (2026-07-19, backlog #207) --
  // opt-in, see Settings.svelte's own toggle. `reflectionPromptEnabled`
  // is fetched once on mount, same "read privacy settings once,
  // logged-in only" pattern Settings.svelte itself uses.
  // `showReflectionPrompt` gates handleBack's own navigation below --
  // shown instead of immediately calling onBack(), not on top of it.
  let reflectionPromptEnabled = $state(false);
  let showReflectionPrompt = $state(false);
  let reflectionText = $state('');
  let submittingReflection = $state(false);

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

  // Wrapped in try/catch (2026-07-18, see frontend/decisions.md "Return
  // to the same Journey after magic-link verify") -- the return-session
  // path from a just-verified magic link is the first way an id that
  // ISN'T simply copied from Home's own `session.id` can reach this
  // screen (a stale/foreign/already-deleted id, post the server's own
  // ownership check -- see AuthStatusOut's own docstring). A normal
  // open from Home never hits this catch; a bad id degrades to Home
  // instead of an unhandled rejection and a permanently blank screen.
  onMount(async () => {
    try {
      messages = await getMessages(sessionId);
      loaded = true;
      await refreshBrief();
      await refreshUnderstanding();
      const bookmark = await getBookmark(sessionId);
      bookmarked = bookmark.bookmarked;
      // Journey-close reflection question (2026-07-19, backlog #207) --
      // same "gated behind sign-in, fetched once" pattern
      // Settings.svelte's own privacy fetch uses. A failure here (or
      // being signed out) just leaves reflectionPromptEnabled at its
      // false default -- never worth failing the whole Journey load
      // over.
      if (authState.authenticated) {
        const privacy = await getPrivacySettings();
        reflectionPromptEnabled = privacy.reflection_prompt_enabled;
      }
    } catch {
      onBack();
    }
  });

  async function handleSend(content) {
    messages = [...messages, { role: 'user', content, created_at: '' }];
    sending = true;
    stageLabel = INITIAL_STAGE_LABEL;
    streamingText = '';
    // Opened synchronously, in the same call as the POST below -- see
    // AmbientPresence.svelte's own docstring for why this can't live
    // inside that component (Svelte's re-render happens on a later
    // microtask than this function's own next line, which would risk
    // missing the "interpretation" stage's event on every turn). Third
    // argument (2026-07-22, backlog #233, see engine/decisions.md
    // "Stream Response text token-by-token"): each raw response_text
    // fragment just gets appended -- displayMessages above turns the
    // running total into a provisional last message.
    const closeStream = openStageStream(
      sessionId,
      (stage) => {
        pulseCount += 1;
        if (STAGE_LABELS[stage]) stageLabel = STAGE_LABELS[stage];
      },
      (delta) => {
        streamingText += delta;
      },
    );
    try {
      const result = await sendMessage(sessionId, content);
      const text = result.response_text || honestFailureMessage(result.failed_stage);
      // Response v3 -- real choice buttons: only a genuine response_text
      // carries real, grounded options -- a failed turn's honest-failure
      // message never gets buttons attached to it.
      const options = result.response_text ? result.options || [] : [];
      messages = [...messages, { role: 'assistant', content: text, created_at: '', options }];
      // Cleared HERE, not just in `finally` below -- displayMessages'
      // own condition is `sending && streamingText`, and `sending` is
      // still true for the rest of this try block (refreshBrief/
      // refreshUnderstanding are still pending), so leaving
      // streamingText set until `finally` would render the real message
      // above AND the stale provisional bubble at once for one tick.
      streamingText = '';
      if (result.response_text) {
        await refreshBrief();
      }
      // Unlike refreshBrief above, not gated behind response_text --
      // Tier 2 (src/understanding/tier2_engine.py) runs before Planner/
      // Response in the pipeline, so it can have updated even on a turn
      // where Response Generator itself failed.
      await refreshUnderstanding();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401 && err.detail === 'response_limit_reached') {
        // Roll back the optimistic user message above -- it was never
        // actually recorded, so the transcript shouldn't claim it was.
        messages = messages.slice(0, -1);
        responseLimitReached = true;
      } else {
        messages = [
          ...messages,
          { role: 'assistant', content: "I couldn't reach Confidant just now. Please try again in a moment.", created_at: '' },
        ];
      }
    } finally {
      sending = false;
      stageLabel = '';
      streamingText = '';
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

  function openActionsLoginGate() {
    showActionsLoginGate = true;
    closeMenu();
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

  // Only populated after a real message is shared (2026-07-18, see
  // frontend/decisions.md): createSession fires the moment a mode is
  // picked (Home.svelte's own chooseMode()), before a single word has
  // been typed -- direct founder feedback that
  // backing out of that empty Journey without sending anything
  // shouldn't leave it behind. db.py::list_sessions already hides any
  // session with zero messages from Home's own list (defense in depth,
  // covers a tab close or browser-back too), but this is the active
  // half: the in-app "← Home" tap actively deletes the empty row
  // rather than leaving an orphan for that filter to hide forever.
  // Deliberately unconditional on bookmark state -- an empty Journey
  // bookmarked via this screen's own menu and then abandoned has
  // nothing in it worth keeping either.
  async function handleBack() {
    // `loaded` gates this, not just `messages.length === 0` alone -- a
    // real Journey with real history briefly has messages.length === 0
    // too, in the split second between mount and getMessages resolving;
    // deleting on THAT window instead of the genuinely-empty case would
    // be exactly the kind of accidental data loss this whole feature
    // exists to prevent.
    if (loaded && messages.length === 0) {
      await deleteSession(sessionId);
    } else if (loaded) {
      // Journey-completion login nudge (2026-07-18, see
      // frontend/decisions.md "Two earlier login nudges") -- leaving a
      // Journey that actually has content is the "winds down" moment;
      // markJourneyCompleted itself is a no-op once already signed in
      // or once this browser has ever seen the nudge before.
      markJourneyCompleted(sessionId);
      // Journey-close reflection question (2026-07-19, backlog #207) --
      // the same "winds down" moment as the login nudge above, opt-in
      // via Settings. Shown INSTEAD of navigating home immediately --
      // submitReflection/skipReflection below are what actually call
      // onBack() once the person has answered or explicitly skipped.
      if (reflectionPromptEnabled) {
        showReflectionPrompt = true;
        return;
      }
    }
    onBack();
  }

  async function submitReflection() {
    submittingReflection = true;
    try {
      await submitJourneyReflection(sessionId, reflectionText);
    } catch {
      // A failed submission must not trap the person on this screen --
      // same "never block navigation on a background action" discipline
      // as everywhere else in this file. The reflection is simply lost,
      // same honest tradeoff as any other best-effort, non-retried write.
    } finally {
      submittingReflection = false;
      onBack();
    }
  }

  function skipReflection() {
    onBack();
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
  {#if showReflectionPrompt}
    <div class="reflection-prompt card" in:fade={{ duration: 220 }}>
      <p class="voice">Before you go -- anything about this conversation you'd want to remember or reflect on?</p>
      <textarea
        class="reflection-input"
        bind:value={reflectionText}
        placeholder="Optional -- write as much or as little as you'd like."
        rows="4"
        disabled={submittingReflection}
      ></textarea>
      <div class="reflection-actions">
        <button type="button" class="link-button" onclick={skipReflection} disabled={submittingReflection}>
          Skip
        </button>
        <button
          type="button"
          class="btn-primary"
          onclick={submitReflection}
          disabled={submittingReflection || !reflectionText.trim()}
        >
          {submittingReflection ? 'Saving…' : 'Share and leave'}
        </button>
      </div>
    </div>
  {:else}
  <div class="scroll-fade" aria-hidden="true"></div>

  <div class="journey-header">
    <button type="button" class="back" onclick={handleBack}>&larr; Home</button>

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
          {#if !authState.authenticated}
            <p class="voice menu-confirm">Log in to bookmark or delete Journeys.</p>
            <button type="button" class="link-button menu-item" onclick={openActionsLoginGate}>
              Log in
            </button>
          {:else if pendingDelete}
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

  {#if showActionsLoginGate}
    <div class="actions-gate card" in:fade={{ duration: 220 }}>
      <LoginGate message="Log in to bookmark or delete this Journey." returnSessionId={sessionId} />
    </div>
  {/if}

  <Transcript messages={displayMessages} disabled={sending} onOptionSelect={handleSend} />
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

  <!-- Composer sits directly under the transcript/orb now (2026-07-22,
       direct founder feedback, screen overhaul round) -- this reverses
       backlog #236's "Clarity Brief during the wait" placement, which
       put the brief between the latest response and the reply box.
       Direct founder complaint: the brief had grown long/intimidating
       after a few rounds, and having to scroll past it just to reply
       felt disorienting -- reply should stay adjacent to what you just
       read. The Understanding panel moves below the Composer instead,
       collapsed by default (see the toggle below). -->
  {#if responseLimitReached}
    <div class="limit-gate card" in:fade={{ duration: 220 }}>
      <LoginGate
        message="You've reached the free limit for one conversation. Log in to keep going -- your Journey will be right here."
        returnSessionId={sessionId}
      />
    </div>
  {:else}
    {#if !authState.authenticated && userMessageCount >= PROXIMITY_NUDGE_THRESHOLD && !proximityNudgeDismissed}
      <div class="proximity-nudge card" in:fade={{ duration: 200 }}>
        {#if showProximityLoginForm}
          <LoginGate
            message="Sign in for unlimited replies in this conversation."
            returnSessionId={sessionId}
          />
        {:else}
          <p class="voice aside proximity-message">
            Free replies are limited per conversation.
            <button type="button" class="link-button" onclick={() => (showProximityLoginForm = true)}>
              Sign in
            </button> to keep going without a limit.
          </p>
          <button
            type="button"
            class="dismiss"
            aria-label="Dismiss"
            onclick={() => (proximityNudgeDismissed = true)}
          >
            &times;
          </button>
        {/if}
      </div>
    {/if}
    <Composer disabled={sending} onSend={handleSend} />
  {/if}

  <!-- Understanding panel, collapsed by default (see comment above) --
       only rendered (not just hidden) once expanded, so a person who
       never opens it never pays for Understanding's own render cost. -->
  {#if brief || tier2?.length}
    <button
      type="button"
      class="understanding-toggle"
      aria-expanded={understandingExpanded}
      onclick={() => (understandingExpanded = !understandingExpanded)}
    >
      <span>{understandingExpanded ? 'Hide' : 'Show'} what we understand so far</span>
      <span class="chevron" aria-hidden="true">{understandingExpanded ? '▾' : '▸'}</span>
    </button>
    {#if understandingExpanded}
      <Understanding {brief} {tier2} {deepeningClarityNote} />
    {/if}
  {/if}
  {/if}
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

  /* Journey-close reflection question (2026-07-19, backlog #207) --
     replaces the whole Journey body (same "stands in for everything
     else on screen" treatment as .limit-gate below), shown at the
     "winds down" moment right as a person leaves a Journey with real
     content, before onBack() actually navigates away. */
  .reflection-prompt {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    margin: var(--space-4) 0;
    padding: var(--space-4);
  }

  .reflection-input {
    font-family: var(--font-ui);
    font-size: 15px;
    color: var(--ink);
    background: var(--paper-raised);
    border: none;
    border-radius: var(--radius-sm);
    padding: var(--space-2) var(--space-3);
    resize: vertical;
  }

  .reflection-actions {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: var(--space-3);
  }

  /* Response-limit login gate (see script comment on
     responseLimitReached) -- same .card recipe Settings' own gated
     screen uses, standing in for the Composer at exactly the same
     spot in the layout rather than appearing as an unrelated overlay. */
  .limit-gate {
    margin-top: var(--space-4);
    padding: var(--space-3);
  }

  /* Bookmark/delete login gate (see script comment on
     showActionsLoginGate) -- sits right below the header, above the
     transcript, since it's prompted by the overflow menu right there;
     unlike .limit-gate it doesn't replace anything else on screen. */
  .actions-gate {
    margin-bottom: var(--space-3);
    padding: var(--space-3);
  }

  /* Proximity login nudge (2026-07-18, see frontend/decisions.md "Two
     earlier login nudges") -- deliberately quieter than .limit-gate:
     sits ABOVE the still-functioning Composer rather than replacing
     it, and is dismissible, since hitting this threshold doesn't
     actually stop anything yet. */
  .proximity-nudge {
    position: relative;
    margin-bottom: var(--space-3);
    padding: var(--space-2) var(--space-5) var(--space-2) var(--space-3);
  }

  .proximity-message {
    margin: 0;
  }

  .dismiss {
    position: absolute;
    top: var(--space-1);
    right: var(--space-1);
    font-size: 18px;
    line-height: 1;
    color: var(--ink-muted);
    padding: var(--space-1);
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

  /* Understanding panel toggle (see script/template comments) -- quiet,
     text-button styling matching .menu-trigger's own restraint: this is
     a secondary affordance, not something competing with the Composer
     or the transcript above it for attention. */
  .understanding-toggle {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    margin-top: var(--space-3);
    color: var(--ink-muted);
    font-size: 14px;
  }

  .understanding-toggle .chevron {
    font-size: 11px;
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
