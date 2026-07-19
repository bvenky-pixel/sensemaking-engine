import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, waitFor } from '@testing-library/svelte';
import BehavioralPatterns from '../components/BehavioralPatterns.svelte';
import * as api from '../lib/api.js';

// Learning surfaced to users (2026-07-18, see engine/decisions.md
// "Learning made per-account", frontend/specs/trust-and-privacy-ux-v1.md's
// Principle 6). Mocking lib/api.js matches every other component
// test's own boundary.
vi.mock('../lib/api.js', () => ({
  getBehavioralPatterns: vi.fn(),
}));

describe('BehavioralPatterns', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows a quiet placeholder when nothing has been computed yet', async () => {
    api.getBehavioralPatterns.mockResolvedValue([]);
    const { getByText, queryByText } = render(BehavioralPatterns);

    await waitFor(() =>
      getByText('Nothing noticed yet -- this needs a few Journeys with a real, repeated pattern before it says anything.')
    );
    expect(queryByText(/Noticed \d+ times/)).toBeNull();
  });

  it('renders every computed pattern with its detail and evidence count, unlike POM never hiding the count behind a category', async () => {
    api.getBehavioralPatterns.mockResolvedValue([
      { pattern_type: 'decision_status_changed', detail: "3 of your decisions have moved to 'deferred' status.", evidence_count: 3 },
      { pattern_type: 'goal_status_changed', detail: "4 of your goals have moved to 'completed' status.", evidence_count: 4 },
    ]);
    const { getByText, queryByText } = render(BehavioralPatterns);

    await waitFor(() => getByText("3 of your decisions have moved to 'deferred' status."));
    expect(getByText('Noticed 3 times')).toBeTruthy();

    expect(getByText("4 of your goals have moved to 'completed' status.")).toBeTruthy();
    expect(getByText('Noticed 4 times')).toBeTruthy();

    // The placeholder must not linger alongside real content.
    expect(queryByText(/Nothing noticed yet/)).toBeNull();
    // Raw internal event-type vocabulary never reaches the screen.
    expect(queryByText(/decision_status_changed/)).toBeNull();
    expect(queryByText(/goal_status_changed/)).toBeNull();
  });
});
