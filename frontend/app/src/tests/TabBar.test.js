import { describe, it, expect, vi } from 'vitest';
import { render, fireEvent } from '@testing-library/svelte';
import TabBar from '../components/TabBar.svelte';

// 5-tab navigation shell, reordered and Home retired (2026-07-21, direct
// founder instruction, see engine/decisions.md "Tab order: You, Activity,
// +, Plans, Settings"): You, Activity, [+], Plans, Settings. The center
// action is now also the current-location signal for `active === 'start'`
// (App.svelte's own default), not just a one-way action -- see
// TabBar.svelte's own docstring.
describe('TabBar', () => {
  it('marks the active tab and calls onNavigate for the others', async () => {
    const onNavigate = vi.fn();
    const { getByText } = render(TabBar, {
      props: { active: 'you', onNavigate },
    });

    expect(getByText('You').getAttribute('aria-current')).toBe('page');
    expect(getByText('Activity').getAttribute('aria-current')).toBeNull();

    await fireEvent.click(getByText('Activity'));
    expect(onNavigate).toHaveBeenCalledWith('activity');

    await fireEvent.click(getByText('Plans'));
    expect(onNavigate).toHaveBeenCalledWith('plans');

    await fireEvent.click(getByText('Settings'));
    expect(onNavigate).toHaveBeenCalledWith('settings');
  });

  it('calls onNavigate("start") when the center action is tapped', async () => {
    const onNavigate = vi.fn();
    const { getByLabelText } = render(TabBar, {
      props: { active: 'activity', onNavigate },
    });

    await fireEvent.click(getByLabelText('Begin something new'));

    expect(onNavigate).toHaveBeenCalledWith('start');
  });

  it('marks the center action as active when active is "start"', () => {
    const { getByLabelText, getByText } = render(TabBar, {
      props: { active: 'start', onNavigate: vi.fn() },
    });

    expect(getByLabelText('Begin something new').getAttribute('aria-current')).toBe('page');
    expect(getByText('You').getAttribute('aria-current')).toBeNull();
  });

  it('marks Activity as active and You as not, when active is "activity"', () => {
    const { getByText } = render(TabBar, {
      props: { active: 'activity', onNavigate: vi.fn() },
    });

    expect(getByText('Activity').getAttribute('aria-current')).toBe('page');
    expect(getByText('You').getAttribute('aria-current')).toBeNull();
  });
});
