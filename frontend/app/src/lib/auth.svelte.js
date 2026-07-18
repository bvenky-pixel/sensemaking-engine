// Basic auth (2026-07-18, see frontend/decisions.md "Auth, the
// low-friction way") -- one shared, module-level reactive store rather
// than a prop threaded through App.svelte -> Settings.svelte/Journey.svelte.
// Both of those screens (and App.svelte itself, for the magic-link
// token-in-URL exchange on boot) need to read AND react to the same
// sign-in state without a router or a context provider -- this app has
// neither (see App.svelte's own "no router library" comment) -- so a
// `.svelte.js` module's own top-level `$state` is the natural fit:
// Svelte 5 runes work outside `.svelte` files too, and every importer
// of this module shares the exact same reactive object.
import { getAuthStatus, requestMagicLink, verifyMagicLink, logout as apiLogout } from './api.js';

export const authState = $state({
  // `checked` distinguishes "we don't know yet" (page just loaded) from
  // "we checked and you're logged out" -- Settings/Journey must not
  // flash the logged-out gate for a split second on every load before
  // GET /auth/me resolves.
  checked: false,
  authenticated: false,
  email: null,
});

export async function checkAuth() {
  const status = await getAuthStatus();
  authState.checked = true;
  authState.authenticated = status.authenticated;
  authState.email = status.email;
}

// Magic-link token in the URL (e.g. `?token=...`, from the emailed
// link -- see src/api/server.py's /auth/request-link) is exchanged for
// a real session cookie here, then stripped from the address bar so a
// page refresh/share never re-sends an already-used token. Called once
// from App.svelte's own onMount, before checkAuth -- verifying already
// tells us the resulting auth state directly, so a second /auth/me
// round trip right after would be redundant.
//
// Returns `false` when there was no token to consume (App.svelte falls
// back to its own checkAuth in that case); otherwise
// `{ authenticated, returnSessionId }` -- `returnSessionId` is non-null
// only when the clicked link should reopen a specific Journey (see
// "Return to the same Journey after magic-link verify" above).
export async function consumeMagicLinkFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const token = params.get('token');
  if (!token) return false;

  params.delete('token');
  const query = params.toString();
  window.history.replaceState({}, '', window.location.pathname + (query ? `?${query}` : ''));

  try {
    const status = await verifyMagicLink(token);
    authState.checked = true;
    authState.authenticated = status.authenticated;
    authState.email = status.email;
    // Response-limit login UX gap fix (2026-07-18, see
    // frontend/decisions.md "Return to the same Journey after
    // magic-link verify") -- `status.return_session_id` is the
    // server's own authoritative answer (only ever set when the
    // clicked link actually carried one AND it survived the
    // ownership check post-claim), never read from the URL itself.
    return { authenticated: status.authenticated, returnSessionId: status.return_session_id || null };
  } catch {
    // An invalid/expired/already-used token (see db.consume_magic_link's
    // own docstring for why those three collapse into one 404) -- the
    // person just sees the logged-out state they'd have seen anyway,
    // not a crash.
    return false;
  }
}

export async function sendLoginLink(email, returnSessionId) {
  await requestMagicLink(email, returnSessionId);
}

export async function logout() {
  await apiLogout();
  authState.authenticated = false;
  authState.email = null;
}
