import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, fireEvent, waitFor } from '@testing-library/svelte';
import Home from '../screens/Home.svelte';
import * as api from '../lib/api.js';

// Home: time period + mode filtering (2026-07-18, see
// frontend/decisions.md) -- the first dedicated test file for
// Home.svelte, scoped to the new filtering logic specifically (period
// toggle + counts, mode filter chips, the two composing and resetting
// correctly on period change). Mocking lib/api.js (rather than fetch)
// matches every other screen test's own boundary.
vi.mock('../lib/api.js', () => ({
  listSessions: vi.fn(),
  setBookmark: vi.fn(),
  createSession: vi.fn(),
  getModes: vi.fn(),
}));

const MODES = [
  { id: 'vent', label: 'Vent', description: 'Just get this out.' },
  { id: 'strategize', label: 'Strategize', description: 'Lay out real choices.' },
];

// A fixed "now" (a Wednesday, comfortably mid-week/mid-month/mid-year)
// so period boundaries are unambiguous regardless of what day this
// suite actually runs on -- real calendar math (Monday-start weeks,
// variable month lengths) has genuine edge cases near period
// boundaries that would make fixture dates flaky without pinning the
// clock.
const NOW = new Date('2026-07-15T12:00:00Z');

const SESSIONS = [
  // Within the current week (Mon 2026-07-13 or later).
  { id: 's-week', preview_text: 'This week journey', updated_at: '2026-07-15T10:00:00Z', bookmarked: false, has_stagnation_signal: false, mode: 'vent' },
  // Within the current month but before the current week.
  { id: 's-month', preview_text: 'This month journey', updated_at: '2026-07-05T10:00:00Z', bookmarked: false, has_stagnation_signal: false, mode: 'strategize' },
  // Within the current year but before the current month.
  { id: 's-year', preview_text: 'This year journey', updated_at: '2026-03-01T10:00:00Z', bookmarked: false, has_stagnation_signal: false, mode: 'vent' },
  // Older than a year -- only "All time" should include it.
  { id: 's-old', preview_text: 'Old journey', updated_at: '2024-01-01T10:00:00Z', bookmarked: false, has_stagnation_signal: false, mode: null },
];

describe('Home: time period + mode filtering', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
    vi.clearAllMocks();
    api.getModes.mockResolvedValue(MODES);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('shows every Journey under All time, the default', async () => {
    api.listSessions.mockResolvedValue(SESSIONS);
    const { getByText } = render(Home, { props: { onOpen: vi.fn(), onSettings: vi.fn(), onBeginNew: vi.fn() } });

    await waitFor(() => {
      expect(getByText('This week journey')).toBeTruthy();
      expect(getByText('This month journey')).toBeTruthy();
      expect(getByText('This year journey')).toBeTruthy();
      expect(getByText('Old journey')).toBeTruthy();
    });
  });

  it('shows a count next to each time period', async () => {
    api.listSessions.mockResolvedValue(SESSIONS);
    const { getByRole } = render(Home, { props: { onOpen: vi.fn(), onSettings: vi.fn(), onBeginNew: vi.fn() } });

    await waitFor(() => {
      expect(getByRole('button', { name: 'This week filter' }).textContent).toContain('1');
      expect(getByRole('button', { name: 'This month filter' }).textContent).toContain('2');
      expect(getByRole('button', { name: 'This year filter' }).textContent).toContain('3');
      expect(getByRole('button', { name: 'All time filter' }).textContent).toContain('4');
    });
  });

  it('filters to only this week when This week is selected', async () => {
    api.listSessions.mockResolvedValue(SESSIONS);
    const { getByRole, getByText, queryByText } = render(Home, {
      props: { onOpen: vi.fn(), onSettings: vi.fn(), onBeginNew: vi.fn() },
    });

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
    const { getByRole, getByText, queryByText } = render(Home, {
      props: { onOpen: vi.fn(), onSettings: vi.fn(), onBeginNew: vi.fn() },
    });

    await waitFor(() => getByText('Old journey'));
    // This year -> s-week (vent), s-month (strategize), s-year (vent):
    // two distinct modes, so the chip row appears.
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
    const { getByRole, getByText, queryByText } = render(Home, {
      props: { onOpen: vi.fn(), onSettings: vi.fn(), onBeginNew: vi.fn() },
    });

    await waitFor(() => getByText('Old journey'));
    await fireEvent.click(getByRole('button', { name: 'This year filter' }));
    await waitFor(() => getByText('Strategize'));
    await fireEvent.click(getByText('Strategize'));
    // Isolated to This month journey (the only strategize one) --
    // confirms the filter actually applied before testing the reset.
    await waitFor(() => expect(queryByText('This week journey')).toBeNull());

    // If the mode filter carried over uncleared, This week would show
    // nothing (This week journey is 'vent', not 'strategize').
    await fireEvent.click(getByRole('button', { name: 'This week filter' }));

    await waitFor(() => {
      expect(getByText('This week journey')).toBeTruthy();
    });
  });

  it('shows a contextual empty message when the selected period has no Journeys', async () => {
    api.listSessions.mockResolvedValue([SESSIONS[3]]); // only the old one
    const { getByRole, getByText } = render(Home, {
      props: { onOpen: vi.fn(), onSettings: vi.fn(), onBeginNew: vi.fn() },
    });

    await waitFor(() => getByText('Old journey'));
    await fireEvent.click(getByRole('button', { name: 'This week filter' }));

    await waitFor(() => {
      expect(getByText('No Journeys in this time period.')).toBeTruthy();
    });
  });

  it('gives a Journey with a mode a colored left edge, and leaves a mode-less one plain', async () => {
    api.listSessions.mockResolvedValue(SESSIONS);
    const { getByText } = render(Home, { props: { onOpen: vi.fn(), onSettings: vi.fn(), onBeginNew: vi.fn() } });

    await waitFor(() => getByText('Old journey'));

    const modedCard = getByText('This week journey').closest('button.journey-card');
    expect(modedCard.getAttribute('style') ?? '').toContain('--mode-tint');

    const modelessCard = getByText('Old journey').closest('button.journey-card');
    expect(modelessCard.getAttribute('style') ?? '').not.toContain('--mode-tint');
  });
});
