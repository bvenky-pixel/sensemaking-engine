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
//
// You tab (2026-07-21, backlog #263, see engine/decisions.md "Frontend
// IA v2"): PersonalOperatingModel.svelte/BehavioralPatterns.svelte (and
// their getPersonalOperatingModel/getBehavioralPatterns mocks) moved
// out of this file to You.test.js along with the components
// themselves -- Settings no longer mounts either.
vi.mock('../lib/api.js', () => ({
  getPrivacySettings: vi.fn(),
  setCrossSessionLearningEnabled: vi.fn(),
  setReflectionPromptEnabled: vi.fn(),
  exportPrivacyData: vi.fn(),
  resetAllData: vi.fn(),
  getAuthStatus: vi.fn(),
  requestMagicLink: vi.fn(),
  verifyMagicLink: vi.fn(),
  logout: vi.fn(),
}));

describe('Settings', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default resolved value every test gets unless it overrides.
    api.getPrivacySettings.mockResolvedValue({
      cross_session_learning_enabled: true,
      reflection_prompt_enabled: false,
    });
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
    api.getPrivacySettings.mockResolvedValue({
      cross_session_learning_enabled: false,
      reflection_prompt_enabled: false,
    });

    const { getByRole } = render(Settings, { props: {} });

    await waitFor(() => {
      expect(getByRole('switch', { name: 'Learn across Journeys' }).getAttribute('aria-checked')).toBe('false');
    });
  });

  it('toggles cross-session learning and persists it via the API', async () => {
    api.getPrivacySettings.mockResolvedValue({
      cross_session_learning_enabled: true,
      reflection_prompt_enabled: false,
    });
    api.setCrossSessionLearningEnabled.mockResolvedValue({
      cross_session_learning_enabled: false,
      reflection_prompt_enabled: false,
    });

    const { getByRole } = render(Settings, { props: {} });

    const toggle = await waitFor(() => getByRole('switch', { name: 'Learn across Journeys' }));
    expect(toggle.getAttribute('aria-checked')).toBe('true');

    await fireEvent.click(toggle);

    expect(toggle.getAttribute('aria-checked')).toBe('false');
    // Turning learning off also turns reflection prompting off (see
    // Settings.svelte's own toggleCrossSessionLearning) -- both current
    // values are always sent together, not a partial update.
    expect(api.setCrossSessionLearningEnabled).toHaveBeenCalledWith(false, false);
  });

  it('turning cross-session learning back on does not re-enable the reflection prompt', async () => {
    api.getPrivacySettings.mockResolvedValue({
      cross_session_learning_enabled: false,
      reflection_prompt_enabled: false,
    });
    api.setCrossSessionLearningEnabled.mockResolvedValue({
      cross_session_learning_enabled: true,
      reflection_prompt_enabled: false,
    });

    const { getByRole } = render(Settings, { props: {} });

    const toggle = await waitFor(() => getByRole('switch', { name: 'Learn across Journeys' }));
    await fireEvent.click(toggle);

    expect(api.setCrossSessionLearningEnabled).toHaveBeenCalledWith(true, false);
  });

  it('shows the reflection-prompt toggle only when cross-session learning is on', async () => {
    api.getPrivacySettings.mockResolvedValue({
      cross_session_learning_enabled: false,
      reflection_prompt_enabled: false,
    });

    const { queryByRole } = render(Settings, { props: {} });

    await waitFor(() => expect(api.getPrivacySettings).toHaveBeenCalled());
    expect(queryByRole('switch', { name: 'Ask a reflection question when I finish a Journey' })).toBeNull();
  });

  it('toggles the reflection prompt and persists it via the API', async () => {
    api.getPrivacySettings.mockResolvedValue({
      cross_session_learning_enabled: true,
      reflection_prompt_enabled: false,
    });
    api.setReflectionPromptEnabled.mockResolvedValue({
      cross_session_learning_enabled: true,
      reflection_prompt_enabled: true,
    });

    const { getByRole } = render(Settings, { props: {} });

    const toggle = await waitFor(() =>
      getByRole('switch', { name: 'Ask a reflection question when I finish a Journey' })
    );
    expect(toggle.getAttribute('aria-checked')).toBe('false');

    await fireEvent.click(toggle);

    expect(toggle.getAttribute('aria-checked')).toBe('true');
    expect(api.setReflectionPromptEnabled).toHaveBeenCalledWith(true, true);
  });

  it('asks for confirmation before forgetting everything, and does nothing on Cancel', async () => {
    const { getByText, queryByText } = render(Settings, { props: {} });

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

    const { getByText } = render(Settings, { props: {} });

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

    const { getByText } = render(Settings, { props: {} });

    await waitFor(() => getByText('Export your data'));
    await fireEvent.click(getByText('Export your data'));

    await waitFor(() => {
      expect(api.exportPrivacyData).toHaveBeenCalled();
    });
  });

  it('shows the signed-in email and logs out via the API', async () => {
    api.logout.mockResolvedValue(undefined);

    const { getByText } = render(Settings, { props: {} });

    await waitFor(() => getByText('person@example.com'));
    await fireEvent.click(getByText('Log out'));

    await waitFor(() => {
      expect(api.logout).toHaveBeenCalled();
    });
  });
});

