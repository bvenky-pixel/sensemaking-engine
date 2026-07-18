// Per-mode color coding (2026-07-18, see frontend/decisions.md "Home:
// time period + mode filtering") -- extracted from
// components/ModePicker.svelte, the only place this map existed until
// Home's own mode-filter chips and journey-card accent needed the
// IDENTICAL colors. Same "more than one deliberate identical use
// warrants sharing" threshold already applied to tokens.css's own
// .card/.btn-primary/.link-button recipes.
export const MODE_TINTS = {
  vent: 'var(--accent-2)',
  strategize: 'var(--accent)',
  commit: 'var(--accent-5)',
  explore: 'var(--accent-4)',
  realign: 'var(--accent-3)',
  adaptive: 'var(--accent)',
};

export function tintFor(modeId) {
  return MODE_TINTS[modeId] || 'var(--accent)';
}
