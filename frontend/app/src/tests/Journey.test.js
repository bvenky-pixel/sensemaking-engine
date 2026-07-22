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
    openStageStream: vi.fn(),
    deleteSession: vi.fn(),
    getBookmark: vi.fn(),
    setBookmark: vi.fn(),
    getPrivacySettings: vi.fn(),
    submitJourneyReflection: vi.fn(),
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
    api.getBookmark.mockResolvedValue({ bookmarked: false });
    api.getPrivacySettings.mockResolvedValue({
      cross_session_learning_enabled: true,
      reflection_prompt_enabled: false,
    });
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

    // getBookmark resolves after getMessages/getClarityBrief in onMount,
    // so the menu trigger itself (rendered unconditionally,
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

// Journey-close reflection question (2026-07-19, backlog #207) -- opt-in
// via Settings, shown at the "winds down" moment instead of navigating
// home immediately, once a Journey with real content is left.
describe('Journey-close reflection question', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getClarityBrief.mockResolvedValue(null);
    api.getBookmark.mockResolvedValue({ bookmarked: false });
    api.getMessages.mockResolvedValue([{ role: 'user', content: 'I want to move teams.', created_at: '' }]);
    api.openStageStream.mockReturnValue(vi.fn());
    authState.checked = true;
    authState.authenticated = true;
    authState.email = 'person@example.com';
  });

  it('does not show the prompt when reflection_prompt_enabled is off', async () => {
    api.getPrivacySettings.mockResolvedValue({
      cross_session_learning_enabled: true,
      reflection_prompt_enabled: false,
    });
    const onBack = vi.fn();
    const { getByText, queryByText } = render(Journey, { props: { sessionId: 's1', onBack } });

    await waitFor(() => getByText('I want to move teams.'));
    await fireEvent.click(getByText('← Home'));

    await waitFor(() => expect(onBack).toHaveBeenCalled());
    expect(queryByText('Before you go -- anything about this conversation you\'d want to remember or reflect on?')).toBeNull();
  });

  it('shows the prompt and does not navigate home until skipped', async () => {
    api.getPrivacySettings.mockResolvedValue({
      cross_session_learning_enabled: true,
      reflection_prompt_enabled: true,
    });
    const onBack = vi.fn();
    const { getByText } = render(Journey, { props: { sessionId: 's1', onBack } });

    await waitFor(() => getByText('I want to move teams.'));
    await waitFor(() => expect(api.getPrivacySettings).toHaveBeenCalled());
    await fireEvent.click(getByText('← Home'));

    await waitFor(() => {
      expect(getByText('Before you go -- anything about this conversation you\'d want to remember or reflect on?')).toBeTruthy();
    });
    expect(onBack).not.toHaveBeenCalled();

    await fireEvent.click(getByText('Skip'));

    expect(onBack).toHaveBeenCalled();
    expect(api.submitJourneyReflection).not.toHaveBeenCalled();
  });

  it('submits the reflection and navigates home', async () => {
    api.getPrivacySettings.mockResolvedValue({
      cross_session_learning_enabled: true,
      reflection_prompt_enabled: true,
    });
    api.submitJourneyReflection.mockResolvedValue(undefined);
    const onBack = vi.fn();
    const { getByText, getByPlaceholderText } = render(Journey, { props: { sessionId: 's1', onBack } });

    await waitFor(() => getByText('I want to move teams.'));
    // onMount fetches privacy settings AFTER messages/bookmark resolve --
    // wait for that specific call, not just the earlier message render,
    // or handleBack can run against reflectionPromptEnabled's still-false
    // default and skip the prompt entirely.
    await waitFor(() => expect(api.getPrivacySettings).toHaveBeenCalled());
    await fireEvent.click(getByText('← Home'));

    const textarea = await waitFor(() => getByPlaceholderText('Optional -- write as much or as little as you\'d like.'));
    await fireEvent.input(textarea, { target: { value: 'This was a hard conversation to have.' } });
    await fireEvent.click(getByText('Share and leave'));

    await waitFor(() => {
      expect(api.submitJourneyReflection).toHaveBeenCalledWith('s1', 'This was a hard conversation to have.');
      expect(onBack).toHaveBeenCalled();
    });
  });

  it('still navigates home if the reflection submission fails', async () => {
    api.getPrivacySettings.mockResolvedValue({
      cross_session_learning_enabled: true,
      reflection_prompt_enabled: true,
    });
    api.submitJourneyReflection.mockRejectedValue(new Error('network error'));
    const onBack = vi.fn();
    const { getByText, getByPlaceholderText } = render(Journey, { props: { sessionId: 's1', onBack } });

    await waitFor(() => getByText('I want to move teams.'));
    // onMount fetches privacy settings AFTER messages/bookmark resolve --
    // wait for that specific call, not just the earlier message render,
    // or handleBack can run against reflectionPromptEnabled's still-false
    // default and skip the prompt entirely.
    await waitFor(() => expect(api.getPrivacySettings).toHaveBeenCalled());
    await fireEvent.click(getByText('← Home'));

    const textarea = await waitFor(() => getByPlaceholderText('Optional -- write as much or as little as you\'d like.'));
    await fireEvent.input(textarea, { target: { value: 'Anything.' } });
    await fireEvent.click(getByText('Share and leave'));

    await waitFor(() => expect(onBack).toHaveBeenCalled());
  });
});

