import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, fireEvent, waitFor } from '@testing-library/svelte';
import Settings from '../screens/Settings.svelte';
import * as api from '../lib/api.js';
import { authState } from '../lib/auth.svelte.js';

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
//
// Auth, the low-friction way (2026-07-18, see frontend/decisions.md):
// getAuthStatus/requestMagicLink/verifyMagicLink/logout are mocked here
// too since lib/auth.svelte.js (which Settings now imports) calls them
// -- unused by most tests below, but needed so those imports resolve
// to real mock functions rather than undefined. `authState` itself is
// a real, shared module -- NOT mocked -- since it's plain reactive
// state, not a network boundary; tests set it directly instead.
// POM surfaced to users (2026-07-18, see frontend/decisions.md):
// getPersonalOperatingModel mocked too, since Settings now mounts
// PersonalOperatingModel.svelte as a third section whenever signed in.
vi.mock('../lib/api.js', () => ({
  getPrivacySettings: vi.fn(),
  setCrossSessionLearningEnabled: vi.fn(),
  exportPrivacyData: vi.fn(),
  resetAllData: vi.fn(),
  getAuthStatus: vi.fn(),
  requestMagicLink: vi.fn(),
  verifyMagicLink: vi.fn(),
  logout: vi.fn(),
  getPersonalOperatingModel: vi.fn(),
}));

describe('Settings', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default resolved value every test gets unless it overrides.
    api.getPrivacySettings.mockResolvedValue({ cross_session_learning_enabled: true });
    // Default: no POM computed yet -- PersonalOperatingModel.test.js
    // covers its own populated/empty states directly.
    api.getPersonalOperatingModel.mockResolvedValue(null);
    // Every existing test below exercises the signed-in screen -- see
    // the new describe block further down for the signed-out gate
    // itself. Reset explicitly rather than relying on a previous
    // test's leftover state, since `authState` is one shared module
    // object across every test in this file.
    authState.checked = true;
    authState.authenticated = true;
    authState.email = 'person@example.com';
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

  it('shows the signed-in email and logs out via the API', async () => {
    api.logout.mockResolvedValue(undefined);

    const { getByText } = render(Settings, { props: { onBack: () => {} } });

    await waitFor(() => getByText('person@example.com'));
    await fireEvent.click(getByText('Log out'));

    await waitFor(() => {
      expect(api.logout).toHaveBeenCalled();
    });
  });
});

// Auth, the low-friction way (2026-07-18, see frontend/decisions.md
// "Auth, the low-friction way") -- direct founder brief: the whole
// screen, not just the two backend-persisted controls, needs a login.
describe('Settings: signed out', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authState.checked = true;
    authState.authenticated = false;
    authState.email = null;
  });

  it('shows a login prompt instead of Privacy/Account content', async () => {
    const { getByText, queryByText } = render(Settings, { props: { onBack: () => {} } });

    await waitFor(() => getByText('Log in to access Settings and Privacy controls.'));
    expect(queryByText('Learn across Journeys')).toBeNull();
    expect(queryByText('Reduce motion')).toBeNull();
    // Never calls the privacy endpoint while logged out -- a doomed
    // request nobody needs (see Settings.svelte's own onMount comment).
    expect(api.getPrivacySettings).not.toHaveBeenCalled();
  });

  it('requests a magic link from the login gate', async () => {
    api.requestMagicLink.mockResolvedValue({ sent: true });

    const { getByPlaceholderText, getByText } = render(Settings, { props: { onBack: () => {} } });

    const emailInput = await waitFor(() => getByPlaceholderText('you@example.com'));
    await fireEvent.input(emailInput, { target: { value: 'me@example.com' } });
    await fireEvent.click(getByText('Send me a login link'));

    await waitFor(() => {
      expect(api.requestMagicLink).toHaveBeenCalledWith('me@example.com');
      expect(getByText(/Check/)).toBeTruthy();
    });
  });
});
