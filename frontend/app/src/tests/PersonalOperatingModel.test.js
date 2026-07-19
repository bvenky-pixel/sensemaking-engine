import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, waitFor } from '@testing-library/svelte';
import PersonalOperatingModel from '../components/PersonalOperatingModel.svelte';
import * as api from '../lib/api.js';

// POM surfaced to users (2026-07-18, see frontend/decisions.md "POM
// surfaced to users"). Mocking lib/api.js matches every other
// component test's own boundary.
vi.mock('../lib/api.js', () => ({
  getPersonalOperatingModel: vi.fn(),
  submitPomFeedback: vi.fn(),
}));

const EMPTY_POM = {
  belief: { beliefs: [] },
  relationship: { relationships: [] },
  identity: { self_concept: '', evidence: [] },
  motivation: {
    autonomy: 'unclear', autonomy_evidence: [],
    competence: 'unclear', competence_evidence: [],
    relatedness: 'unclear', relatedness_evidence: [],
  },
  learning_style: { style: '', evidence: [] },
  stress: { level: 'unclear', evidence: [] },
  narrative: { arc: 'unclear', summary: '', evidence: [] },
  theory_of_mind: { entries: [] },
};

const POPULATED_POM = {
  computed_at: '2026-07-19T00:00:00',
  belief: { beliefs: ['Believes hard work should be rewarded with recognition.'] },
  relationship: { relationships: ['Manager -- role is manager; has final say on transfers.'] },
  identity: { self_concept: 'Sees themselves as someone who values independence at work.', evidence: ['said so directly'] },
  motivation: {
    autonomy: 'high', autonomy_evidence: ['Chose to restructure the project alone.'],
    competence: 'unclear', competence_evidence: [],
    relatedness: 'moderate', relatedness_evidence: ['Checks in with the team before big changes.'],
  },
  learning_style: { style: 'Learns best by trying something and adjusting from what happens.', evidence: ['tried the new process before asking questions'] },
  stress: { level: 'moderate', evidence: ['Mentioned feeling stretched thin this month.'] },
  narrative: { arc: 'redemptive', summary: 'Moved from a difficult transfer denial toward real clarity about what they want next.', evidence: ['from denial to clarity'] },
  theory_of_mind: {
    entries: [
      { entity_name: 'Sarah', inferred_perspective: 'Seems supportive of the move, though cautious about timing.', evidence: ['Sarah said "let\'s wait and see"'] },
    ],
  },
};

describe('PersonalOperatingModel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows a quiet placeholder when nothing has been computed yet', async () => {
    api.getPersonalOperatingModel.mockResolvedValue(null);
    const { getByText, queryByText } = render(PersonalOperatingModel);

    await waitFor(() => getByText('Nothing standing yet -- this builds up the more we talk.'));
    expect(queryByText('What you\'ve told me you believe')).toBeNull();
  });

  it('shows the same quiet placeholder when POM exists but every system is still unclear/empty', async () => {
    api.getPersonalOperatingModel.mockResolvedValue(EMPTY_POM);
    const { getByText } = render(PersonalOperatingModel);

    await waitFor(() => getByText('Nothing standing yet -- this builds up the more we talk.'));
  });

  it('renders every populated system, using real evidence prose rather than raw category labels', async () => {
    api.getPersonalOperatingModel.mockResolvedValue(POPULATED_POM);
    const { getByText, queryByText } = render(PersonalOperatingModel);

    await waitFor(() => getByText("What you've told me you believe"));
    expect(getByText('Believes hard work should be rewarded with recognition.')).toBeTruthy();

    expect(getByText('People who come up')).toBeTruthy();
    expect(getByText('Manager -- role is manager; has final say on transfers.')).toBeTruthy();

    expect(getByText('How you seem to see yourself')).toBeTruthy();
    expect(getByText('Sees themselves as someone who values independence at work.')).toBeTruthy();

    expect(getByText('What seems to drive you')).toBeTruthy();
    expect(getByText('Doing things your own way.')).toBeTruthy();
    expect(getByText('Chose to restructure the project alone.')).toBeTruthy();
    expect(getByText('Feeling connected to others.')).toBeTruthy();
    // Competence is "unclear" with no evidence -- must not appear.
    expect(queryByText('Feeling capable and effective.')).toBeNull();

    expect(getByText('How you seem to learn and take things in')).toBeTruthy();
    expect(getByText('Learns best by trying something and adjusting from what happens.')).toBeTruthy();

    expect(getByText('Stress')).toBeTruthy();
    expect(getByText('Mentioned feeling stretched thin this month.')).toBeTruthy();

    expect(getByText('The shape of your story so far')).toBeTruthy();
    expect(getByText('Moved from a difficult transfer denial toward real clarity about what they want next.')).toBeTruthy();

    expect(getByText("What I've noticed about people in your life")).toBeTruthy();
    expect(getByText('Sarah:')).toBeTruthy();
    expect(getByText('Seems supportive of the move, though cautious about timing.')).toBeTruthy();

    // No raw ConfidenceLevel/arc vocabulary anywhere on screen.
    expect(queryByText(/moderate/i)).toBeNull();
    expect(queryByText(/unclear/i)).toBeNull();
    expect(queryByText(/redemptive/i)).toBeNull();
  });

  it('shows when this was last computed (backlog #271, computed_at staleness signal)', async () => {
    api.getPersonalOperatingModel.mockResolvedValue(POPULATED_POM);
    const { findByText } = render(PersonalOperatingModel);

    expect(await findByText(/Last updated/)).toBeTruthy();
  });

  it('omits the last-updated line when computed_at is empty (e.g. a stale fixture)', async () => {
    api.getPersonalOperatingModel.mockResolvedValue({ ...POPULATED_POM, computed_at: '' });
    const { queryByText, getByText } = render(PersonalOperatingModel);

    await waitFor(() => getByText("What you've told me you believe"));
    expect(queryByText(/Last updated/)).toBeNull();
  });

  it('renders the affirm/correct affordance next to every populated statement', async () => {
    api.getPersonalOperatingModel.mockResolvedValue(POPULATED_POM);
    const { getByText, getAllByText } = render(PersonalOperatingModel);

    await waitFor(() => getByText("What you've told me you believe"));
    // One "Sounds right"/"Not quite" pair per rendered statement (belief,
    // relationship, identity, autonomy, relatedness, learning_style,
    // stress, narrative, theory_of_mind = 9 statements in POPULATED_POM).
    expect(getAllByText('Sounds right').length).toBe(9);
    expect(getAllByText('Not quite').length).toBe(9);
  });

  it('omits a system entirely when it has nothing grounded, even if others are populated', async () => {
    api.getPersonalOperatingModel.mockResolvedValue({
      ...EMPTY_POM,
      identity: { self_concept: 'Values independence at work.', evidence: ['said so'] },
    });
    const { getByText, queryByText } = render(PersonalOperatingModel);

    await waitFor(() => getByText('How you seem to see yourself'));
    expect(queryByText("What you've told me you believe")).toBeNull();
    expect(queryByText('People who come up')).toBeNull();
    expect(queryByText('What seems to drive you')).toBeNull();
    expect(queryByText('Stress')).toBeNull();
    expect(queryByText('Nothing standing yet -- this builds up the more we talk.')).toBeNull();
  });
});
