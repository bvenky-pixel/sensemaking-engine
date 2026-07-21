import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, fireEvent, waitFor } from '@testing-library/svelte';
import Activity from '../screens/Activity.svelte';
import * as api from '../lib/api.js';
import { authState } from '../lib/auth.svelte.js';
import { loginNudgeState, markJourneyCompleted } from '../lib/loginNudge.svelte.js';

// Activity tab (2026-07-21, backlog #262, see
// information-architecture-v2.md, engine/decisions.md "Frontend IA
// v2") -- Home's own journey-list/filtering/bookmark/completion-nudge
// tests, relocated here wholesale since that's exactly what happened
// to the markup they cover. Mocking lib/api.js (rather than fetch)
// matches every other screen test's own boundary.
vi.mock('../lib/api.js', () => ({
  listSessions: vi.fn(),
  setBookmark: vi.fn(),
  getModes: vi.fn(),
  getAuthStatus: vi.fn(),
  requestMagicLink: vi.fn(),
  verifyMagicLink: vi.fn(),
  logout: vi.fn(),
}));

const MODES = [
  { id: 'vent', label: 'Vent', description: 'Just get this out.' },
  { id: 'strategize', label: 'Strategize', description: 'Lay out real choices.' },
];

// A fixed "now" (a Wednesday, comfortably mid-week/mid-month/mid-year)
// so period boundaries are unambiguous regardless of what day this
// suite actually runs on.
const NOW = new Date('2026-07-15T12:00:00Z');

const SESSIONS = [
  { id: 's-week', preview_text: 'This week journey', updated_at: '2026-07-15T10:00:00Z', bookmarked: false, has_stagnation_signal: false, mode: 'vent' },
  { id: 's-month', preview_text: 'This month journey', updated_at: '2026-07-05T10:00:00Z', bookmarked: false, has_stagnation_signal: false, mode: 'strategize' },
  { id: 's-year', preview_text: 'This year journey', updated_at: '2026-03-01T10:00:00Z', bookmarked: false, has_stagnation_signal: false, mode: 'vent' },
  { id: 's-old', preview_text: 'Old journey', updated_at: '2024-01-01T10:00:00Z', bookmarked: false, has_stagnation_signal: false, mode: null },
];

