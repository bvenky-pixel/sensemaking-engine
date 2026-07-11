import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/svelte';
import Understanding from '../components/Understanding.svelte';

// Philosophy-conformance (frontend-philosophy-v1.md /
// trust-and-privacy-ux-v1.md): the understanding region must never leak
// raw backend vocabulary to the person using it.
describe('Understanding', () => {
  const brief = {
    situation: 'You are weighing a job offer against staying put.',
    key_insights: ['The new role would mean relocating within three months.'],
    current_direction: 'Leaning toward staying, but not certain yet.',
    remaining_unknowns: ['What the new team actually looks like day to day'],
    decisions: ['Whether to accept the offer'],
    secondary_issues: ['You mentioned the commute a few times without dwelling on it.'],
    stagnation_notes: ['This has sat without a change for a few turns now.'],
  };

  it('renders the brief content without raw backend vocabulary', () => {
    const { container } = render(Understanding, {
      props: { brief, deepeningClarityNote: '' },
    });
    const text = container.textContent.toLowerCase();
    const banned = ['confidence', 'judgment', 'epistemic', 'primary_problem', 'world_state', 'json'];
    for (const word of banned) {
      expect(text).not.toContain(word);
    }
  });

  it('renders nothing when there is no brief yet', () => {
    const { container } = render(Understanding, {
      props: { brief: null, deepeningClarityNote: '' },
    });
    expect(container.textContent.trim()).toBe('');
  });

  it('surfaces the deepening-clarity callout when present', () => {
    const { getByText } = render(Understanding, {
      props: { brief, deepeningClarityNote: 'Something has become clearer since last time.' },
    });
    expect(getByText('Something has become clearer since last time.')).toBeTruthy();
  });

  it('renders key_insights in their own card (major update: previously sent by the API but never rendered)', () => {
    const { getByText } = render(Understanding, {
      props: { brief, deepeningClarityNote: '' },
    });
    expect(getByText('What matters here')).toBeTruthy();
    expect(
      getByText('The new role would mean relocating within three months.')
    ).toBeTruthy();
  });

  it('omits the key_insights card entirely when the list is empty', () => {
    const { queryByText } = render(Understanding, {
      props: { brief: { ...brief, key_insights: [] }, deepeningClarityNote: '' },
    });
    expect(queryByText('What matters here')).toBeNull();
  });
});
