import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, fireEvent, waitFor } from '@testing-library/svelte';
import Journey from '../screens/Journey.svelte';
import * as api from '../lib/api.js';
import { authState } from '../lib/auth.svelte.js';

// Tuck destructive/secondary Journey actions behind an overflow menu
// (2026-07-18, see frontend/decisions.md): delete moved to Journey.svelte
// last round, now tucked behind a "..." near the back button instead of
// standing visible at the bottom of every screen -- direct founder worry
// that a permanent delete link was "too much... I risk losing data every
// time." Bookmark lives in the same menu now too. Mocking lib/api.js
// (rather than fetch) matches every other screen test's own boundary.
// Basic auth (2026-07-18, see frontend/decisions.md "Auth, the
// low-friction way"): `ApiError` is passed through from the REAL
// module (via importOriginal), not stubbed with vi.fn() like
// everything else here -- Journey.svelte's own catch block does
// `err instanceof ApiError`, which needs a real class to check against,
// not a mock function standing in for one.
vi.mock('../lib/api.js', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    getMessages: vi.fn(),
    sendMessage: vi.fn(),
    getClarityBrief: vi.fn(),
    getUnderstanding: vi.fn(),
    openStageStream: vi.fn(),
    deleteSession: vi.fn(),
    getBookmark: vi.fn(),
    setBookmark: vi.fn(),
    ApiError: actual.ApiError,
    getAuthStatus: vi.fn(),
    requestMagicLink: vi.fn(),
    verifyMagicLink: vi.fn(),
    logout: vi.fn(),
  };
});

describe('Journey overflow menu', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getMessages.mockResolvedValue([]);
    api.getClarityBrief.mockResolvedValue(null);
    api.getUnderstanding.mockResolvedValue({ tier1: [], tier2: [] });
    api.getBookmark.mockResolvedValue({ bookmarked: false });
    api.openStageStream.mockReturnValue(vi.fn());
    // Bookmark/delete require login (2026-07-18, see
    // frontend/decisions.md) -- every test below exercises the
    // signed-in menu; the new describe block further down covers the
    // signed-out login prompt itself.
    authState.checked = true;
    authState.authenticated = true;
    authState.email = 'person@example.com';
  });

  it('does not show any actions until the menu is opened', async () => {
    const { getByLabelText, queryByText } = render(Journey, { props: { sessionId: 's1', onBack: vi.fn() } });

    await waitFor(() => getByLabelText('Journey options'));

    expect(queryByText('Delete this Journey')).toBeNull();
    expect(queryByText('☆ Bookmark this Journey')).toBeNull();
  });

  it('opens the menu on click, showing bookmark and delete', async () => {
    const { getByLabelText, getByText } = render(Journey, { props: { sessionId: 's1', onBack: vi.fn() } });

    const trigger = await waitFor(() => getByLabelText('Journey options'));
    await fireEvent.click(trigger);

    expect(getByText('☆ Bookmark this Journey')).toBeTruthy();
    expect(getByText('Delete this Journey')).toBeTruthy();
  });

  it('toggles the bookmark and closes the menu', async () => {
    api.setBookmark.mockResolvedValue({ bookmarked: true });
    const { getByLabelText, getByText, queryByText } = render(Journey, { props: { sessionId: 's1', onBack: vi.fn() } });

    const trigger = await waitFor(() => getByLabelText('Journey options'));
    await fireEvent.click(trigger);
    await fireEvent.click(getByText('☆ Bookmark this Journey'));

    await waitFor(() => {
      expect(api.setBookmark).toHaveBeenCalledWith('s1', true);
      // Menu closes after a bookmark toggle.
      expect(queryByText('Delete this Journey')).toBeNull();
    });
  });

  it('reflects an already-bookmarked Journey when the menu opens', async () => {
    api.getBookmark.mockResolvedValue({ bookmarked: true });
    const { getByLabelText, getByText } = render(Journey, { props: { sessionId: 's1', onBack: vi.fn() } });

    // getBookmark resolves after getMessages/getClarityBrief/getUnderstanding
    // in onMount, so the menu trigger itself (rendered unconditionally,
    // not gated behind `loaded`) can exist in the DOM before `bookmarked`
    // has actually loaded -- wait for the real signal, not just the
    // trigger's presence.
    await waitFor(() => expect(api.getBookmark).toHaveBeenCalled());
    const trigger = getByLabelText('Journey options');
    await fireEvent.click(trigger);

    await waitFor(() => {
      expect(getByText('★ Remove bookmark')).toBeTruthy();
    });
  });

  it('asks for confirmation before deleting, and does nothing on Cancel', async () => {
    const onBack = vi.fn();
    const { getByLabelText, getByText, queryByText } = render(Journey, { props: { sessionId: 's1', onBack } });

    const trigger = await waitFor(() => getByLabelText('Journey options'));
    await fireEvent.click(trigger);
    await fireEvent.click(getByText('Delete this Journey'));

    expect(getByText("Delete this Journey for good? This can't be undone.")).toBeTruthy();
    expect(api.deleteSession).not.toHaveBeenCalled();

    await fireEvent.click(getByText('Cancel'));

    expect(queryByText("Delete this Journey for good? This can't be undone.")).toBeNull();
    expect(api.deleteSession).not.toHaveBeenCalled();
    expect(onBack).not.toHaveBeenCalled();
  });

  it('deletes the Journey and navigates back to Home after confirming', async () => {
    api.deleteSession.mockResolvedValue(undefined);
    const onBack = vi.fn();
    const { getByLabelText, getByText } = render(Journey, { props: { sessionId: 's1', onBack } });

    const trigger = await waitFor(() => getByLabelText('Journey options'));
    await fireEvent.click(trigger);
    await fireEvent.click(getByText('Delete this Journey'));
    await fireEvent.click(getByText('Yes, delete it'));

    await waitFor(() => {
      expect(api.deleteSession).toHaveBeenCalledWith('s1');
      expect(onBack).toHaveBeenCalled();
    });
  });

  it('closes the menu on an outside click', async () => {
    const { getByLabelText, getByText, queryByText } = render(Journey, { props: { sessionId: 's1', onBack: vi.fn() } });

    const trigger = await waitFor(() => getByLabelText('Journey options'));
    await fireEvent.click(trigger);
    expect(getByText('Delete this Journey')).toBeTruthy();

    await fireEvent.click(document.body);

    await waitFor(() => {
      expect(queryByText('Delete this Journey')).toBeNull();
    });
  });
});