// Appearance: accent color picker (2026-07-21, direct founder
// instruction, see engine/decisions.md "Accent color picker") --
// accentTheme.js itself is plain localStorage + a <html> attribute
// (same untested-directly precedent as motionPreference.js, its own
// established sibling), so this file covers it through the real
// Settings UI rather than a separate unit-test file for the module.
describe('Settings: accent color picker', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getPrivacySettings.mockResolvedValue({
      cross_session_learning_enabled: true,
      reflection_prompt_enabled: false,
    });
    authState.checked = true;
    authState.authenticated = true;
    authState.email = 'person@example.com';
    localStorage.removeItem('confidant:accent-theme');
    document.documentElement.removeAttribute('data-accent-theme');
  });

  it('defaults to Coral selected and no data-accent-theme attribute', async () => {
    const { getByRole } = render(Settings, { props: {} });

    await waitFor(() => {
      expect(getByRole('radio', { name: 'Coral (default)' }).getAttribute('aria-checked')).toBe('true');
    });
    expect(getByRole('radio', { name: 'Periwinkle' }).getAttribute('aria-checked')).toBe('false');
    expect(document.documentElement.getAttribute('data-accent-theme')).toBeNull();
  });

  it('selecting a color persists it and sets the data-accent-theme attribute immediately', async () => {
    const { getByRole } = render(Settings, { props: {} });

    const sage = await waitFor(() => getByRole('radio', { name: 'Sage' }));
    await fireEvent.click(sage);

    expect(sage.getAttribute('aria-checked')).toBe('true');
    expect(document.documentElement.getAttribute('data-accent-theme')).toBe('sage');
    expect(localStorage.getItem('confidant:accent-theme')).toBe('sage');
  });

  it('selecting Coral after a different color clears the attribute and storage', async () => {
    localStorage.setItem('confidant:accent-theme', 'gold');
    const { getByRole } = render(Settings, { props: {} });

    const coral = await waitFor(() => getByRole('radio', { name: 'Coral (default)' }));
    expect(coral.getAttribute('aria-checked')).toBe('false');

    await fireEvent.click(coral);

    expect(coral.getAttribute('aria-checked')).toBe('true');
    expect(document.documentElement.getAttribute('data-accent-theme')).toBeNull();
    expect(localStorage.getItem('confidant:accent-theme')).toBeNull();
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
    const { getByText, queryByText } = render(Settings, { props: {} });

    await waitFor(() => getByText('Log in to access Settings and Privacy controls.'));
    expect(queryByText('Learn across Journeys')).toBeNull();
    expect(queryByText('Reduce motion')).toBeNull();
    // Never calls the privacy endpoint while logged out -- a doomed
    // request nobody needs (see Settings.svelte's own onMount comment).
    expect(api.getPrivacySettings).not.toHaveBeenCalled();
  });

  it('requests a magic link from the login gate', async () => {
    api.requestMagicLink.mockResolvedValue({ sent: true });

    const { getByPlaceholderText, getByText } = render(Settings, { props: {} });

    const emailInput = await waitFor(() => getByPlaceholderText('you@example.com'));
    await fireEvent.input(emailInput, { target: { value: 'me@example.com' } });
    await fireEvent.click(getByText('Send me a login link'));

    await waitFor(() => {
      // Settings' own gate has no Journey to return to (see
      // LoginGate.svelte's returnSessionId default) -- null, not a
      // real session id.
      expect(api.requestMagicLink).toHaveBeenCalledWith('me@example.com', null);
      expect(getByText(/Check/)).toBeTruthy();
    });
  });
});
