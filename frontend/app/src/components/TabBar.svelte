<script>
  // 5-tab navigation shell (2026-07-21, backlog #261, see
  // information-architecture-v2.md, engine/decisions.md "Frontend IA
  // v2"). Four persistent destinations (Home, Activity, You, Settings)
  // plus one center navigation ACTION, not a fifth destination -- it
  // starts a new Journey via the existing Mentor mode-select flow
  // rather than showing its own content, so it's visually distinct
  // (accent-filled, like .btn-primary) rather than a fifth plain tab
  // label. Text-only, no icon set -- matches every other control in
  // this app (Journey's own "← Home", Settings' own former back link);
  // introducing icons for this one piece of chrome would be a new
  // visual language this codebase has never used anywhere else.
  //
  // Responsive shape (mobile: fixed to the bottom of the viewport,
  // thumb-reachable; desktop: a plain top row, not fixed) is the one
  // deliberate, scoped exception to this app's otherwise-uniform
  // single-column layout (tokens.css's `body { max-width: 60ch }`
  // applies at every viewport width today) -- the first width-based
  // `@media` rule in this codebase. 640px is an honest first guess at
  // the mobile/desktop line, not an empirically validated breakpoint;
  // revisit if it reads wrong on a real range of devices.
  //
  // Deliberately NOT rendered while inside a Journey or ModeSelect
  // (App.svelte's own choice of when to mount this component) -- both
  // already have their own dedicated back navigation, and a persistent
  // tab bar competing with that during a live exchange would cut
  // against "navigation should never interrupt an in-progress moment
  // of thinking" (information-architecture-v2.md's own Navigation
  // Philosophy, carried from v1 unchanged).
  let { active, onNavigate, onBeginNew } = $props();
</script>

<nav class="tab-bar" aria-label="Main">
  <button
    type="button"
    class="tab"
    class:active={active === 'home'}
    aria-current={active === 'home' ? 'page' : undefined}
    onclick={() => onNavigate('home')}
  >
    Home
  </button>
  <button
    type="button"
    class="tab"
    class:active={active === 'activity'}
    aria-current={active === 'activity' ? 'page' : undefined}
    onclick={() => onNavigate('activity')}
  >
    Activity
  </button>
  <button type="button" class="tab-center" aria-label="Begin something new" onclick={onBeginNew}>
    +
  </button>
  <button
    type="button"
    class="tab"
    class:active={active === 'you'}
    aria-current={active === 'you' ? 'page' : undefined}
    onclick={() => onNavigate('you')}
  >
    You
  </button>
  <button
    type="button"
    class="tab"
    class:active={active === 'settings'}
    aria-current={active === 'settings' ? 'page' : undefined}
    onclick={() => onNavigate('settings')}
  >
    Settings
  </button>
</nav>

<style>
  .tab-bar {
    display: flex;
    align-items: center;
    justify-content: space-around;
    gap: var(--space-1);
    padding: var(--space-2);
    background: var(--paper-raised);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-soft);
    margin-bottom: var(--space-4);
  }

  .tab {
    flex: 1;
    font-family: var(--font-ui);
    font-size: 13px;
    font-weight: 700;
    color: var(--ink-muted);
    padding: var(--space-1);
    border-radius: var(--radius-sm);
    transition: color var(--motion-quick) ease-out;
  }

  .tab.active {
    color: var(--accent);
  }

  .tab-center {
    flex-shrink: 0;
    width: 40px;
    height: 40px;
    line-height: 1;
    font-size: 22px;
    font-weight: 700;
    color: var(--accent-ink);
    background: var(--accent);
    border-radius: 50%;
    box-shadow: var(--shadow-soft);
    transition: transform var(--motion-bouncy);
  }

  .tab-center:hover {
    transform: scale(1.06);
  }

  /* Mobile: fixed to the bottom of the viewport, thumb-reachable --
     App.svelte adds matching bottom padding to its own content wrapper
     on these same screens so real content never sits underneath the
     fixed bar (see App.svelte's own `.has-tab-bar` rule). */
  @media (max-width: 639px) {
    .tab-bar {
      position: fixed;
      left: var(--space-2);
      right: var(--space-2);
      bottom: var(--space-2);
      z-index: 10;
      margin-bottom: 0;
    }
  }

  /* Desktop: a plain top row, not fixed -- mouse-driven navigation
     doesn't need thumb-zone placement, and pinning it would compete
     with this app's own scroll-fade top-of-page treatment
     (Journey.svelte's `.scroll-fade`). */
  @media (min-width: 640px) {
    .tab-bar {
      position: static;
    }
  }
</style>
