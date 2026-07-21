<script>
  // Activity tab (2026-07-21, backlog #262, see
  // information-architecture-v2.md, engine/decisions.md "Frontend IA
  // v2") -- Home's own journey-list markup, relocated wholesale, not
  // rebuilt: time-period/mode filtering, the bookmark star and its
  // login gate, the stagnation/insight asides, and the post-Journey
  // completion login nudge (moved here from Home since it's about a
  // Journey now sitting in THIS list, not about starting something
  // new). Home itself no longer shows this content at all -- see
  // Home.svelte's own docstring for what it kept.
  //
  // Deliberately has NO "+ Begin something new" button of its own --
  // that action now lives permanently on the tab bar's center action
  // (backlog #264), reachable from every screen including this one, so
  // duplicating it here would just be the same affordance twice.
  import { onMount } from 'svelte';
  import { fade, fly } from 'svelte/transition';
  import { listSessions, setBookmark, getModes } from '../lib/api.js';
  import LoginGate from '../components/LoginGate.svelte';
  import { authState } from '../lib/auth.svelte.js';
  import { consumeCompletionNudge } from '../lib/loginNudge.svelte.js';
  import { tintFor } from '../lib/modeTints.js';

  let { onOpen } = $props();

  let sessions = $state([]);
  let showBookmarkedOnly = $state(false);
  let showLoginGate = $state(false);
  let completionNudge = $state(null);
  let showCompletionLoginForm = $state(false);
  let loaded = $state(false);
  let timePeriod = $state('all');
  let modeFilter = $state(null);
  let modeLabels = $state({});

  const TIME_PERIODS = [
    { id: 'week', label: 'This week' },
    { id: 'month', label: 'This month' },
    { id: 'year', label: 'This year' },
    { id: 'all', label: 'All time' },
  ];

  function startOfWeek(now) {
    const d = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const day = d.getDay();
    d.setDate(d.getDate() + (day === 0 ? -6 : 1) - day); // Monday as week start
    return d;
  }

  function startOfMonth(now) {
    return new Date(now.getFullYear(), now.getMonth(), 1);
  }

  function startOfYear(now) {
    return new Date(now.getFullYear(), 0, 1);
  }

  const PERIOD_START = { week: startOfWeek, month: startOfMonth, year: startOfYear };

  function withinPeriod(session, periodId) {
    if (periodId === 'all') return true;
    return new Date(session.updated_at) >= PERIOD_START[periodId](new Date());
  }

  let periodCounts = $derived(
    Object.fromEntries(TIME_PERIODS.map((p) => [p.id, sessions.filter((s) => withinPeriod(s, p.id)).length]))
  );

  let periodSessions = $derived(sessions.filter((s) => withinPeriod(s, timePeriod)));

  // Only modes actually present in the currently-selected period --
  // showing all six mode chips regardless of what's there would be
  // exactly the clutter this feature exists to cut down on.
  let modesInPeriod = $derived([...new Set(periodSessions.map((s) => s.mode).filter(Boolean))]);

  let filteredSessions = $derived(
    modeFilter ? periodSessions.filter((s) => s.mode === modeFilter) : periodSessions
  );

  async function refresh() {
    sessions = await listSessions(showBookmarkedOnly);
    loaded = true;
  }

  onMount(async () => {
    await refresh();
    const modes = await getModes();
    modeLabels = Object.fromEntries(modes.map((m) => [m.id, m.label]));
    completionNudge = consumeCompletionNudge();
  });

  async function toggleFilter(bookmarkedOnly) {
    showBookmarkedOnly = bookmarkedOnly;
    await refresh();
  }

  function selectPeriod(periodId) {
    timePeriod = periodId;
    modeFilter = null;
  }

  function selectModeFilter(modeId) {
    modeFilter = modeFilter === modeId ? null : modeId;
  }

  async function toggleBookmark(event, session) {
    event.stopPropagation();
    if (!authState.authenticated) {
      showLoginGate = true;
      return;
    }
    const nextBookmarked = !session.bookmarked;
    await setBookmark(session.id, nextBookmarked);
    await refresh();
  }
</script>

