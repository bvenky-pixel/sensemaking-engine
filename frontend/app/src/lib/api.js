// Thin fetch wrappers over src/api/server.py's real endpoints. No
// client library, no request caching layer -- every call is a direct,
// unadorned reflection of a backend request (see
// frontend-engineering-architecture-v1.md Principle 1: "Reflection of
// Backend Truth, Never a Second Copy").

async function _json(res) {
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Request failed (${res.status}): ${detail}`);
  }
  return res.json();
}

export async function createSession() {
  const res = await fetch('/sessions', { method: 'POST' });
  return _json(res);
}

export async function listSessions(bookmarkedOnly = false) {
  const res = await fetch(bookmarkedOnly ? '/sessions?bookmarked_only=true' : '/sessions');
  return _json(res);
}

export async function setBookmark(sessionId, bookmarked) {
  const res = await fetch(`/sessions/${sessionId}/bookmark`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ bookmarked }),
  });
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
