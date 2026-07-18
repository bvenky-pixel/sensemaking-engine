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
  //
  // Orb as consciousness (2026-07-18, see frontend/decisions.md "Orb as
  // consciousness"): direct founder framing -- "the orb is Confidant, it
  // is consciousness" -- so the hero now opens with a real teaching
  // (ZenQuote, a new one each page load) between the orb and the mode
  // prompt, not decoration alone.
  //
  // The orb stays here too (2026-07-18, see frontend/decisions.md "The
  // orb stays, and it tells you what it's doing"): direct founder
  // feedback -- "the orb is not present on the home screen after the
  // first journey populates the screen." The hero's own big orb is
  // deliberately conditional on `sessions.length === 0` (see the "Home
  // hero" comment above -- that tradeoff is still correct, promoting
  // the full hero once real history exists would push it down for no
  // benefit), but that meant Home behaved exactly like Journey used to:
  // an orb that only exists in the empty state and vanishes the moment
  // there's anything else to show. Same fix as Journey's own
  // `.orb-companion` -- a small, always-present `BreathingOrb compact`
  // next to the greeting once the populated branch is showing, so the
  // orb is never fully absent from Home again.
  //
  // Home: time period + mode filtering (2026-07-18, see
  // frontend/decisions.md) -- direct founder request: "reduce the
  // clutter on the screen" as Journeys accumulate, via a This week/This
  // month/This year/All time toggle (with a count per period) plus a
  // mode filter scoped to whichever modes are actually present within
  // the selected period. Boundaries are computed client-side against
  // the browser's own local time -- this app has no per-person
  // timezone stored anywhere (see src/api/db.py's own "single-user
  // simplification" note), so a server-side "this week" would either
  // hardcode UTC (wrong for most people, most of the time) or need new
  // timezone infrastructure neither asked for nor needed just for this.
  // Both filters compose with the existing bookmark filter and with
  // each other -- switching time period resets the mode filter (a
  // mode selected in "This month" may not exist at all in "This
  // week"), never the reverse.
  //
  // One "all", not two (2026-07-18): the bookmark filter used to be a
  // separate All/Bookmarked pair, which sat right next to the new "All
  // time" period pill and read as two different, competing "show
  // everything" buttons. Collapsed to a single "★ Bookmarked only"
  // toggle -- off (the default) already means "show everything the
  // period/mode filters allow", so a redundant explicit "All" had
  // nothing left to mean.
  //
  // Auth, the low-friction way (2026-07-18, see frontend/decisions.md):
  // bookmarking is a login-required action now, same as delete in
  // Journey's own overflow menu -- direct founder follow-up. Tapping a
  // journey card's star while signed out shows the same shared
  // LoginGate instead of a doomed API call. A "Log in" link also sits
  // at the bottom of Home now, "in line with Settings" (direct founder
  // ask) -- Settings' own gate already gets someone there eventually,
  // but a person who just wants to log in shouldn't have to detour
  // through Settings first to find where.
  import { onMount } from 'svelte';
  import { fade, fly } from 'svelte/transition';
  import { listSessions, setBookmark, createSession, getModes } from '../lib/api.js';
  import BreathingOrb from '../components/BreathingOrb.svelte';
  import ZenQuote from '../components/ZenQuote.svelte';
  import ModePicker from '../components/ModePicker.svelte';
  import LoginGate from '../components/LoginGate.svelte';
  import { authState } from '../lib/auth.svelte.js';
  import { tintFor } from '../lib/modeTints.js';

  let { onOpen, onSettings, onBeginNew } = $props();

  let sessions = $state([]);
  let showBookmarkedOnly = $state(false);
  let showLoginGate = $state(false);
  // Guards against a one-frame flash of the hero (orb + mode picker)
  // before the first real listSessions() call resolves -- unlike the
  // old single-button design, the hero and the journey list are now
  // visually distinct enough that briefly showing the wrong one on
  // every load would read as a glitch, not a loading state.
  let loaded = $state(false);
  let starting = $state(false);
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
  <div class="header">
    <p class="display">A quiet place to think something through.</p>
    {#if loaded && (showBookmarkedOnly || sessions.length > 0)}
      <BreathingOrb compact />
    {/if}
  </div>

  {#if showLoginGate}
    <div class="login-gate-card card" in:fade={{ duration: 220 }}>
      <LoginGate message="Log in to bookmark Journeys." />
    </div>
  {/if}

  {#if loaded && !showBookmarkedOnly && sessions.length === 0}
    <div class="hero" in:fade={{ duration: 320 }}>
      <BreathingOrb />
      <ZenQuote />
      <p class="voice hero-copy">Pick what fits right now.</p>
      <ModePicker onChoose={chooseMode} {starting} />
    </div>
  {:else if loaded}
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
    {:else if sessions.length === 0}
      <p class="voice" transition:fade={{ duration: 200 }}>No bookmarked Journeys yet.</p>
    {:else}
      <p class="voice" transition:fade={{ duration: 200 }}>No Journeys in this time period.</p>
    {/if}

    <button type="button" class="btn-primary start" onclick={onBeginNew}>
      + Begin something new
    </button>
  {/if}

  <div class="bottom-links">
    <button type="button" class="ui-label settings-link" onclick={onSettings}>Settings</button>
    {#if authState.checked && !authState.authenticated}
      <button type="button" class="ui-label settings-link" onclick={() => (showLoginGate = true)}>
        Log in
      </button>
    {/if}
  </div>
</div>

<style>
  .header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
    margin: 0 0 var(--space-4);
  }

  .display {
    margin: 0;
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

  /* Journey rows become cards -- now the shared .card/.card-interactive
     recipe from tokens.css (see that file's own comment on why this is
     no longer hand-duplicated). Mode-tint left edge (see script
     comment) mirrors ModePicker's own per-mode color coding -- only
     drawn when a Journey actually has a mode (--mode-tint is only set
     inline for those), so a mode-less legacy Journey stays a plain
     card rather than getting an arbitrary default color implying a
     mode it doesn't have. */
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

  /* Login link "in line with Settings" (see script comment) -- a plain
     flex row so both share the same top margin/spacing rhythm the
     lone Settings link used to have on its own, rather than stacking
     with a second margin-top of its own. */
  .bottom-links {
    display: flex;
    gap: var(--space-3);
    margin-top: var(--space-5);
  }

  .settings-link {
    display: block;
  }

  /* Bookmark login gate (see script comment on showLoginGate) -- same
     .card recipe every other login prompt in this app uses. */
  .login-gate-card {
    margin-bottom: var(--space-3);
    padding: var(--space-3);
  }
</style>