<div class="activity">
  <p class="display">Activity</p>

  {#if completionNudge}
    <div class="completion-nudge card" in:fade={{ duration: 220 }}>
      {#if showCompletionLoginForm}
        <LoginGate
          message="Sign in to keep that Journey accessible everywhere."
          returnSessionId={completionNudge.sessionId}
        />
      {:else}
        <p class="voice completion-message">
          Want to keep that accessible everywhere?
          <button type="button" class="link-button" onclick={() => (showCompletionLoginForm = true)}>
            Sign in
          </button>
        </p>
        <button
          type="button"
          class="dismiss"
          aria-label="Dismiss"
          onclick={() => (completionNudge = null)}
        >
          &times;
        </button>
      {/if}
    </div>
  {/if}

  {#if loaded}
    {#if sessions.length > 0 || showBookmarkedOnly}
      <div class="period-filter">
        {#each TIME_PERIODS as period (period.id)}
          <button
            type="button"
            class="ui-label filter-option"
            class:active={timePeriod === period.id}
            aria-label="{period.label} filter"
            onclick={() => selectPeriod(period.id)}
          >
            {period.label} <span class="count">{periodCounts[period.id]}</span>
          </button>
        {/each}
      </div>

      <div class="filter">
        <button
          type="button"
          class="ui-label filter-option"
          class:active={showBookmarkedOnly}
          onclick={() => toggleFilter(!showBookmarkedOnly)}
        >
          ★ Bookmarked only
        </button>
      </div>

      {#if modesInPeriod.length > 1}
        <div class="mode-filter" transition:fade={{ duration: 200 }}>
          <button type="button" class="mode-chip" class:active={!modeFilter} onclick={() => (modeFilter = null)}>
            All modes
          </button>
          {#each modesInPeriod as modeId (modeId)}
            <button
              type="button"
              class="mode-chip"
              class:active={modeFilter === modeId}
              style="--mode-tint: {tintFor(modeId)}"
              onclick={() => selectModeFilter(modeId)}
            >
              <span class="mode-chip-dot"></span>{modeLabels[modeId] || modeId}
            </button>
          {/each}
        </div>
      {/if}
    {/if}

    {#if filteredSessions.length > 0}
      <ul class="journeys">
        {#each filteredSessions as session, i (session.id)}
          <li in:fly={{ y: 12, duration: 320, delay: Math.min(i * 40, 240) }}>
            <button
              type="button"
              class="journey-card card card-interactive"
              style={session.mode ? `--mode-tint: ${tintFor(session.mode)}` : ''}
              onclick={() => onOpen(session.id)}
            >
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
              {#if session.stagnation_note}
                <p class="voice aside">{session.stagnation_note}</p>
              {:else if session.has_stagnation_signal}
                <p class="voice aside">There's more to think through here.</p>
              {/if}
              {#if session.insight_detail}
                <p class="voice aside insight-aside">This has come up before, too. {session.insight_detail}</p>
              {/if}
            </button>
          </li>
        {/each}
      </ul>
    {:else if sessions.length === 0 && showBookmarkedOnly}
      <p class="voice" transition:fade={{ duration: 200 }}>No bookmarked Journeys yet.</p>
    {:else if sessions.length === 0}
      <p class="voice" transition:fade={{ duration: 200 }}>
        Nothing here yet -- tap the + below to begin a new Journey.
      </p>
    {:else}
      <p class="voice" transition:fade={{ duration: 200 }}>No Journeys in this time period.</p>
    {/if}
  {/if}

  {#if showLoginGate}
    <div class="login-gate-card card" in:fade={{ duration: 220 }}>
      <LoginGate message="Log in to bookmark Journeys." />
    </div>
  {/if}
</div>

<style>
  .display {
    margin: 0 0 var(--space-4);
  }

  /* Time period toggle (see script comment) -- same understated
     .ui-label pill-of-text treatment as .filter below, just with a
     count riding along. flex-wrap so four options + counts never
     force horizontal scroll on a narrow phone. */
  .period-filter {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1) var(--space-3);
    margin-bottom: var(--space-2);
  }

  .count {
    opacity: 0.7;
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

  /* Mode filter chips (see script comment) -- same tinted-left-edge
     language ModePicker's own mode cards already established, shrunk
     to a small pill so a whole row of them reads as a filter, not a
     second list of things to choose. Only ever shows modes actually
     present in the current period (see modesInPeriod), so it never
     grows past what's genuinely useful to filter by. */
  .mode-filter {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
    margin-bottom: var(--space-3);
  }

  .mode-chip {
    display: flex;
    align-items: center;
    gap: 6px;
    font-family: var(--font-ui);
    font-size: 13px;
    font-weight: 700;
    color: var(--ink-muted);
    background: var(--paper-raised);
    border: 2px solid var(--line);
    border-radius: var(--radius-pill);
    padding: 5px var(--space-2);
    transition: border-color var(--motion-quick) ease-out, color var(--motion-quick) ease-out;
  }

  .mode-chip.active {
    color: var(--ink);
    border-color: var(--mode-tint, var(--accent));
  }

  .mode-chip-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--mode-tint, var(--ink-muted));
    flex-shrink: 0;
  }

  .journeys {
    list-style: none;
    margin: 0 0 var(--space-4);
    padding: 0;
  }

  .journeys li {
    margin-bottom: var(--space-2);
  }

  /* Journey rows become cards -- the shared .card/.card-interactive
     recipe from tokens.css. Mode-tint left edge mirrors ModePicker's
     own per-mode color coding -- only drawn when a Journey actually
     has a mode. */
  .journey-card {
    display: block;
    width: 100%;
    text-align: left;
    padding: var(--space-3);
    border-left: 4px solid var(--mode-tint, transparent);
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
     Journeys, not a flag about this one Journey. Same aside rhythm,
     accent-colored rather than ink-muted, no "Insight:" label per
     interaction-model-v4.md's felt-difference rule. */
  .insight-aside {
    color: var(--accent-2);
  }

  /* Bookmark login gate -- same .card recipe every other login prompt
     in this app uses. */
  .login-gate-card {
    margin-top: var(--space-3);
    padding: var(--space-3);
  }

  /* Journey-completion login nudge -- same quiet, dismissible recipe as
     Journey.svelte's own .proximity-nudge. */
  .completion-nudge {
    position: relative;
    margin-bottom: var(--space-3);
    padding: var(--space-2) var(--space-5) var(--space-2) var(--space-3);
  }

  .completion-message {
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
</style>