describe('Journey: only populated after a real message is shared', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getClarityBrief.mockResolvedValue(null);
    api.getBookmark.mockResolvedValue({ bookmarked: false });
    api.getPrivacySettings.mockResolvedValue({
      cross_session_learning_enabled: true,
      reflection_prompt_enabled: false,
    });
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
    api.getBookmark.mockResolvedValue({ bookmarked: false });
    api.getPrivacySettings.mockResolvedValue({
      cross_session_learning_enabled: true,
      reflection_prompt_enabled: false,
    });
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
    api.getBookmark.mockResolvedValue({ bookmarked: false });
    api.getPrivacySettings.mockResolvedValue({
      cross_session_learning_enabled: true,
      reflection_prompt_enabled: false,
    });
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

    // returnSessionId (2026-07-18, see frontend/decisions.md "Return to
    // the same Journey after magic-link verify") -- this gate lives
    // inside a specific Journey, so it carries that Journey's own id.
    await waitFor(() => expect(api.requestMagicLink).toHaveBeenCalledWith('me@example.com', 's1'));
    expect(api.setBookmark).not.toHaveBeenCalled();
    expect(api.deleteSession).not.toHaveBeenCalled();
  });
});

// Proximity login nudge (2026-07-18, see frontend/decisions.md "Two
// earlier login nudges") -- a soft, dismissible note once an anonymous
// Journey gets close to the hard response-limit wall, ahead of actually
// hitting it.
function userMessages(count) {
  return Array.from({ length: count }, (_, i) => ({
    role: 'user', content: `message ${i + 1}`, created_at: '',
  }));
}

