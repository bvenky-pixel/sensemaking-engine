// v4's Deepening Clarity moment: a previously open question resolving
// gets a one-line callout the next time the understanding region renders
// -- never a silent update (see frontend/specs/screen-design-v1.md).
// Compared by count, not content, deliberately: this only needs to
// notice something resolved, not explain which one -- the understanding
// region itself already shows the current, accurate list.
//
// Note: `decisions` in the Clarity Brief lists ALL decisions regardless
// of status (build_clarity_brief maps every state.decisions entry, not
// just open ones), so a decision resolving never changes that list's
// length. There is currently no count-based signal for "a decision
// moved forward" -- only remaining_unknowns shrinking is observable this
// way. Revisit if the brief ever exposes decision status.
export function noteDeepeningClarity(previous, next) {
  if (!previous) return '';
  if (next.remaining_unknowns.length < previous.remaining_unknowns.length) {
    return 'Something has become clearer since last time.';
  }
  return '';
}
