import { describe, it, expect } from 'vitest';
import { noteDeepeningClarity } from '../lib/deepeningClarity.js';

describe('noteDeepeningClarity', () => {
  it('produces no note on the first fetch (no previous brief to compare)', () => {
    const next = { remaining_unknowns: [], decisions: [] };
    expect(noteDeepeningClarity(null, next)).toBe('');
  });

  it('produces no note when nothing changed', () => {
    const previous = { remaining_unknowns: ['a', 'b'], decisions: ['x'] };
    const next = { remaining_unknowns: ['a', 'b'], decisions: ['x'] };
    expect(noteDeepeningClarity(previous, next)).toBe('');
  });

  it('fires exactly one note when an unknown resolves', () => {
    const previous = { remaining_unknowns: ['a', 'b'], decisions: [] };
    const next = { remaining_unknowns: ['a'], decisions: [] };
    const note = noteDeepeningClarity(previous, next);
    expect(note).not.toBe('');
    expect(note.toLowerCase()).not.toContain('unknown');
    expect(note.toLowerCase()).not.toContain('remaining_unknowns');
  });

  it('does not fire on a decisions-list change alone (no status in the brief to compare)', () => {
    // build_clarity_brief lists all decisions regardless of status, so a
    // decision resolving doesn't shrink this array -- confirms we don't
    // falsely fire on it when it does happen to change length.
    const previous = { remaining_unknowns: [], decisions: ['open'] };
    const next = { remaining_unknowns: [], decisions: [] };
    expect(noteDeepeningClarity(previous, next)).toBe('');
  });
});