describe('Journey: only populated after a real message is shared', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getClarityBrief.mockResolvedValue(null);
    api.getUnderstanding.mockResolvedValue({ tier1: [], tier2: [] });
    api.getBookmark.mockResolvedValue({ bookmarked: false });
  });

  it('deletes an empty Journey when backing out without sending anything', async () => {
    api.getMessages.mockResolvedValue([]);
    api.deleteSession.mockResolvedValue(undefined);
    const onBack = vi.fn();
    const { getByText } = render(Journey, { props: { sessionId: 's1', onBack } });

    // Waits for the real "messages have loaded and there are none" signal
    // (not just the back button's own presence, which renders immediately) --
    // handleBack only auto-deletes once `loaded` is true, precisely to avoid
    // deleting a real Journey whose history just hasn't arrived yet.
    await waitFor(() => expect(api.getMessages).toHaveBeenCalled());
    await fireEvent.click(getByText('← Home'));

    await waitFor(() => {
      expect(api.deleteSession).toHaveBeenCalledWith('s1');
      expect(onBack).toHaveBeenCalled();
    });
  });

  it('does not delete a Journey that already has messages when backing out', async () => {
    api.getMessages.mockResolvedValue([{ role: 'user', content: 'I want to move teams.', created_at: '' }]);
    const onBack = vi.fn();
    const { getByText } = render(Journey, { props: { sessionId: 's1', onBack } });

    await waitFor(() => getByText('I want to move teams.'));
    await fireEvent.click(getByText('← Home'));

    await waitFor(() => expect(onBack).toHaveBeenCalled());
    expect(api.deleteSession).not.toHaveBeenCalled();
  });
});