describe('Activity: time period + mode filtering', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
    vi.clearAllMocks();
    api.getModes.mockResolvedValue(MODES);
    authState.checked = true;
    authState.authenticated = false;
    authState.email = null;
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('shows every Journey under All time, the default', async () => {
    api.listSessions.mockResolvedValue(SESSIONS);
    const { getByText } = render(Activity, { props: { onOpen: vi.fn() } });

    await waitFor(() => {
      expect(getByText('This week journey')).toBeTruthy();
      expect(getByText('This month journey')).toBeTruthy();
      expect(getByText('This year journey')).toBeTruthy();
      expect(getByText('Old journey')).toBeTruthy();
    });
  });

  it('shows a count next to each time period', async () => {
    api.listSessions.mockResolvedValue(SESSIONS);
    const { getByRole } = render(Activity, { props: { onOpen: vi.fn() } });

    await waitFor(() => {
      expect(getByRole('button', { name: 'This week filter' }).textContent).toContain('1');
      expect(getByRole('button', { name: 'This month filter' }).textContent).toContain('2');
      expect(getByRole('button', { name: 'This year filter' }).textContent).toContain('3');
      expect(getByRole('button', { name: 'All time filter' }).textContent).toContain('4');
    });
  });

  it('filters to only this week when This week is selected', async () => {
    api.listSessions.mockResolvedValue(SESSIONS);
    const { getByRole, getByText, queryByText } = render(Activity, { props: { onOpen: vi.fn() } });

    await waitFor(() => getByText('Old journey'));
    await fireEvent.click(getByRole('button', { name: 'This week filter' }));

    await waitFor(() => {
      expect(getByText('This week journey')).toBeTruthy();
      expect(queryByText('This month journey')).toBeNull();
      expect(queryByText('This year journey')).toBeNull();
      expect(queryByText('Old journey')).toBeNull();
    });
  });

  it('shows a mode filter chip row scoped to modes present in the selected period, and filters on click', async () => {
    api.listSessions.mockResolvedValue(SESSIONS);
    const { getByRole, getByText, queryByText } = render(Activity, { props: { onOpen: vi.fn() } });

    await waitFor(() => getByText('Old journey'));
    await fireEvent.click(getByRole('button', { name: 'This year filter' }));
    await waitFor(() => {
      expect(getByText('Vent')).toBeTruthy();
      expect(getByText('Strategize')).toBeTruthy();
    });

    await fireEvent.click(getByText('Strategize'));

    await waitFor(() => {
      expect(getByText('This month journey')).toBeTruthy();
      expect(queryByText('This week journey')).toBeNull();
      expect(queryByText('This year journey')).toBeNull();
    });
  });

  it('resets the mode filter when the time period changes', async () => {
    api.listSessions.mockResolvedValue(SESSIONS);
    const { getByRole, getByText, queryByText } = render(Activity, { props: { onOpen: vi.fn() } });

    await waitFor(() => getByText('Old journey'));
    await fireEvent.click(getByRole('button', { name: 'This year filter' }));
    await waitFor(() => getByText('Strategize'));
    await fireEvent.click(getByText('Strategize'));
    await waitFor(() => expect(queryByText('This week journey')).toBeNull());

    await fireEvent.click(getByRole('button', { name: 'This week filter' }));

    await waitFor(() => {
      expect(getByText('This week journey')).toBeTruthy();
    });
  });

  it('shows a contextual empty message when the selected period has no Journeys', async () => {
    api.listSessions.mockResolvedValue([SESSIONS[3]]);
    const { getByRole, getByText } = render(Activity, { props: { onOpen: vi.fn() } });

    await waitFor(() => getByText('Old journey'));
    await fireEvent.click(getByRole('button', { name: 'This week filter' }));

    await waitFor(() => {
      expect(getByText('No Journeys in this time period.')).toBeTruthy();
    });
  });

  it('shows a distinct empty message when there are no Journeys at all', async () => {
    api.listSessions.mockResolvedValue([]);
    const { getByText } = render(Activity, { props: { onOpen: vi.fn() } });

    await waitFor(() => {
      expect(getByText(/Nothing here yet/)).toBeTruthy();
    });
  });

  it('gives a Journey with a mode a colored left edge, and leaves a mode-less one plain', async () => {
    api.listSessions.mockResolvedValue(SESSIONS);
    const { getByText } = render(Activity, { props: { onOpen: vi.fn() } });

    await waitFor(() => getByText('Old journey'));

    const modedCard = getByText('This week journey').closest('button.journey-card');
    expect(modedCard.getAttribute('style') ?? '').toContain('--mode-tint');

    const modelessCard = getByText('Old journey').closest('button.journey-card');
    expect(modelessCard.getAttribute('style') ?? '').not.toContain('--mode-tint');
  });
});

describe('Activity: bookmark requires login', () => {
  const ONE_SESSION = [
    { id: 's1', preview_text: 'A single journey', updated_at: '2026-07-15T10:00:00Z', bookmarked: false, has_stagnation_signal: false, mode: null },
  ];

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
    vi.clearAllMocks();
    api.getModes.mockResolvedValue(MODES);
    api.listSessions.mockResolvedValue(ONE_SESSION);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('shows a login prompt instead of toggling the bookmark when signed out', async () => {
    authState.checked = true;
    authState.authenticated = false;
    authState.email = null;
    const { getByLabelText, getByText } = render(Activity, { props: { onOpen: vi.fn() } });

    const star = await waitFor(() => getByLabelText('Bookmark this Journey'));
    await fireEvent.click(star);

    await waitFor(() => getByText('Log in to bookmark Journeys.'));
    expect(api.setBookmark).not.toHaveBeenCalled();
  });

  it('actually toggles the bookmark when signed in', async () => {
    authState.checked = true;
    authState.authenticated = true;
    authState.email = 'person@example.com';
    api.setBookmark.mockResolvedValue({ bookmarked: true });
    const { getByLabelText } = render(Activity, { props: { onOpen: vi.fn() } });

    const star = await waitFor(() => getByLabelText('Bookmark this Journey'));
    await fireEvent.click(star);

    await waitFor(() => expect(api.setBookmark).toHaveBeenCalledWith('s1', true));
  });
});

