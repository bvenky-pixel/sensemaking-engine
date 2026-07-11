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
  import { listSessions, createSession, setBookmark } from '../lib/api.js';

  let { onOpen, onSettings } = $props();

  let sessions = $state([]);
  let starting = $state(false);
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

  async function startNew() {
    starting = true;
    try {
      const { id } = await createSession();
      onOpen(id);
    } finally {
      starting = false;
    }
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
      {#each sessions as session}
        <li>
          <button type="button" class="journey-card" onclick={() => onOpen(session.id)}>
            <div class="journey-row">
              <span>{session.surface_complaint || 'A new Journey'}</span>
              <span
                type="button"
                role="button"
                tabindex="0"
                class="bookmark"
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
          </button>
        </li>
      {/each}
    </ul>
  {:else if showBookmarkedOnly}
    <p class="voice">No bookmarked Journeys yet.</p>
  {/if}

  <button type="button" class="start" disabled={starting} onclick={startNew}>
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
  }

  .filter-option.active {
    opacity: 1;
  }

  .journeys {
    list-style: none;
    margin: 0 0 var(--space-4);
    padding: 0;
  }

  .journeys li {
    margin-bottom: var(--space-2);
  }

  /* Journey rows become cards -- same settled-card recipe established
     in Understanding.svelte, kept as a local, scoped duplicate rather
     than a shared class (no premature abstraction yet). */
  .journey-card {
    display: block;
    width: 100%;
    text-align: left;
    background: var(--paper-raised);
    border-radius: var(--radius);
    box-shadow: 0 1px 0 var(--line);
    padding: var(--space-2) var(--space-3);
  }

  .journey-row {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: var(--space-2);
    color: var(--ink);
    font-family: var(--serif);
    font-size: 17px;
  }

  .bookmark {
    flex-shrink: 0;
    font-family: var(--sans);
    color: var(--ink-muted);
    cursor: pointer;
  }

  .aside {
    margin: var(--space-1) 0 0;
  }

  .start {
    margin-top: var(--space-3);
  }

  .settings-link {
    display: block;
    margin-top: var(--space-5);
  }
</style>
