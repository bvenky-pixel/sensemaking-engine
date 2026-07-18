import { describe, it, expect, beforeEach } from 'vitest';
import { authState } from '../lib/auth.svelte.js';
import { loginNudgeState, markJourneyCompleted, consumeCompletionNudge } from '../lib/loginNudge.svelte.js';

// Journey-completion login nudge (2026-07-18, see frontend/decisions.md
// "Two earlier login nudges") -- tested directly here (no component
// render needed), same pattern as auth.svelte.js's own dedicated test
// file, since the interesting behavior (once-ever, no-op while signed
// in) lives entirely in this plain module.
describe('lib/loginNudge.svelte.js', () => {
  beforeEach(() => {
    localStorage.clear();
    loginNudgeState.pending = false;
    loginNudgeState.sessionId = null;
    authState.checked = true;
    authState.authenticated = false;
    authState.email = null;
  });

  it('markJourneyCompleted sets a pending nudge for a signed-out browser', () => {
    markJourneyCompleted('s1');

    expect(loginNudgeState.pending).toBe(true);
    expect(loginNudgeState.sessionId).toBe('s1');
  });

  it('markJourneyCompleted is a no-op while already signed in', () => {
    authState.authenticated = true;

    markJourneyCompleted('s1');

    expect(loginNudgeState.pending).toBe(false);
  });

  it('markJourneyCompleted is a no-op once this browser has ever seen the nudge', () => {
    localStorage.setItem('confidant_completion_nudge_seen', '1');

    markJourneyCompleted('s1');

    expect(loginNudgeState.pending).toBe(false);
  });

  it('consumeCompletionNudge returns the session id and marks the nudge seen', () => {
    markJourneyCompleted('s1');

    const result = consumeCompletionNudge();

    expect(result).toEqual({ sessionId: 's1' });
    expect(localStorage.getItem('confidant_completion_nudge_seen')).toBe('1');
    // Consuming clears the pending flag -- a second read in the same
    // browser session (e.g. a re-render) doesn't show it again.
    expect(consumeCompletionNudge()).toBeNull();
  });

  it('consumeCompletionNudge returns null when there is nothing pending', () => {
    expect(consumeCompletionNudge()).toBeNull();
  });

  it('consumeCompletionNudge returns null if the browser signed in before Home rendered', () => {
    markJourneyCompleted('s1');
    authState.authenticated = true;

    expect(consumeCompletionNudge()).toBeNull();
    // Doesn't burn the "ever seen" flag on a nudge that was never
    // actually shown.
    expect(localStorage.getItem('confidant_completion_nudge_seen')).toBeNull();
  });
});
