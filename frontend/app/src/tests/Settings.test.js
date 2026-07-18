import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, fireEvent, waitFor } from '@testing-library/svelte';
import Settings from '../screens/Settings.svelte';
import * as api from '../lib/api.js';

// Privacy, made real (2026-07-18, see frontend/decisions.md): Settings
// calls getPrivacySettings on mount, setCrossSessionLearningEnabled/
// exportPrivacyData/resetAllData on user action. Mocking lib/api.js
// here (rather than fetch itself) matches this screen's own "thin
// fetch wrapper" boundary -- Settings never talks to fetch directly.
//
// Delete a Journey, from the Journey itself (2026-07-18, see
// frontend/decisions.md): listSessions/deleteSession moved out of this
// file along with Settings' own Data section -- see Journey.test.js
// for the delete-a-Journey coverage now.
vi.mock('../lib/api.js', () => ({
  getPrivacySettings: vi.fn(),
  setCrossSessionLearningEnabled: vi.fn(),
  exportPrivacyData: vi.fn(),
  resetAllData: vi.fn(),
}));

describe('Settings', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default resolved value every test gets unless it overrides.
    api.getPrivacySettings.mockResolvedValue({ cross_session_learning_enabled: true });
  });

  it('reflects the current cross-session-learning setting on load', async () => {
    api.getPrivacySettings.mockResolvedValue({ cross_session_learning_enabled: false });

    const { getByRole } = render(Settings, { props: { onBack: () => {} } });

    await waitFor(() => {
      expect(getByRole('switch', { name: 'Learn across Journeys' }).getAttribute('aria-checked')).toBe('false');
    });
  });

  it('toggles cross-session learning and persists it via the API', async () => {
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
    const { getByText, queryByText } = render(Settings, { props: { onBack: () => {} } });

    await waitFor(() => getByText('Forget everything'));
    await fireEvent.click(getByText('Forget everything'));

    expect(getByText("Forget everything Confidant knows about you? This can't be undone.")).toBeTruthy();
    expect(api.resetAllData).not.toHaveBeenCalled();

    await fireEvent.click(getByText('Cancel'));

    expect(queryByText("Forget everything Confidant knows about you? This can't be undone.")).toBeNull();
    expect(api.resetAllData).not.toHaveBeenCalled();
  });

  it('calls resetAllData after confirming Forget everything', async () => {
    api.resetAllData.mockResolvedValue(undefined);

    const { getByText } = render(Settings, { props: { onBack: () => {} } });

    await waitFor(() => getByText('Forget everything'));
    await fireEvent.click(getByText('Forget everything'));
    await fireEvent.click(getByText('Yes, forget everything'));

    await waitFor(() => {
      expect(api.resetAllData).toHaveBeenCalled();
    });
  });

  it('triggers a data export download', async () => {
    const blob = new Blob(['{}'], { type: 'application/json' });
    api.exportPrivacyData.mockResolvedValue(blob);

    const { getByText } = render(Settings, { props: { onBack: () => {} } });

    await waitFor(() => getByText('Export your data'));
    await fireEvent.click(getByText('Export your data'));

    await waitFor(() => {
      expect(api.exportPrivacyData).toHaveBeenCalled();
    });
  });
});
