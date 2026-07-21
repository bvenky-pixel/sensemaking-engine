import { describe, it, expect, vi } from 'vitest';
import { render, fireEvent } from '@testing-library/svelte';
import TabBar from '../components/TabBar.svelte';

// 5-tab navigation shell (2026-07-21, backlog #261, see
// information-architecture-v2.md): four persistent destinations plus
// one center navigation ACTION (starts a new Journey), not a fifth
// destination -- see TabBar.svelte's own docstring.
describe('TabBar', () => {
  it('marks the active tab and calls onNavigate for the others', async () => {
    const onNavigate = vi.fn();
    const { getByText } = render(TabBar, {
      props: { active: 'home', onNavigate, onBeginNew: vi.fn() },
    });

    expect(getByText('Home').getAttribute('aria-current')).toBe('page');
    expect(getByText('Activity').getAttribute('aria-current')).toBeNull();

    await fireEvent.click(getByText('Activity'));
    expect(onNavigate).toHaveBeenCalledWith('activity');

    await fireEvent.click(getByText('You'));
    expect(onNavigate).toHaveBeenCalledWith('you');

    await fireEvent.click(getByText('Settings'));
    expect(onNavigate).toHaveBeenCalledWith('settings');
  });

  it('calls onBeginNew, not onNavigate, when the center action is tapped', async () => {
    const onNavigate = vi.fn();
    const onBeginNew = vi.fn();
    const { getByLabelText } = render(TabBar, {
      props: { active: 'activity', onNavigate, onBeginNew },
    });

    await fireEvent.click(getByLabelText('Begin something new'));

    expect(onBeginNew).toHaveBeenCalled();
    expect(onNavigate).not.toHaveBeenCalled();
  });

  it('marks Activity as active and Home as not, when active is "activity"', () => {
    const { getByText } = render(TabBar, {
      props: { active: 'activity', onNavigate: vi.fn(), onBeginNew: vi.fn() },
    });

    expect(getByText('Activity').getAttribute('aria-current')).toBe('page');
    expect(getByText('Home').getAttribute('aria-current')).toBeNull();
  });
});
