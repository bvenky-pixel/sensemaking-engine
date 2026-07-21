import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, waitFor } from '@testing-library/svelte';
import You from '../screens/You.svelte';
import * as api from '../lib/api.js';
import { authState } from '../lib/auth.svelte.js';

// You tab (2026-07-21, backlog #263, see information-architecture-v2.md,
// engine/decisions.md "Frontend IA v2") -- PersonalOperatingModel.svelte/
// BehavioralPatterns.svelte moved here from Settings.svelte, each fully
// self-contained and already covered in detail by their own dedicated
// test files (PersonalOperatingModel.test.js, BehavioralPatterns.test.js)
// -- this file only covers the auth gate and that both mount when
// signed in, not their own populated/empty states again.
vi.mock('../lib/api.js', () => ({
  getPersonalOperatingModel: vi.fn(),
  submitPomFeedback: vi.fn(),
  getBehavioralPatterns: vi.fn(),
}));

describe('You', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getPersonalOperatingModel.mockResolvedValue(null);
    api.getBehavioralPatterns.mockResolvedValue([]);
  });

  it('shows a login prompt instead of POM/Behavioral Patterns when signed out', async () => {
    authState.checked = true;
    authState.authenticated = false;
    authState.email = null;

    const { getByText } = render(You, { props: {} });

    await waitFor(() => getByText('Log in to see what Confidant has noticed about you.'));
    expect(api.getPersonalOperatingModel).not.toHaveBeenCalled();
    expect(api.getBehavioralPatterns).not.toHaveBeenCalled();
  });

  it('mounts both PersonalOperatingModel and BehavioralPatterns when signed in', async () => {
    authState.checked = true;
    authState.authenticated = true;
    authState.email = 'person@example.com';

    render(You, { props: {} });

    await waitFor(() => {
      expect(api.getPersonalOperatingModel).toHaveBeenCalled();
      expect(api.getBehavioralPatterns).toHaveBeenCalled();
    });
  });
});
