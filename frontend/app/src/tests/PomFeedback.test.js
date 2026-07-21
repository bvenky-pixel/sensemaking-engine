import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, fireEvent, waitFor } from '@testing-library/svelte';
import PomFeedback from '../components/PomFeedback.svelte';
import * as api from '../lib/api.js';

// Light affirm/correct affordance on POM's "You" section (2026-07-19,
// backlog #209, see engine/decisions.md).
vi.mock('../lib/api.js', () => ({
  submitPomFeedback: vi.fn(),
}));

describe('PomFeedback', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows both reactions up front, and none of the transient states', () => {
    const { getByText, queryByText } = render(PomFeedback, {
      system: 'identity', statement: 'Values independence at work.',
    });
    expect(getByText('Sounds right')).toBeTruthy();
    expect(getByText('Not quite')).toBeTruthy();
    expect(queryByText('Noted, thanks.')).toBeNull();
  });

  it('affirming submits the statement as-is and shows a quiet confirmation', async () => {
    api.submitPomFeedback.mockResolvedValue(undefined);
    const { getByText, queryByText } = render(PomFeedback, {
      system: 'identity', statement: 'Values independence at work.',
    });

    await fireEvent.click(getByText('Sounds right'));

    await waitFor(() => getByText('Noted, thanks.'));
    expect(api.submitPomFeedback).toHaveBeenCalledWith('identity', 'Values independence at work.', 'affirm');
    expect(queryByText('Sounds right')).toBeNull();
  });

  it('correcting reveals an optional text box, and submits with the typed correction', async () => {
    api.submitPomFeedback.mockResolvedValue(undefined);
    const { getByText, getByPlaceholderText } = render(PomFeedback, {
      system: 'stress', statement: 'You seem stretched thin.',
    });

    await fireEvent.click(getByText('Not quite'));
    const textarea = getByPlaceholderText("Optional -- what's actually true?");
    await fireEvent.input(textarea, { target: { value: 'Actually things have calmed down a lot.' } });
    await fireEvent.click(getByText('Send'));

    await waitFor(() => getByText('Noted, thanks.'));
    expect(api.submitPomFeedback).toHaveBeenCalledWith(
      'stress', 'You seem stretched thin.', 'correct', 'Actually things have calmed down a lot.',
    );
  });

  it('correcting with no typed text still submits, with a null correction', async () => {
    api.submitPomFeedback.mockResolvedValue(undefined);
    const { getByText } = render(PomFeedback, {
      system: 'stress', statement: 'You seem stretched thin.',
    });

    await fireEvent.click(getByText('Not quite'));
    await fireEvent.click(getByText('Send'));

    await waitFor(() => getByText('Noted, thanks.'));
    expect(api.submitPomFeedback).toHaveBeenCalledWith('stress', 'You seem stretched thin.', 'correct', null);
  });

  it('cancelling a correction returns to the idle reactions with no submission', async () => {
    const { getByText, queryByPlaceholderText } = render(PomFeedback, {
      system: 'stress', statement: 'You seem stretched thin.',
    });

    await fireEvent.click(getByText('Not quite'));
    await fireEvent.click(getByText('Cancel'));

    expect(queryByPlaceholderText("Optional -- what's actually true?")).toBeNull();
    expect(getByText('Sounds right')).toBeTruthy();
    expect(api.submitPomFeedback).not.toHaveBeenCalled();
  });

  it('a failed submission shows a retry-friendly error and leaves the reactions in place', async () => {
    api.submitPomFeedback.mockRejectedValue(new Error('network down'));
    const { getByText } = render(PomFeedback, {
      system: 'identity', statement: 'Values independence at work.',
    });

    await fireEvent.click(getByText('Sounds right'));

    await waitFor(() => getByText("Couldn't send -- try again."));
    expect(getByText('Sounds right')).toBeTruthy();
  });
});
