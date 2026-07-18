<script>
  // Not a dashboard: no counts, no metrics, no activity feed (see
  // information-architecture-v1.md's "Three Spaces" section). A calm
  // list of Journeys and one unforced way to begin a new one.
  //
  // Frontend redesign increment 3, final of three (see
  // frontend/decisions.md, interaction-model-v4.md's guardrail relaxed
  // 2026-07-11): Journey rows become cards, a plain-text bookmark
  // toggle and All/Bookmarked filter, a stagnation-based "worth
  // returning to" aside, and the reserved `.display` typographic
  // moment finally used for Home's own greeting.
  //
  // Home hero: orb + inline modes (2026-07-18, see
  // frontend/decisions.md "Home hero"). Direct founder feedback: with
  // no Journeys yet, Home left most of the page empty around one lonely
  // button. Discussed two options (a bigger button, or giving the
  // existing button's surroundings more content) and landed on a third,
  // combined one: a decorative BreathingOrb as a calm focal point, plus
  // the mode picker brought inline -- reducing the empty-account tap
  // count from "tap Begin -> tap a mode" down to "tap a mode" directly.
  // Deliberately CONDITIONAL on sessions.length, not always-on: the
  // founder's own framing of the tradeoff was real ("home screen is
  // more cluttered but we reduce friction") -- once real Journeys
  // exist, promoting six mode cards above them every single visit would
  // push a returning person's actual history down the page for no
  // benefit, so the hero collapses back to the original single "+Begin
  // something new" button (which still routes to the full ModeSelect
  // screen) the moment there's anything to show instead.
  import { onMount } from 'svelte';
  import { fade, fly } from 'svelte/transition';
  import { listSessions, setBookmark, createSession } from '../lib/api.js';
  import BreathingOrb from '../components/BreathingOrb.svelte';
  import ModePicker from '../components/ModePicker.svelte';

  let { onOpen, onSettings, onBeginNew } = $props();

  let sessions = $state([]);
  let showBookmarkedOnly = $state(false);
  // Guards against a one-frame flash of the hero (orb + mode picker)
  // before the first real listSessions() call resolves -- unlike the
  // old single-button design, the hero and the journey list are now
  // visually distinct enough that briefly showing the wrong one on
  // every load would read as a glitch, not a loading state.
  let loaded = $state(false);
  let starting = $state(false);

  async function refresh() {
    sessions = await listSessions(showBookmarkedOnly);
    loaded = true;
  }

  onMount(refresh);

  async function toggleFilter(bookmarkedOnly) {
    showBookmarkedOnly = bookmarkedOnly;
    await refresh();
  }

  async function toggleBookmark(event, session) {
    event.stopPropagation();
    const nextBookmarked = !session.bookmarked;
    await setBookmark(session.id, nextBookmarked);
    await refresh();
  }

  // Same create-then-open flow as ModeSelect.svelte's own choose() --
  // duplicated rather than shared (this codebase's own small-utility
  // duplication convention), since the two call sites differ in what
  // happens around it (ModeSelect navigates via onBack/a whole separate
  // screen; Home does this inline on its own screen).
  async function chooseMode(modeId) {
    starting = true;
    try {
      const { id } = await createSession(modeId);
      onOpen(id);
    } finally {
      starting = false;
    }
  }
</script>

