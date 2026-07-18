import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, fireEvent, waitFor } from '@testing-library/svelte';
import Settings from '../screens/Settings.svelte';
import * as api from '../lib/api.js';

// Data section added 2026-07-15 (see engine/decisions.md "Frontend UX
// pass" / conversation-removal follow-up): the first of Settings' three
// sections with a real backend-backed control. Mocking lib/api.js here
// (rather than fetch itself) matches this screen's own "thin fetch
// wrapper" boundary -- Settings never talks to fetch directly.
// Privacy, made real (2026-07-18, see frontend/decisions.md): three more
// api.js functions Settings now calls -- getPrivacySettings on mount
// (same as listSessions), setCrossSessionLearningEnabled/exportPrivacyData/
// resetAllData on user action, mirroring listSessions/deleteSession's own
// mocking treatment.
vi.mock('../lib/api.js', () => ({
  listSessions: vi.fn(),
  deleteSession: vi.fn(),
  getPrivacySettings: vi.fn(),
  setCrossSessionLearningEnabled: vi.fn(),
  exportPrivacyData: vi.fn(),
  resetAllData: vi.fn(),
}));

describe('Settings', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default resolved value every test gets unless it overrides --
    // mirrors every existing test's own explicit
    // api.listSessions.mockResolvedValue(...) call, just for the one
    // new fetch Settings makes on every mount regardless of what a
    // given test actually cares about.
    api.getPrivacySettings.mockResolvedValue({ cross_session_learning_enabled: true });
  });

  it('renders each session by its preview_text', async () => {
    api.listSessions.mockResolvedValue([
      { id: 's1', preview_text: 'I want to move teams.' },
      { id: 's2', preview_text: 'Deciding between two job offers.' },
    ]);

    const { getByText } = render(Settings, { props: { onBack: () => {} } });

    await waitFor(() => {
      expect(getByText('I want to move teams.')).toBeTruthy();
      expect(getByText('Deciding between two job offers.')).toBeTruthy();
    });
  });

  it('falls back to a generic label when a session has no preview_text yet', async () => {
    api.listSessions.mockResolvedValue([{ id: 's1', preview_text: '' }]);

    const { getByText } = render(Settings, { props: { onBack: () => {} } });

    await waitFor(() => {
      expect(getByText('A new Journey')).toBeTruthy();
    });
  });

  it('shows a plain message when there are no sessions', async () => {
    api.listSessions.mockResolvedValue([]);

    const { getByText } = render(Settings, { props: { onBack: () => {} } });

    await waitFor(() => {
      expect(getByText('Nothing shared here yet.')).toBeTruthy();
    });
  });

  it('asks for confirmation before removing, and does nothing on Cancel', async () => {
    api.listSessions.mockResolvedValue([{ id: 's1', preview_text: 'I want to move teams.' }]);

    const { getByText, queryByText } = render(Settings, { props: { onBack: () => {} } });

    await waitFor(() => getByText('I want to move teams.'));
    await fireEvent.click(getByText('Remove'));

    expect(getByText('Remove this Journey for good?')).toBeTruthy();
    expect(api.deleteSession).not.toHaveBeenCalled();

    await fireEvent.click(getByText('Cancel'));

    expect(queryByText('Remove this Journey for good?')).toBeNull();
    expect(getByText('I want to move teams.')).toBeTruthy();
    expect(api.deleteSession).not.toHaveBeenCalled();
  });

  it('removes the session from the list after confirming', async () => {
    api.listSessions.mockResolvedValue([
      { id: 's1', preview_text: 'I want to move teams.' },
      { id: 's2', preview_text: 'Deciding between two job offers.' },
    ]);
    api.deleteSession.mockResolvedValue(undefined);

    const { getByText, getAllByText, queryByText } = render(Settings, { props: { onBack: () => {} } });

    await waitFor(() => getByText('I want to move teams.'));
    await fireEvent.click(getAllByText('Remove')[0]);
    await fireEvent.click(getByText('Yes, remove it'));

    await waitFor(() => {
      expect(api.deleteSession).toHaveBeenCalledWith('s1');
      expect(queryByText('I want to move teams.')).toBeNull();
    });
    expect(getByText('Deciding between two job offers.')).toBeTruthy();
  });

  it('reflects the current cross-session-learning setting on load', async () => {
    api.listSessions.mockResolvedValue([]);
    api.getPrivacySettings.mockResolvedValue({ cross_session_learning_enabled: false });

    const { getByRole } = render(Settings, { props: { onBack: () => {} } });

    await waitFor(() => {
      expect(getByRole('switch', { name: 'Learn across Journeys' }).getAttribute('aria-checked')).toBe('false');
    });
  });

  it('toggles cross-session learning and persists it via the API', async () => {
    api.listSessions.mockResolvedValue([]);
    api.getPrivacySettings.mockResolvedValue({ cross_session_learning_enabled: true });
    api.setCrossSessionLearningEnabled.mockResolvedValue({ cross_session_learning_enabled: false });

    const { getByRole } = render(Settings, { props: { onBack: () => {} } });

    const toggle = await waitFor(() => getByRole('switch', { name: 'Learn across Journeys' }));
    expect(toggle.getAttribute('aria-checked')).toBe('true');

    await fireEvent.click(toggle);

    expect(toggle.getAttribute('aria-checked')).toBe('false');
    expect(api.setCrossSessionLearningEnabled).toHaveBeenCalledWith(false);
  });

  it('asks for confirmation before forgetting everything, and does nothing on Cancel', async () => {
    api.listSessions.mockResolvedValue([{ id: 's1', preview_text: 'I want to move teams.' }]);

    const { getByText, queryByText } = render(Settings, { props: { onBack: () => {} } });

    await waitFor(() => getByText('I want to move teams.'));
    await fireEvent.click(getByText('Forget everything'));

    expect(getByText("Forget everything Confidant knows about you? This can't be undone.")).toBeTruthy();
    expect(api.resetAllData).not.toHaveBeenCalled();

    await fireEvent.click(getByText('Cancel'));

    expect(queryByText("Forget everything Confidant knows about you? This can't be undone.")).toBeNull();
    expect(api.resetAllData).not.toHaveBeenCalled();
  });

  it('clears every Journey after confirming Forget everything', async () => {
    api.listSessions.mockResolvedValue([{ id: 's1', preview_text: 'I want to move teams.' }]);
    api.resetAllData.mockResolvedValue(undefined);

    const { getByText, queryByText } = render(Settings, { props: { onBack: () => {} } });

    await waitFor(() => getByText('I want to move teams.'));
    await fireEvent.click(getByText('Forget everything'));
    await fireEvent.click(getByText('Yes, forget everything'));

    await waitFor(() => {
      expect(api.resetAllData).toHaveBeenCalled();
      expect(queryByText('I want to move teams.')).toBeNull();
      expect(getByText('Nothing shared here yet.')).toBeTruthy();
    });
  });
});
