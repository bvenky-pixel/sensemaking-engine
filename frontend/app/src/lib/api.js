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