describe('Journey proximity login nudge', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getClarityBrief.mockResolvedValue(null);
    api.getBookmark.mockResolvedValue({ bookmarked: false });
    api.getPrivacySettings.mockResolvedValue({
      cross_session_learning_enabled: true,
      reflection_prompt_enabled: false,
    });
    api.openStageStream.mockReturnValue(vi.fn());
  });

  it('does not show below the threshold', async () => {
    authState.checked = true;
    authState.authenticated = false;
    authState.email = null;
    api.getMessages.mockResolvedValue(userMessages(6));

    const { queryByText } = render(Journey, { props: { sessionId: 's1', onBack: vi.fn() } });

    await waitFor(() => expect(api.getMessages).toHaveBeenCalled());
    expect(queryByText(/Free replies are limited/)).toBeNull();
  });

  it('shows once the threshold is reached, signed out', async () => {
    authState.checked = true;
    authState.authenticated = false;
    authState.email = null;
    api.getMessages.mockResolvedValue(userMessages(7));

    const { getByText } = render(Journey, { props: { sessionId: 's1', onBack: vi.fn() } });

    await waitFor(() => getByText(/Free replies are limited/));
  });

  it('never shows when signed in, regardless of message count', async () => {
    authState.checked = true;
    authState.authenticated = true;
    authState.email = 'person@example.com';
    api.getMessages.mockResolvedValue(userMessages(9));

    const { queryByText } = render(Journey, { props: { sessionId: 's1', onBack: vi.fn() } });

    await waitFor(() => expect(api.getMessages).toHaveBeenCalled());
    expect(queryByText(/Free replies are limited/)).toBeNull();
  });

  it('dismissing hides it without calling the API', async () => {
    authState.checked = true;
    authState.authenticated = false;
    authState.email = null;
    api.getMessages.mockResolvedValue(userMessages(7));

    const { getByText, getByLabelText, queryByText } = render(Journey, {
      props: { sessionId: 's1', onBack: vi.fn() },
    });

    await waitFor(() => getByText(/Free replies are limited/));
    await fireEvent.click(getByLabelText('Dismiss'));

    expect(queryByText(/Free replies are limited/)).toBeNull();
    expect(api.requestMagicLink).not.toHaveBeenCalled();
  });

  it('tapping Sign in reveals the login gate, carrying this Journey\'s id', async () => {
    authState.checked = true;
    authState.authenticated = false;
    authState.email = null;
    api.getMessages.mockResolvedValue(userMessages(7));
    api.requestMagicLink.mockResolvedValue({ sent: true });

    const { getByText, getByPlaceholderText } = render(Journey, {
      props: { sessionId: 's1', onBack: vi.fn() },
    });

    await waitFor(() => getByText(/Free replies are limited/));
    await fireEvent.click(getByText('Sign in'));
    await fireEvent.input(await waitFor(() => getByPlaceholderText('you@example.com')), {
      target: { value: 'me@example.com' },
    });
    await fireEvent.click(getByText('Send me a login link'));

    await waitFor(() => expect(api.requestMagicLink).toHaveBeenCalledWith('me@example.com', 's1'));
  });
});

// Composer adjacent to the transcript, Understanding collapsed by
// default (2026-07-22, direct founder feedback, screen overhaul round)
// -- this REVERSES backlog #236's earlier "Clarity Brief during the
// wait" placement (Understanding right after the orb, ahead of the
// Composer): the founder's direct complaint was that the brief had
// grown long/intimidating after a few rounds of conversation, and
// having to scroll past it just to reply felt disorienting. jsdom
// doesn't do real layout, so this can't check pixel position (that's
// what a live Playwright verification round covers) -- it checks DOM
// SOURCE order instead, via compareDocumentPosition, which is what
// actually determines visual order for this normal-flow, non-
// absolutely-positioned markup.
describe('Journey: Composer adjacent to transcript, Understanding collapsed by default', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getMessages.mockResolvedValue([{ role: 'user', content: 'I keep putting off a hard conversation.', created_at: '' }]);
    api.getClarityBrief.mockResolvedValue({
      situation: 'Weighing whether to raise a workload concern with a manager.',
      current_direction: 'Leaning toward having the conversation soon.',
      key_insights: ['The delay itself is adding stress.'],
      remaining_unknowns: [],
      decisions: [],
      secondary_issues: [],
      stagnation_notes: [],
    });
    api.getBookmark.mockResolvedValue({ bookmarked: false });
    api.getPrivacySettings.mockResolvedValue({
      cross_session_learning_enabled: true,
      reflection_prompt_enabled: false,
    });
    api.openStageStream.mockReturnValue(vi.fn());
    authState.checked = true;
    authState.authenticated = true;
    authState.email = 'person@example.com';
  });

  it('renders the Composer before the Understanding toggle, with brief content hidden until expanded', async () => {
    const { getByText, getByPlaceholderText, queryByText, container } = render(Journey, {
      props: { sessionId: 's1', onBack: vi.fn() },
    });

    await waitFor(() => getByText('I keep putting off a hard conversation.'));

    // Collapsed by default -- the brief's own content isn't in the DOM yet.
    expect(queryByText(/The delay itself is adding stress/)).toBeNull();

    const toggle = await waitFor(() => getByText('Show what we understand so far'));
    const composerTextarea = container.querySelector('textarea');
    expect(composerTextarea).toBeTruthy();

    // DOCUMENT_POSITION_FOLLOWING on the toggle (relative to the
    // composer textarea) means the toggle comes AFTER the composer in
    // source order -- i.e. Composer, then Understanding, reversed from
    // backlog #236's earlier ordering.
    const position = composerTextarea.compareDocumentPosition(toggle);
    expect(position & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

    await fireEvent.click(toggle);

    // key_insights ("What matters here"), not situation ("Where things
    // stand" -- removed entirely, 2026-07-22, direct founder redirect).
    await waitFor(() => getByText(/The delay itself is adding stress/));
    expect(getByText('Hide what we understand so far')).toBeTruthy();
  });
});

