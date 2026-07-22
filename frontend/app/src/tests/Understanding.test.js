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
    known_facts: [],
    competing_priorities: [],
    contradictions: [],
    emerging_patterns: [],
  };

  it('renders the brief content without raw backend vocabulary', () => {
    const { container } = render(Understanding, {
      props: { brief, whatChanged: [] },
    });
    const text = container.textContent.toLowerCase();
    const banned = ['confidence', 'judgment', 'epistemic', 'primary_problem', 'world_state', 'json'];
    for (const word of banned) {
      expect(text).not.toContain(word);
    }
  });

  it('renders nothing when there is no brief yet', () => {
    const { container } = render(Understanding, {
      props: { brief: null, whatChanged: [] },
    });
    expect(container.textContent.trim()).toBe('');
  });

  // Frontend v2 (2026-07-22, direct founder redirect: "where things
  // stand is just an overall assessment of the situation and does not
  // add much value... I don't really care about the rest") -- the
  // "Where things stand" card (situation/current_direction) is removed
  // entirely, not just relabeled.
  it('never renders a "Where things stand" card even when situation/current_direction are set', () => {
    const { queryByText } = render(Understanding, {
      props: { brief, whatChanged: [] },
    });
    expect(queryByText('Where things stand')).toBeNull();
    expect(queryByText(brief.situation)).toBeNull();
    expect(queryByText(brief.current_direction)).toBeNull();
  });

  // Major update (2026-07-22, see engine/decisions.md and
  // clarity-brief-specification-v1.md "Decided" section): "what changed"
  // is now server-computed (src/executor/engine.py::diff_clarity_briefs)
  // and can be a real, multi-item list -- replaces the old client-side
  // deepeningClarityNote (a single generic sentence).
  it('surfaces each what_changed item inside the callout', () => {
    const { getByText } = render(Understanding, {
      props: {
        brief,
        whatChanged: [
          'A new contradiction surfaced: X vs. Y.',
          'This has been resolved: What the new team looks like.',
        ],
      },
    });
    expect(getByText('A new contradiction surfaced: X vs. Y.')).toBeTruthy();
    expect(getByText('This has been resolved: What the new team looks like.')).toBeTruthy();
  });

  it('renders no callout when what_changed is empty', () => {
    const { container } = render(Understanding, {
      props: { brief, whatChanged: [] },
    });
    expect(container.querySelector('.callout')).toBeNull();
  });

  it('renders key_insights in their own card (major update: previously sent by the API but never rendered)', () => {
    const { getByText } = render(Understanding, {
      props: { brief, whatChanged: [] },
    });
    expect(getByText('What matters here')).toBeTruthy();
    expect(
      getByText('The new role would mean relocating within three months.')
    ).toBeTruthy();
  });

  it('omits the key_insights card entirely when the list is empty', () => {
    const { queryByText } = render(Understanding, {
      props: { brief: { ...brief, key_insights: [] }, whatChanged: [] },
    });
    expect(queryByText('What matters here')).toBeNull();
  });

  // Added 2026-07-22 (see engine/decisions.md and
  // clarity-brief-specification-v1.md "The Eight Sections"): three new
  // ClarityBrief sections, each with its own casual heading (no raw
  // field names), same settled-card treatment as key_insights/decisions.
  it('renders known_facts in their own card', () => {
    const { getByText } = render(Understanding, {
      props: { brief: { ...brief, known_facts: ['You have two years of runway saved.'] }, whatChanged: [] },
    });
    expect(getByText('What I know')).toBeTruthy();
    expect(getByText('You have two years of runway saved.')).toBeTruthy();
  });

  it('omits the known_facts card entirely when the list is empty', () => {
    const { queryByText } = render(Understanding, {
      props: { brief, whatChanged: [] },
    });
    expect(queryByText('What I know')).toBeNull();
  });

  it('renders competing_priorities in their own card', () => {
    const { getByText } = render(Understanding, {
      props: {
        brief: { ...brief, competing_priorities: ['Autonomy vs. protecting the relationship.'] },
        whatChanged: [],
      },
    });
    expect(getByText('Pulling you in different directions')).toBeTruthy();
    expect(getByText('Autonomy vs. protecting the relationship.')).toBeTruthy();
  });

  it('omits the competing_priorities card entirely when the list is empty', () => {
    const { queryByText } = render(Understanding, {
      props: { brief, whatChanged: [] },
    });
    expect(queryByText('Pulling you in different directions')).toBeNull();
  });

  it('renders contradictions in their own card', () => {
    const { getByText } = render(Understanding, {
      props: {
        brief: { ...brief, contradictions: ['Manager says great, but passed over.'] },
        whatChanged: [],
      },
    });
    expect(getByText('Worth a second look')).toBeTruthy();
    expect(getByText('Manager says great, but passed over.')).toBeTruthy();
  });

  it('omits the contradictions card entirely when the list is empty', () => {
    const { queryByText } = render(Understanding, {
      props: { brief, whatChanged: [] },
    });
    expect(queryByText('Worth a second look')).toBeNull();
  });

  // Frontend v2 (2026-07-22, direct founder redirect: "putting it
  // together is not as valuable as it looks like we are literally
  // putting together my words") -- the tier2-sourced "Putting it
  // together" card, and the `tier2` prop itself, are removed entirely.
  it('never renders a "Putting it together" card even when tier2 content is passed', () => {
    const tier2 = [
      { id: 'tier2:1', tier: 2, kind: 'synthesis', text: 'Your decision may hinge on an unexamined assumption.', grounding_item_ids: ['a', 'b'] },
    ];
    const { queryByText } = render(Understanding, {
      props: { brief, tier2, whatChanged: [] },
    });
    expect(queryByText('Putting it together')).toBeNull();
    expect(queryByText('Your decision may hinge on an unexamined assumption.')).toBeNull();
  });
});