<div class="home">
  <p class="display">A quiet place to think something through.</p>

  {#if loaded && !showBookmarkedOnly && sessions.length === 0}
    <div class="hero" in:fade={{ duration: 320 }}>
      <BreathingOrb />
      <p class="voice hero-copy">Pick what fits right now.</p>
      <ModePicker onChoose={chooseMode} {starting} />
    </div>
  {:else if loaded}
    {#if sessions.length > 0 || showBookmarkedOnly}
      <div class="filter">
        <button
          type="button"
          class="ui-label filter-option"
          class:active={!showBookmarkedOnly}
          onclick={() => toggleFilter(false)}
        >
          All
        </button>
        <button
          type="button"
          class="ui-label filter-option"
          class:active={showBookmarkedOnly}
          onclick={() => toggleFilter(true)}
        >
          Bookmarked
        </button>
      </div>
    {/if}

    {#if sessions.length > 0}
      <ul class="journeys">
        {#each sessions as session, i (session.id)}
          <li in:fly={{ y: 12, duration: 320, delay: Math.min(i * 40, 240) }}>
            <button type="button" class="journey-card card card-interactive" onclick={() => onOpen(session.id)}>
              <div class="journey-row">
                <span>{session.preview_text || 'A new Journey'}</span>
                <span
                  type="button"
                  role="button"
                  tabindex="0"
                  class="bookmark"
                  class:bookmarked={session.bookmarked}
                  aria-label={session.bookmarked ? 'Remove bookmark' : 'Bookmark this Journey'}
                  onclick={(event) => toggleBookmark(event, session)}
                  onkeydown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') toggleBookmark(event, session);
                  }}
                >
                  {session.bookmarked ? '★' : '☆'}
                </span>
              </div>
              {#if session.has_stagnation_signal}
                <p class="voice aside">There's more to think through here.</p>
              {/if}
              {#if session.insight_detail}
                <p class="voice aside insight-aside">This has come up before, too. {session.insight_detail}</p>
              {/if}
            </button>
          </li>
        {/each}
      </ul>
    {:else if showBookmarkedOnly}
      <p class="voice" transition:fade={{ duration: 200 }}>No bookmarked Journeys yet.</p>
    {/if}

    <button type="button" class="btn-primary start" onclick={onBeginNew}>
      + Begin something new
    </button>
  {/if}

  <button type="button" class="ui-label settings-link" onclick={onSettings}>Settings</button>
</div>

<style>
  .display {
    margin: 0 0 var(--space-4);
  }

  .hero {
    text-align: center;
  }

  .hero-copy {
    color: var(--ink-muted);
    margin: 0 0 var(--space-3);
  }

  /* The mode cards themselves stay left-aligned (label/description read
     better that way) even though the orb + intro line above them are
     centered. */
  .hero :global(.modes) {
    text-align: left;
  }

  .filter {
    display: flex;
    gap: var(--space-3);
    margin-bottom: var(--space-3);
  }

  .filter-option {
    opacity: 0.5;
    transition: opacity var(--motion-quick) ease-out;
  }

  .filter-option.active {
    opacity: 1;
    color: var(--accent);
  }

  .journeys {
    list-style: none;
    margin: 0 0 var(--space-4);
    padding: 0;
  }

  .journeys li {
    margin-bottom: var(--space-2);
  }

  /* Journey rows become cards -- now the shared .card/.card-interactive
     recipe from tokens.css (see that file's own comment on why this is
     no longer hand-duplicated). */
  .journey-card {
    display: block;
    width: 100%;
    text-align: left;
    padding: var(--space-3);
  }

  .journey-row {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: var(--space-2);
    color: var(--ink);
    font-family: var(--font-body);
    font-size: 17px;
    font-weight: 600;
  }

  .bookmark {
    flex-shrink: 0;
    font-family: var(--font-ui);
    color: var(--ink-muted);
    cursor: pointer;
    font-size: 18px;
    transition: transform var(--motion-bouncy), color var(--motion-quick);
  }

  .bookmark.bookmarked {
    color: var(--accent-5);
  }

  .bookmark:hover {
    transform: scale(1.15);
  }

  .aside {
    margin: var(--space-1) 0 0;
  }

  /* Distinct from the stagnation aside above -- a quiet noticing across
     Journeys, not a flag about this one Journey (see engine/decisions.md
     "Major update"). Same aside rhythm, accent-colored rather than
     ink-muted, no "Insight:" label per interaction-model-v4.md's
     felt-difference rule. */
  .insight-aside {
    color: var(--accent-2);
  }

  .start {
    margin-top: var(--space-3);
    width: 100%;
  }

  .settings-link {
    display: block;
    margin-top: var(--space-5);
  }
</style>
