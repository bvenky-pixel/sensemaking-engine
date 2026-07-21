import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, fireEvent, waitFor } from '@testing-library/svelte';
import Home from '../screens/Home.svelte';
import * as api from '../lib/api.js';

// Home, narrowed (2026-07-21, backlog #265, see
// information-architecture-v2.md, engine/decisions.md "Frontend IA
// v2"): the journey list, filtering, bookmarking, and completion nudge
// all moved to Activity.svelte (see Activity.test.js for that
// coverage) -- Home is now purely the entry/welcome hero, always
// shown, with a single job: get a person into a Journey.
vi.mock('../lib/api.js', () => ({
  createSession: vi.fn(),
  getModes: vi.fn(),
}));

const MODES = [
  { id: 'vent', label: 'Vent', description: 'Just get this out.' },
  { id: 'strategize', label: 'Strategize', description: 'Lay out real choices.' },
];

describe('Home', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getModes.mockResolvedValue(MODES);
  });

  it('always shows the mode picker, with no journey list or filters', async () => {
    const { getByText, queryByRole } = render(Home, { props: { onOpen: vi.fn() } });

    await waitFor(() => expect(getByText('Vent')).toBeTruthy());
    expect(queryByRole('button', { name: 'All time filter' })).toBeNull();
  });

  it('creates a session and calls onOpen when a mode is chosen', async () => {
    api.createSession.mockResolvedValue({ id: 'new-session' });
    const onOpen = vi.fn();
    const { getByText } = render(Home, { props: { onOpen } });

    await fireEvent.click(await waitFor(() => getByText('Vent')));

    await waitFor(() => expect(api.createSession).toHaveBeenCalledWith('vent'));
    expect(onOpen).toHaveBeenCalledWith('new-session');
  });
});