// Two earlier login nudges (2026-07-18, see frontend/decisions.md) --
// the Journey-completion half, now shown on Activity (a Journey now
// sitting in THIS list) rather than Home.
describe('Activity: Journey-completion login nudge', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
    vi.clearAllMocks();
    localStorage.clear();
    loginNudgeState.pending = false;
    loginNudgeState.sessionId = null;
    api.getModes.mockResolvedValue(MODES);
    api.listSessions.mockResolvedValue([]);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('shows the nudge once a Journey has just completed, signed out', async () => {
    authState.checked = true;
    authState.authenticated = false;
    authState.email = null;
    markJourneyCompleted('s1');

    const { getByText } = render(Activity, { props: { onOpen: vi.fn() } });

    await waitFor(() => getByText(/Want to keep that accessible everywhere/));
  });

  it('never shows the nudge when already signed in', async () => {
    authState.checked = true;
    authState.authenticated = true;
    authState.email = 'person@example.com';
    markJourneyCompleted('s1');

    const { queryByText } = render(Activity, { props: { onOpen: vi.fn() } });

    await waitFor(() => expect(api.listSessions).toHaveBeenCalled());
    expect(queryByText(/Want to keep that accessible everywhere/)).toBeNull();
  });

  it('dismissing the nudge hides it without calling the API', async () => {
    authState.checked = true;
    authState.authenticated = false;
    authState.email = null;
    markJourneyCompleted('s1');

    const { getByText, getByLabelText, queryByText } = render(Activity, { props: { onOpen: vi.fn() } });

    await waitFor(() => getByText(/Want to keep that accessible everywhere/));
    await fireEvent.click(getByLabelText('Dismiss'));

    expect(queryByText(/Want to keep that accessible everywhere/)).toBeNull();
    expect(api.requestMagicLink).not.toHaveBeenCalled();
  });

  it('tapping Sign in reveals the login gate, carrying the completed Journey id', async () => {
    authState.checked = true;
    authState.authenticated = false;
    authState.email = null;
    markJourneyCompleted('s1');
    api.requestMagicLink.mockResolvedValue({ sent: true });

    const { getByText, getByPlaceholderText } = render(Activity, { props: { onOpen: vi.fn() } });

    await waitFor(() => getByText(/Want to keep that accessible everywhere/));
    await fireEvent.click(getByText('Sign in'));
    await fireEvent.input(await waitFor(() => getByPlaceholderText('you@example.com')), {
      target: { value: 'me@example.com' },
    });
    await fireEvent.click(getByText('Send me a login link'));

    await waitFor(() => expect(api.requestMagicLink).toHaveBeenCalledWith('me@example.com', 's1'));
  });
});

// Backlog #255 (see engine/decisions.md "Frontend: richer stagnation
// wording sourced from Judgment's own stagnation_notes"): the aside
// should prefer the real stagnation_note text when present, and only
// fall back to the old fixed generic phrase when has_stagnation_signal
// is true but stagnation_note is null.
describe('Activity: stagnation aside prefers real Judgment wording', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
    vi.clearAllMocks();
    api.getModes.mockResolvedValue(MODES);
    authState.checked = true;
    authState.authenticated = true;
    authState.email = 'me@example.com';
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders the real stagnation_note text when present', async () => {
    api.listSessions.mockResolvedValue([
      {
        id: 's1', preview_text: 'A Journey', updated_at: '2026-07-15T10:00:00Z',
        bookmarked: false, has_stagnation_signal: true,
        stagnation_note: 'You have not moved on this decision in several turns.', mode: null,
      },
    ]);

    const { getByText, queryByText } = render(Activity, { props: { onOpen: vi.fn() } });

    await waitFor(() => getByText('You have not moved on this decision in several turns.'));
    expect(queryByText("There's more to think through here.")).toBeNull();
  });

  it('falls back to the fixed generic phrase when has_stagnation_signal is true but stagnation_note is null', async () => {
    api.listSessions.mockResolvedValue([
      {
        id: 's1', preview_text: 'A Journey', updated_at: '2026-07-15T10:00:00Z',
        bookmarked: false, has_stagnation_signal: true, stagnation_note: null, mode: null,
      },
    ]);

    const { getByText } = render(Activity, { props: { onOpen: vi.fn() } });

    await waitFor(() => getByText("There's more to think through here."));
  });

  it('renders neither aside when has_stagnation_signal is false and stagnation_note is null', async () => {
    api.listSessions.mockResolvedValue([
      {
        id: 's1', preview_text: 'A Journey', updated_at: '2026-07-15T10:00:00Z',
        bookmarked: false, has_stagnation_signal: false, stagnation_note: null, mode: null,
      },
    ]);

    const { getByText, queryByText } = render(Activity, { props: { onOpen: vi.fn() } });

    await waitFor(() => getByText('A Journey'));
    expect(queryByText("There's more to think through here.")).toBeNull();
  });
});