// Basic auth (2026-07-18, see frontend/decisions.md "Auth, the
// low-friction way"): ANONYMOUS_MESSAGE_LIMIT's frontend half --
// src/api/server.py's send_message rejects with
// `ApiError(401, "response_limit_reached")` once an anonymous
// conversation's cap is hit.
describe('Journey: response limit reached', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getMessages.mockResolvedValue([{ role: 'user', content: 'Already said something.', created_at: '' }]);
    api.getClarityBrief.mockResolvedValue(null);
    api.getUnderstanding.mockResolvedValue({ tier1: [], tier2: [] });
    api.getBookmark.mockResolvedValue({ bookmarked: false });
    api.openStageStream.mockReturnValue(vi.fn());
  });

  it('shows a login prompt instead of the composer, and rolls back the unsent message', async () => {
    api.sendMessage.mockRejectedValue(new api.ApiError(401, 'response_limit_reached'));
    const { getByPlaceholderText, getByText, queryByText } = render(Journey, {
      props: { sessionId: 's1', onBack: vi.fn() },
    });

    await waitFor(() => getByText('Already said something.'));
    const textarea = getByPlaceholderText("What's on your mind?");
    await fireEvent.input(textarea, { target: { value: 'One more thing.' } });
    await fireEvent.click(getByText('Share this'));

    await waitFor(() => {
      expect(getByText(/reached the free limit/)).toBeTruthy();
    });
    // The optimistically-added message was never actually recorded --
    // the transcript shouldn't claim otherwise.
    expect(queryByText('One more thing.')).toBeNull();
    expect(queryByText('Share this')).toBeNull();
  });

  it('shows a generic failure message (not the login gate) for an unrelated error', async () => {
    api.sendMessage.mockRejectedValue(new Error('network exploded'));
    const { getByPlaceholderText, getByText, queryByText } = render(Journey, {
      props: { sessionId: 's1', onBack: vi.fn() },
    });

    await waitFor(() => getByText('Already said something.'));
    const textarea = getByPlaceholderText("What's on your mind?");
    await fireEvent.input(textarea, { target: { value: 'One more thing.' } });
    await fireEvent.click(getByText('Share this'));

    await waitFor(() => {
      expect(getByText("I couldn't reach Confidant just now. Please try again in a moment.")).toBeTruthy();
    });
    expect(queryByText(/reached the free limit/)).toBeNull();
    // Unlike the limit case, a generic failure keeps the composer and
    // the message the person actually typed.
    expect(getByText('One more thing.')).toBeTruthy();
    expect(getByText('Share this')).toBeTruthy();
  });
});

// Auth, the low-friction way (2026-07-18, see frontend/decisions.md):
// direct founder follow-up -- bookmark and delete are login-required
// actions too, not just Settings/Privacy and the response cap.
describe('Journey overflow menu: signed out', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getMessages.mockResolvedValue([]);
    api.getClarityBrief.mockResolvedValue(null);
    api.getUnderstanding.mockResolvedValue({ tier1: [], tier2: [] });
    api.getBookmark.mockResolvedValue({ bookmarked: false });
    api.openStageStream.mockReturnValue(vi.fn());
    authState.checked = true;
    authState.authenticated = false;
    authState.email = null;
  });

  it('shows a login prompt instead of Bookmark/Delete', async () => {
    const { getByLabelText, getByText, queryByText } = render(Journey, {
      props: { sessionId: 's1', onBack: vi.fn() },
    });

    const trigger = await waitFor(() => getByLabelText('Journey options'));
    await fireEvent.click(trigger);

    expect(getByText('Log in to bookmark or delete Journeys.')).toBeTruthy();
    expect(queryByText('Delete this Journey')).toBeNull();
    expect(queryByText('☆ Bookmark this Journey')).toBeNull();
  });

  it('opens the shared login gate below the header when tapped, and never calls the API', async () => {
    const { getByLabelText, getByText, getByPlaceholderText } = render(Journey, {
      props: { sessionId: 's1', onBack: vi.fn() },
    });

    await fireEvent.click(await waitFor(() => getByLabelText('Journey options')));
    await fireEvent.click(getByText('Log in'));

    await waitFor(() => getByText('Log in to bookmark or delete this Journey.'));
    await fireEvent.input(getByPlaceholderText('you@example.com'), { target: { value: 'me@example.com' } });
    await fireEvent.click(getByText('Send me a login link'));

    await waitFor(() => expect(api.requestMagicLink).toHaveBeenCalledWith('me@example.com'));
    expect(api.setBookmark).not.toHaveBeenCalled();
    expect(api.deleteSession).not.toHaveBeenCalled();
  });
});
