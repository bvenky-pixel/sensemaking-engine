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
  import { onMount } from 'svelte';
  import { fade, fly } from 'svelte/transition';
  import { listSessions, setBookmark } from '../lib/api.js';

  // "+ Begin something new" hands off to a mode-select step (see
  // engine/decisions.md "Counseling modes") rather than creating a
  // session itself -- App.svelte owns that screen transition;
  // ModeSelect.svelte is the one that actually calls createSession now.
  let { onOpen, onSettings, onBeginNew } = $props();

  let sessions = $state([]);
  let showBookmarkedOnly = $state(false);

  async function refresh() {
    sessions = await listSessions(showBookmarkedOnly);
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

</script>

<div class="home">
  <p class="display">A quiet place to think something through.</p>

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

  <button type="button" class="ui-label settings-link" onclick={onSettings}>Settings</button>
</div>

<style>
  .display {
    margin: 0 0 var(--space-4);
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
