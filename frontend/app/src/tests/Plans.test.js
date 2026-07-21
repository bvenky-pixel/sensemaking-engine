import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/svelte';
import Plans from '../screens/Plans.svelte';

// Plans tab placeholder (2026-07-21, direct founder instruction, see
// engine/decisions.md "Tab order: You, Activity, +, Plans, Settings") --
// nothing built yet, just an honest "Coming soon" claiming the tab's spot.
describe('Plans', () => {
  it('shows a coming-soon message and nothing else', () => {
    const { getByText } = render(Plans, { props: {} });

    expect(getByText('Plans')).toBeTruthy();
    expect(getByText('Coming soon.')).toBeTruthy();
  });
});
