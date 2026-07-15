import { describe, it, expect, vi } from 'vitest';
import { render, fireEvent } from '@testing-library/svelte';
import Transcript from '../components/Transcript.svelte';

// Response v3 -- real choice buttons (see engine/decisions.md): tapping
// an option must behave exactly like typing and sending it, and only
// the LAST message's options are ever live -- an earlier turn's
// question is no longer the one on the table.
describe('Transcript', () => {
  it('renders option buttons for the last assistant message', () => {
    const messages = [
      { role: 'user', content: 'I want to move teams.', created_at: '' },
      {
        role: 'assistant',
        content: 'Which one is weighing on you more right now?',
        created_at: '',
        options: ['The MBA', 'The home loan'],
      },
    ];
    const { getByText } = render(Transcript, {
      props: { messages, onOptionSelect: vi.fn(), disabled: false },
    });

    expect(getByText('The MBA')).toBeTruthy();
    expect(getByText('The home loan')).toBeTruthy();
  });

  it('calls onOptionSelect with the tapped option label', async () => {
    const onOptionSelect = vi.fn();
    const messages = [
      {
        role: 'assistant',
        content: 'Which one is weighing on you more right now?',
        created_at: '',
        options: ['The MBA', 'The home loan'],
      },
    ];
    const { getByText } = render(Transcript, {
      props: { messages, onOptionSelect, disabled: false },
    });

    await fireEvent.click(getByText('The MBA'));
    expect(onOptionSelect).toHaveBeenCalledWith('The MBA');
  });

  it('does not render options for an earlier message once a later one exists', () => {
    const messages = [
      {
        role: 'assistant',
        content: 'Which one is weighing on you more right now?',
        created_at: '',
        options: ['The MBA', 'The home loan'],
      },
      { role: 'user', content: 'The MBA.', created_at: '' },
      { role: 'assistant', content: 'What makes the MBA feel riskier?', created_at: '', options: [] },
    ];
    const { queryByText } = render(Transcript, {
      props: { messages, onOptionSelect: vi.fn(), disabled: false },
    });

    expect(queryByText('The MBA')).toBeNull();
    expect(queryByText('The home loan')).toBeNull();
  });

  it('renders nothing extra when the last assistant message has no options', () => {
    const messages = [
      { role: 'assistant', content: 'What feels unresolved right now?', created_at: '', options: [] },
    ];
    const { container } = render(Transcript, {
      props: { messages, onOptionSelect: vi.fn(), disabled: false },
    });

    expect(container.querySelector('.options')).toBeNull();
  });

  it('disables option buttons while a turn is in flight', () => {
    const messages = [
      {
        role: 'assistant',
        content: 'Which one is weighing on you more right now?',
        created_at: '',
        options: ['The MBA', 'The home loan'],
      },
    ];
    const { getByText } = render(Transcript, {
      props: { messages, onOptionSelect: vi.fn(), disabled: true },
    });

    expect(getByText('The MBA')).toBeDisabled();
  });
});
