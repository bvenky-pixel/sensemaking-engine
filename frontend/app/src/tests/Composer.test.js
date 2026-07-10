import { describe, it, expect, vi } from 'vitest';
import { render, fireEvent } from '@testing-library/svelte';
import Composer from '../components/Composer.svelte';

// Philosophy-conformance: "handing the page over" must stay two
// deliberately distinct actions (writing vs. indicating readiness).
// Bare Enter must never submit -- only the explicit "Share this" click.
describe('Composer', () => {
  it('never submits on bare Enter, only on the explicit action', async () => {
    const onSend = vi.fn();
    const { getByPlaceholderText, getByText } = render(Composer, {
      props: { disabled: false, onSend },
    });

    const textarea = getByPlaceholderText("What's on your mind?");
    await fireEvent.input(textarea, { target: { value: 'a real thought' } });
    await fireEvent.keyDown(textarea, { key: 'Enter' });

    expect(onSend).not.toHaveBeenCalled();

    await fireEvent.click(getByText('Share this'));
    expect(onSend).toHaveBeenCalledWith('a real thought');
  });

  it('does not send empty or whitespace-only content', async () => {
    const onSend = vi.fn();
    const { getByPlaceholderText, getByText } = render(Composer, {
      props: { disabled: false, onSend },
    });

    const textarea = getByPlaceholderText("What's on your mind?");
    await fireEvent.input(textarea, { target: { value: '   ' } });

    expect(getByText('Share this')).toBeDisabled();
  });
});
