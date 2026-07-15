import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, fireEvent, waitFor } from '@testing-library/svelte';
import Settings from '../screens/Settings.svelte';
import * as api from '../lib/api.js';

// Data section added 2026-07-15 (see engine/decisions.md "Frontend UX
// pass" / conversation-removal follow-up): the first of Settings' three
// sections with a real backend-backed control. Mocking lib/api.js here
// (rather than fetch itself) matches this screen's own "thin fetch
// wrapper" boundary -- Settings never talks to fetch directly.
vi.mock('../lib/api.js', () => ({
  listSessions: vi.fn(),
  deleteSession: vi.fn(),
}));

describe('Settings', () => {
  beforeEach(() => {
    vi.clearAllMocks();
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
});
