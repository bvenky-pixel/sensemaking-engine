<script>
  // Plans tab (2026-07-21, direct founder instruction -- see
  // engine/decisions.md "Tab order: You, Activity, +, Plans, Settings").
  // Placeholder only: nothing in the backend or the rest of the
  // frontend produces a "Plan" yet (backlog #266 scoped the concept --
  // transformation plans -- but design work on it hasn't started).
  // This screen exists solely to claim the tab's spot in the nav and
  // set an honest expectation, per this app's own "no report of what
  // isn't real yet" discipline -- a plain "Coming soon" rather than a
  // populated-looking empty state with fake affordances.
</script>

<div class="plans">
  <p class="display">Plans</p>
  <p class="voice coming-soon">Coming soon.</p>
</div>

<style>
  .display {
    margin: 0 0 var(--space-4);
  }

  .coming-soon {
    color: var(--ink-muted);
  }
</style>
