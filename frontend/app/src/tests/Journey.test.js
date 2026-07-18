import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, fireEvent, waitFor } from '@testing-library/svelte';
import Journey from '../screens/Journey.svelte';
import * as api from '../lib/api.js';

// Delete a Journey, from the Journey itself (2026-07-18, see
// frontend/decisions.md): moved here from Settings' own Data section --
// this is the first dedicated test file for Journey.svelte, scoped to
// just that one control rather than the whole screen's send/refresh
// flow (already exercised indirectly elsewhere). Mocking lib/api.js
// (rather than fetch) matches every other screen test's own boundary.
vi.mock('../lib/api.js', () => ({
  getMessages: vi.fn(),
  sendMessage: vi.fn(),
  getClarityBrief: vi.fn(),
  getUnderstanding: vi.fn(),
  openStageStream: vi.fn(),
  deleteSession: vi.fn(),
}));

describe('Journey delete action', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getMessages.mockResolvedValue([]);
    api.getClarityBrief.mockResolvedValue(null);
    api.getUnderstanding.mockResolvedValue({ tier1: [], tier2: [] });
  });

  it('asks for confirmation before deleting, and does nothing on Cancel', async () => {
    const onBack = vi.fn();
    const { getByText, queryByText } = render(Journey, { props: { sessionId: 's1', onBack } });

    await waitFor(() => getByText('Delete this Journey'));
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
    const { getByText } = render(Journey, { props: { sessionId: 's1', onBack } });

    await waitFor(() => getByText('Delete this Journey'));
    await fireEvent.click(getByText('Delete this Journey'));
    await fireEvent.click(getByText('Yes, delete it'));

    await waitFor(() => {
      expect(api.deleteSession).toHaveBeenCalledWith('s1');
      expect(onBack).toHaveBeenCalled();
    });
  });
});