// Streamed Response text (2026-07-22, backlog #233, see
// engine/decisions.md "Stream Response text token-by-token") --
// openStageStream's third argument (onToken) is captured here and
// invoked manually, the same way a real GET /stream token event would
// eventually reach it, without needing a real EventSource/backend.
describe('Journey: streamed response text preview', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getMessages.mockResolvedValue([]);
    api.getClarityBrief.mockResolvedValue(null);
    api.getBookmark.mockResolvedValue({ bookmarked: false });
    api.getPrivacySettings.mockResolvedValue({
      cross_session_learning_enabled: true,
      reflection_prompt_enabled: false,
    });
    authState.checked = true;
    authState.authenticated = true;
    authState.email = 'person@example.com';
  });

  it('shows streamed response_text fragments growing in the transcript while still sending', async () => {
    let capturedOnToken;
    api.openStageStream.mockImplementation((sessionId, onStage, onToken) => {
      capturedOnToken = onToken;
      return vi.fn();
    });
    // Never resolves within the test -- holds `sending` at true so the
    // in-flight streaming preview is what gets asserted, not the
    // settled-afterward real message.
    api.sendMessage.mockReturnValue(new Promise(() => {}));

    const { getByPlaceholderText, getByText, queryByText } = render(Journey, {
      props: { sessionId: 's1', onBack: vi.fn() },
    });

    const composer = await waitFor(() => getByPlaceholderText("What's on your mind?"));
    await fireEvent.input(composer, { target: { value: 'I want to talk about work.' } });
    await fireEvent.click(getByText('Share this'));

    await waitFor(() => expect(api.sendMessage).toHaveBeenCalled());
    expect(typeof capturedOnToken).toBe('function');

    // Nothing streamed yet -- the provisional bubble only appears once
    // there's real text to show (see Journey.svelte's own displayMessages).
    expect(queryByText(/It sounds like/)).toBeNull();

    capturedOnToken('It sounds ');
    await waitFor(() => getByText('It sounds', { exact: false }));

    capturedOnToken('like a lot.');
    await waitFor(() => getByText('It sounds like a lot.'));
  });

  it('replaces the streaming preview with the real message once the response resolves, without a duplicate', async () => {
    let capturedOnToken;
    let resolveSend;
    api.openStageStream.mockImplementation((sessionId, onStage, onToken) => {
      capturedOnToken = onToken;
      return vi.fn();
    });
    api.sendMessage.mockReturnValue(
      new Promise((resolve) => {
        resolveSend = resolve;
      }),
    );

    const { getByPlaceholderText, getByText, queryAllByText } = render(Journey, {
      props: { sessionId: 's1', onBack: vi.fn() },
    });

    const composer = await waitFor(() => getByPlaceholderText("What's on your mind?"));
    await fireEvent.input(composer, { target: { value: 'I want to talk about work.' } });
    await fireEvent.click(getByText('Share this'));
    await waitFor(() => expect(api.sendMessage).toHaveBeenCalled());

    capturedOnToken('Partial draft');
    await waitFor(() => getByText('Partial draft', { exact: false }));

    resolveSend({
      response_text: 'The real, final response text.',
      confidence: 0.7,
      options: [],
      failed_stage: null,
      error: null,
    });

    await waitFor(() => getByText('The real, final response text.'));
    // The provisional "Partial draft" bubble must be gone, not left
    // behind alongside the real message.
    expect(queryAllByText(/Partial draft/, { exact: false }).length).toBe(0);
  });
});
