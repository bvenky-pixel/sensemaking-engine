import { describe, it, expect, vi } from 'vitest';
import { render, fireEvent } from '@testing-library/svelte';
import Transcript from '../components/Transcript.svelte';

const MBA_OPTION = { label: 'The MBA', description: "You mentioned the program's tuition." };
const HOUSE_OPTION = { label: 'The home loan', description: 'You mentioned the down payment.' };

// Response v3 -- real choice buttons (see engine/decisions.md): tapping
// an option must behave exactly like typing and sending it, and only
// the LAST message's options are ever live -- an earlier turn's
// question is no longer the one on the table. Each option carries a
// label (the clickable reply) and a description (1-2 sentences of
// display-only reasoning, added same round per direct user request).
describe('Transcript', () => {
  it('renders each option\'s label and description for the last assistant message', () => {
    const messages = [
      { role: 'user', content: 'I want to move teams.', created_at: '' },
      {
        role: 'assistant',
        content: 'Which one is weighing on you more right now?',
        created_at: '',
        options: [MBA_OPTION, HOUSE_OPTION],
      },
    ];
    const { getByText } = render(Transcript, {
      props: { messages, onOptionSelect: vi.fn(), disabled: false },
    });

    expect(getByText('The MBA')).toBeTruthy();
    expect(getByText("You mentioned the program's tuition.")).toBeTruthy();
    expect(getByText('The home loan')).toBeTruthy();
    expect(getByText('You mentioned the down payment.')).toBeTruthy();
  });

  it('calls onOptionSelect with the tapped option\'s label, not its description', async () => {
    const onOptionSelect = vi.fn();
    const messages = [
      {
        role: 'assistant',
        content: 'Which one is weighing on you more right now?',
        created_at: '',
        options: [MBA_OPTION, HOUSE_OPTION],
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
        options: [MBA_OPTION, HOUSE_OPTION],
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
        options: [MBA_OPTION, HOUSE_OPTION],
      },
    ];
    const { getByText } = render(Transcript, {
      props: { messages, onOptionSelect: vi.fn(), disabled: true },
    });

    expect(getByText('The MBA').closest('button')).toBeDisabled();
  });
});

// Only the last exchange visible by default, older turns reachable
// (2026-07-21, backlog #237, see engine/decisions.md): a collapse/
// expand affordance, not a fixed-height scrollable pane.
describe('Transcript: last-exchange-only collapse', () => {
  const OLDER_TURN = [
    { role: 'user', content: 'My boss is not willing to grant me the move to the product team.', created_at: '' },
    { role: 'assistant', content: 'What has your boss said about it directly?', created_at: '' },
  ];
  const LAST_TURN = [
    { role: 'user', content: 'He keeps side stepping the conversation.', created_at: '' },
    { role: 'assistant', content: 'What do you think is behind the side stepping?', created_at: '' },
  ];

  it('hides everything before the last exchange behind a "Show earlier" toggle by default', () => {
    const { getByText, queryByText } = render(Transcript, {
      props: { messages: [...OLDER_TURN, ...LAST_TURN], onOptionSelect: vi.fn(), disabled: false },
    });

    expect(queryByText('What has your boss said about it directly?')).toBeNull();
    expect(getByText('He keeps side stepping the conversation.')).toBeTruthy();
    expect(getByText('What do you think is behind the side stepping?')).toBeTruthy();
    expect(getByText('Show earlier in this Journey')).toBeTruthy();
  });

  it('reveals the older turn when "Show earlier" is tapped, and stays open', async () => {
    const { getByText, queryByText } = render(Transcript, {
      props: { messages: [...OLDER_TURN, ...LAST_TURN], onOptionSelect: vi.fn(), disabled: false },
    });

    await fireEvent.click(getByText('Show earlier in this Journey'));

    expect(getByText('What has your boss said about it directly?')).toBeTruthy();
    expect(queryByText('Show earlier in this Journey')).toBeNull();
  });

  it('shows no toggle when the whole conversation is only one exchange', () => {
    const { queryByText } = render(Transcript, {
      props: { messages: LAST_TURN, onOptionSelect: vi.fn(), disabled: false },
    });

    expect(queryByText('Show earlier in this Journey')).toBeNull();
  });

  it('treats a mid-flight lone user message (no reply yet) as its own last exchange', () => {
    const messages = [...OLDER_TURN, { role: 'user', content: 'Sending a new message.', created_at: '' }];
    const { getByText, queryByText } = render(Transcript, {
      props: { messages, onOptionSelect: vi.fn(), disabled: false },
    });

    expect(getByText('Sending a new message.')).toBeTruthy();
    expect(queryByText('What has your boss said about it directly?')).toBeNull();
    expect(getByText('Show earlier in this Journey')).toBeTruthy();
  });
});
