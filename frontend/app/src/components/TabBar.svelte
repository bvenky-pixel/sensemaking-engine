<script>
  // 5-tab navigation shell (2026-07-21, backlog #261, see
  // information-architecture-v2.md, engine/decisions.md "Frontend IA
  // v2"). Text-only, no icon set -- matches every other control in
  // this app; introducing icons for this one piece of chrome would be
  // a new visual language this codebase has never used anywhere else.
  //
  // Reordered, Home retired as a tab, Plans added (2026-07-21, direct
  // founder instruction, see engine/decisions.md "Tab order: You,
  // Activity, +, Plans, Settings"): You, Activity, [+], Plans,
  // Settings. The center action is no longer purely an action distinct
  // from a "space" -- per the founder's own call, it's now ALSO the
  // default screen (App.svelte opens directly to the same content it
  // navigates to), so it gets the same `active`/`aria-current`
  // treatment as the other four instead of always looking identically
  // "off". Still visually distinct (accent-filled circle, not a plain
  // tab label) since it's still reached differently (a fixed center
  // position, not a left-to-right slot) and still doubles as the
  // fastest way to start a new Journey from anywhere.
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
  // Deliberately NOT rendered while inside a Journey (App.svelte's own
  // choice of when to mount this component) -- Journey already has its
  // own dedicated back navigation, and a persistent tab bar competing
  // with that during a live exchange would cut against "navigation
  // should never interrupt an in-progress moment of thinking"
  // (information-architecture-v2.md's own Navigation Philosophy,
  // carried from v1 unchanged).
  let { active, onNavigate } = $props();
</script>

<nav class="tab-bar" aria-label="Main">
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
    class:active={active === 'activity'}
    aria-current={active === 'activity' ? 'page' : undefined}
    onclick={() => onNavigate('activity')}
  >
    Activity
  </button>
  <button
    type="button"
    class="tab-center"
    class:active={active === 'start'}
    aria-current={active === 'start' ? 'page' : undefined}
    aria-label="Begin something new"
    onclick={() => onNavigate('start')}
  >
    +
  </button>
  <button
    type="button"
    class="tab"
    class:active={active === 'plans'}
    aria-current={active === 'plans' ? 'page' : undefined}
    onclick={() => onNavigate('plans')}
  >
    Plans
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
    transition: transform var(--motion-bouncy), box-shadow var(--motion-quick) ease-out;
  }

  .tab-center:hover {
    transform: scale(1.06);
  }

  /* Same accent color either way (it's already the active color for
     every other tab) -- a visible ring is the only extra cue needed to
     show "you're here" without losing the circle's own distinct shape. */
  .tab-center.active {
    box-shadow: var(--shadow-soft), 0 0 0 2px var(--accent);
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
