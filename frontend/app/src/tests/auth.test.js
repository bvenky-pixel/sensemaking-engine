import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as api from '../lib/api.js';
import { authState, checkAuth, consumeMagicLinkFromUrl, sendLoginLink, logout } from '../lib/auth.svelte.js';

// Basic auth (2026-07-18, see frontend/decisions.md "Auth, the
// low-friction way") -- lib/auth.svelte.js is the one shared reactive
// store App.svelte/Settings.svelte/Journey.svelte all read from; tested
// directly here (no component render needed) the same way
// deepeningClarity.test.js/honestFailure.test.js test their own plain
// lib modules.
vi.mock('../lib/api.js', () => ({
  getAuthStatus: vi.fn(),
  requestMagicLink: vi.fn(),
  verifyMagicLink: vi.fn(),
  logout: vi.fn(),
}));

describe('lib/auth.svelte.js', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authState.checked = false;
    authState.authenticated = false;
    authState.email = null;
    window.history.replaceState({}, '', '/');
  });

  it('checkAuth reflects a signed-in status', async () => {
    api.getAuthStatus.mockResolvedValue({ authenticated: true, email: 'person@example.com' });

    await checkAuth();

    expect(authState.checked).toBe(true);
    expect(authState.authenticated).toBe(true);
    expect(authState.email).toBe('person@example.com');
  });

  it('checkAuth reflects a signed-out status', async () => {
    api.getAuthStatus.mockResolvedValue({ authenticated: false, email: null });

    await checkAuth();

    expect(authState.checked).toBe(true);
    expect(authState.authenticated).toBe(false);
  });

  it('consumeMagicLinkFromUrl is a no-op when there is no token', async () => {
    window.history.replaceState({}, '', '/?foo=bar');

    const consumed = await consumeMagicLinkFromUrl();

    expect(consumed).toBe(false);
    expect(api.verifyMagicLink).not.toHaveBeenCalled();
    // Unrelated query params are left alone.
    expect(window.location.search).toBe('?foo=bar');
  });

  it('consumeMagicLinkFromUrl verifies the token, updates state, and strips it from the URL', async () => {
    window.history.replaceState({}, '', '/?token=abc123&foo=bar');
    api.verifyMagicLink.mockResolvedValue({ authenticated: true, email: 'claimed@example.com' });

    const consumed = await consumeMagicLinkFromUrl();

    expect(consumed).toEqual({ authenticated: true, returnSessionId: null });
    expect(api.verifyMagicLink).toHaveBeenCalledWith('abc123');
    expect(authState.checked).toBe(true);
    expect(authState.authenticated).toBe(true);
    expect(authState.email).toBe('claimed@example.com');
    // Token removed, but an unrelated param survives -- a person
    // shouldn't lose whatever else was in the URL.
    expect(window.location.search).toBe('?foo=bar');
  });

  it('consumeMagicLinkFromUrl surfaces return_session_id from the verify response', async () => {
    // Response-limit login UX gap fix (2026-07-18, see
    // frontend/decisions.md "Return to the same Journey after
    // magic-link verify") -- App.svelte reads this straight off the
    // return value to reopen the right Journey.
    window.history.replaceState({}, '', '/?token=abc123');
    api.verifyMagicLink.mockResolvedValue({
      authenticated: true, email: 'claimed@example.com', return_session_id: 's1',
    });

    const consumed = await consumeMagicLinkFromUrl();

    expect(consumed).toEqual({ authenticated: true, returnSessionId: 's1' });
  });

  it('consumeMagicLinkFromUrl strips the token even when it is invalid, without crashing', async () => {
    window.history.replaceState({}, '', '/?token=expired-or-used');
    api.verifyMagicLink.mockRejectedValue(new Error('404'));

    const consumed = await consumeMagicLinkFromUrl();

    expect(consumed).toBe(false);
    expect(window.location.search).toBe('');
  });

  it('sendLoginLink calls requestMagicLink with the given email', async () => {
    api.requestMagicLink.mockResolvedValue({ sent: true });

    await sendLoginLink('me@example.com');

    expect(api.requestMagicLink).toHaveBeenCalledWith('me@example.com', undefined);
  });

  it('sendLoginLink passes a return session id through to requestMagicLink', async () => {
    api.requestMagicLink.mockResolvedValue({ sent: true });

    await sendLoginLink('me@example.com', 's1');

    expect(api.requestMagicLink).toHaveBeenCalledWith('me@example.com', 's1');
  });

  it('logout clears the shared auth state', async () => {
    authState.authenticated = true;
    authState.email = 'person@example.com';
    api.logout.mockResolvedValue(undefined);

    await logout();

    expect(authState.authenticated).toBe(false);
    expect(authState.email).toBeNull();
  });
});
