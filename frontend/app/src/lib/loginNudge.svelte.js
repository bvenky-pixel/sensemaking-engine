// Journey-completion login nudge (2026-07-18, see frontend/decisions.md
// "Two earlier login nudges") -- tied to a real moment of completion
// (leaving a Journey that actually has content), never a recurring
// gate. Shown at most ONCE per browser, ever (localStorage-backed) --
// a person who dismisses or ignores it isn't asked again on every
// subsequent Journey. Same module-level `$state` pattern as
// auth.svelte.js (see that file's own comment for why): Journey.svelte
// (where a Journey completes) and Home.svelte (where the nudge is
// actually shown) need to share one signal without a router or context
// provider.
import { authState } from './auth.svelte.js';

const SEEN_KEY = 'confidant_completion_nudge_seen';

export const loginNudgeState = $state({ pending: false, sessionId: null });

// Called by Journey.svelte's handleBack when a real (non-empty)
// Journey is left while signed out. A no-op once already signed in, or
// once this browser has ever seen the nudge before -- the check
// happens here (at the moment a Journey completes) rather than only in
// consumeCompletionNudge, so a person who completes several Journeys
// before ever landing back on Home still only ever gets flagged once.
export function markJourneyCompleted(sessionId) {
  if (authState.authenticated) return;
  if (localStorage.getItem(SEEN_KEY)) return;
  loginNudgeState.pending = true;
  loginNudgeState.sessionId = sessionId;
}

// Called once by Home on mount -- returns `{ sessionId }` the one time
// there's a real, still-relevant pending completion to show, or `null`
// otherwise. Marks the nudge "seen" immediately (not on dismiss), so a
// page reload between leaving the Journey and Home actually rendering
// can't show it twice.
export function consumeCompletionNudge() {
  const shouldShow = loginNudgeState.pending && !authState.authenticated;
  const sessionId = loginNudgeState.sessionId;
  loginNudgeState.pending = false;
  loginNudgeState.sessionId = null;
  if (!shouldShow) return null;
  localStorage.setItem(SEEN_KEY, '1');
  return { sessionId };
}
