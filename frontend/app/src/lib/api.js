// Thin fetch wrappers over src/api/server.py's real endpoints. No
// client library, no request caching layer -- every call is a direct,
// unadorned reflection of a backend request (see
// frontend-engineering-architecture-v1.md Principle 1: "Reflection of
// Backend Truth, Never a Second Copy").

// Basic auth (2026-07-18, see frontend/decisions.md "Auth, the
// low-friction way"): callers that need to tell "hit the response
// limit" or "not logged in" apart from a generic failure (Journey's
// composer, Settings' gate) need the parsed `detail` string the
// backend sends alongside 401s (`"login_required"`/
// `"response_limit_reached"`) -- a plain Error's message string alone
// isn't structured enough to branch on safely.
export class ApiError extends Error {
  constructor(status, detail) {
    super(`Request failed (${status}): ${detail}`);
    this.status = status;
    this.detail = detail;
  }
}

async function _json(res) {
  if (!res.ok) {
    // FastAPI's HTTPException always serializes to `{"detail": "..."}` --
    // a non-JSON error body would only happen from something outside
    // this app entirely (a proxy, a network failure page), in which
    // case a generic detail is the honest answer anyway.
    let detail = `HTTP ${res.status}`;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      // body wasn't JSON -- keep the generic detail above.
    }
    throw new ApiError(res.status, detail);
  }
  return res.json();
}

// `mode` (Counseling modes, see engine/decisions.md): optional --
// omitting it (the default) begins a Journey with no mode, same as
// every Journey created before this feature existed.
export async function createSession(mode = null) {
  const res = await fetch('/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode }),
  });
  return _json(res);
}

export async function listSessions(bookmarkedOnly = false) {
  const res = await fetch(bookmarkedOnly ? '/sessions?bookmarked_only=true' : '/sessions');
  return _json(res);
}

// Counseling modes (see engine/decisions.md, src/orchestrator/modes.py)
// -- backs the mode-select screen shown before a new Journey begins.
// Never hardcoded here: the backend is the single source of truth for
// each mode's label/description, same "Reflection of Backend Truth"
// principle as every other call in this file.
export async function getModes() {
  const res = await fetch('/modes');
  return _json(res);
}

// Irreversible -- no soft-delete/undo exists yet (see
// src/api/server.py::delete_session's own docstring).
export async function deleteSession(sessionId) {
  const res = await fetch(`/sessions/${sessionId}`, { method: 'DELETE' });
  if (!res.ok) {
    throw new Error(`Request failed (${res.status}): ${await res.text()}`);
  }
}

export async function setBookmark(sessionId, bookmarked) {
  const res = await fetch(`/sessions/${sessionId}/bookmark`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ bookmarked }),
  });
  return _json(res);
}

// Journey's own overflow menu (see frontend/decisions.md "Tuck
// destructive/secondary Journey actions behind an overflow menu") --
// unlike Home, Journey never fetches the full session list, so it needs
// a direct way to read a session's current bookmark state.
export async function getBookmark(sessionId) {
  const res = await fetch(`/sessions/${sessionId}/bookmark`);
  return _json(res);
}

export async function getMessages(sessionId) {
  const res = await fetch(`/sessions/${sessionId}/messages`);
  return _json(res);
}

