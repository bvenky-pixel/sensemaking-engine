import { describe, it, expect } from 'vitest';
import { honestFailureMessage } from '../lib/honestFailure.js';

// Philosophy-conformance category (developer-tooling-and-testing-
// strategy-v1.md Principle 4): every distinct backend pipeline stopping
// point must be tested directly and individually, not assumed to be
// covered incidentally by the successful path.
describe('honestFailureMessage', () => {
  it('gives a distinct message for each failed_stage value', () => {
    const messages = [
      honestFailureMessage('interpretation'),
      honestFailureMessage('judgment'),
      honestFailureMessage('planner'),
      honestFailureMessage('response'),
      honestFailureMessage(null),
    ];
    // judgment and planner intentionally share one message (both mean
    // "understood, but couldn't finish the thought") -- everything else
    // must be distinct.
    const distinct = new Set(messages);
    expect(distinct.size).toBe(4);
  });

  it('never mentions technical/internal vocabulary', () => {
    const banned = ['interpretation', 'judgment', 'planner', 'stage', 'error', 'null'];
    for (const stage of ['interpretation', 'judgment', 'planner', 'response', null]) {
      const message = honestFailureMessage(stage).toLowerCase();
      for (const word of banned) {
        expect(message).not.toContain(word);
      }
    }
  });
});
