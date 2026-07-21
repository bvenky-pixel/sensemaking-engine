import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, fireEvent, waitFor } from '@testing-library/svelte';
import ModeSelect from '../screens/ModeSelect.svelte';
import * as api from '../lib/api.js';

// Counseling modes (see engine/decisions.md): this screen is a thin
// reflection of GET /modes -- no hardcoded labels/descriptions here,
// same "Reflection of Backend Truth" principle as every other
// frontend/api.js call.
vi.mock('../lib/api.js', () => ({
  getModes: vi.fn(),
  createSession: vi.fn(),
}));

const MODES = [
  { id: 'vent', label: 'Vent', description: 'Just get this out. No fixing needed yet.' },
  { id: 'strategize', label: 'Strategize', description: 'Weigh the options and the tradeoffs.' },
  { id: 'commit', label: 'Commit', description: 'Get real about follow-through.' },
  { id: 'explore', label: 'Explore', description: 'Think it through out loud, one question at a time.' },
  { id: 'realign', label: 'Realign', description: 'Check this against what actually matters to you.' },
];

describe('ModeSelect', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders all five modes fetched from GET /modes', async () => {
    api.getModes.mockResolvedValue(MODES);

    const { getByText } = render(ModeSelect, { props: { onOpen: vi.fn(), onBack: vi.fn() } });

    await waitFor(() => {
      for (const mode of MODES) {
        expect(getByText(mode.label)).toBeTruthy();
        expect(getByText(mode.description)).toBeTruthy();
      }
    });
  });

  it('creates a session with the chosen mode and opens it', async () => {
    api.getModes.mockResolvedValue(MODES);
    api.createSession.mockResolvedValue({ id: 'session-123' });
    const onOpen = vi.fn();

    const { getByText } = render(ModeSelect, { props: { onOpen, onBack: vi.fn() } });

    await waitFor(() => getByText('Vent'));
    await fireEvent.click(getByText('Vent'));

    await waitFor(() => {
      expect(api.createSession).toHaveBeenCalledWith('vent');
      expect(onOpen).toHaveBeenCalledWith('session-123');
    });
  });

  it('calls onBack when the Back link is clicked', async () => {
    api.getModes.mockResolvedValue(MODES);
    const onBack = vi.fn();

    const { getByText } = render(ModeSelect, { props: { onOpen: vi.fn(), onBack } });

    await fireEvent.click(getByText('← Back'));
    expect(onBack).toHaveBeenCalled();
  });
});