export async function sendMessage(sessionId, content) {
  const res = await fetch(`/sessions/${sessionId}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  });
  return _json(res);
}

// Clarity Brief legitimately 404s until a turn has completed Judgment
// and Planner -- that's not an error state, it's "nothing to
// summarize yet," so this returns null instead of throwing.
export async function getClarityBrief(sessionId) {
  const res = await fetch(`/sessions/${sessionId}/clarity-brief`);
  if (res.status === 404) return null;
  return _json(res);
}

// GET /sessions/{id}/understanding never 404s (unlike getClarityBrief
// above) -- an empty tier1/tier2 list before any turn has completed is
// a valid, correct response, not an error state.
export async function getUnderstanding(sessionId) {
  const res = await fetch(`/sessions/${sessionId}/understanding`);
  return _json(res);
}

// Major update (2026-07-11, see engine/decisions.md): one Server-Sent
// Event per pipeline stage that finishes during this session's next
// sendMessage call (see src/api/server.py's GET /sessions/{id}/stream).
// EventSource is the browser's own SSE client -- it already ignores `:
// keepalive` comment lines per the SSE spec, no parsing needed here for
// those. Returns a plain close function rather than the EventSource
// itself, matching this file's own "thin fetch wrapper" pattern: callers
// (AmbientPresence.svelte) never need the underlying object.
export function openStageStream(sessionId, onStage) {
  const source = new EventSource(`/sessions/${sessionId}/stream`);
  source.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.stage) onStage(data.stage);
    } catch {
      // Malformed/unexpected payload -- never let a stream event break
      // the actual conversation turn, which doesn't depend on this.
    }
  };
  return () => source.close();
}

// Privacy, made real (2026-07-18, see frontend/decisions.md) -- backs
// Settings' Privacy card.
export async function getPrivacySettings() {
  const res = await fetch('/privacy/settings');
  return _json(res);
}

export async function setCrossSessionLearningEnabled(enabled) {
  const res = await fetch('/privacy/settings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ cross_session_learning_enabled: enabled }),
  });
  return _json(res);
}

// Returns a Blob, not JSON -- this is a file download
// (Content-Disposition: attachment on the response), not a typed
// resource a caller reads fields off of.
export async function exportPrivacyData() {
  const res = await fetch('/privacy/export');
  if (!res.ok) {
    throw new Error(`Request failed (${res.status}): ${await res.text()}`);
  }
  return res.blob();
}

// Irreversible -- same "no soft-delete/undo" honesty as deleteSession's
// own docstring, just wider (see src/api/db.py::reset_all_data).
export async function resetAllData() {
  const res = await fetch('/privacy/reset', { method: 'POST' });
  if (!res.ok) {
    throw new Error(`Request failed (${res.status}): ${await res.text()}`);
  }
}

// Basic auth (2026-07-18, see frontend/decisions.md "Auth, the
// low-friction way") -- see lib/auth.svelte.js for the shared reactive
// state these back; this file stays a thin reflection of the backend
// the same as everywhere else.
export async function getAuthStatus() {
  const res = await fetch('/auth/me');
  return _json(res);
}

export async function requestMagicLink(email, returnSessionId) {
  const res = await fetch('/auth/request-link', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, return_session_id: returnSessionId || null }),
  });
  return _json(res);
}

export async function verifyMagicLink(token) {
  const res = await fetch('/auth/verify', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token }),
  });
  return _json(res);
}

export async function logout() {
  const res = await fetch('/auth/logout', { method: 'POST' });
  if (!res.ok) {
    throw new Error(`Request failed (${res.status}): ${await res.text()}`);
  }
}

// POM surfaced to users (2026-07-18, see frontend/decisions.md) --
// backs Settings' "You" section. Requires login, same as the privacy
// endpoints (see src/api/server.py's own docstring on this gate).
// Returns null both when nothing's been computed yet AND (implicitly,
// since this is only ever called from Settings' own authenticated
// branch) never from a logged-out caller.
export async function getPersonalOperatingModel() {
  const res = await fetch('/personal-operating-model');
  return _json(res);
}

// Learning surfaced to users (2026-07-18, see frontend/decisions.md
// "Learning surfaced to users") -- backs Settings' own behavioral-
// patterns card. Requires login, same as /personal-operating-model
// (see engine/decisions.md "Learning made per-account"). Returns an
// empty array both when nothing's been computed yet AND (implicitly,
// since this is only ever called from Settings' own authenticated
// branch) never from a logged-out caller.
export async function getBehavioralPatterns() {
  const res = await fetch('/patterns');
  return _json(res);
}
