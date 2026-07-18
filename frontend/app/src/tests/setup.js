import '@testing-library/jest-dom/vitest';

// Warm & Alive redesign (see frontend/decisions.md) introduced
// svelte/transition (fade/fly) across several components -- Svelte's
// transition implementation calls the real DOM Element.animate() (Web
// Animations API), which jsdom doesn't implement. Without this
// polyfill, any component using transition:/in:/out: throws
// "element.animate is not a function" during render in tests. This is
// jsdom's own known gap, not a real bug -- the minimal fake below gives
// Svelte's transition code enough of the Animation interface
// (cancel/finished/pause/play/finish) to run to completion synchronously
// in tests, which is all a test needs (it doesn't need to observe the
// actual visual animation).
if (typeof Element !== 'undefined' && !Element.prototype.animate) {
  Element.prototype.animate = function () {
    return {
      cancel: () => {},
      finish: () => {},
      pause: () => {},
      play: () => {},
      reverse: () => {},
      persist: () => {},
      commitStyles: () => {},
      updatePlaybackRate: () => {},
      currentTime: 0,
      playState: 'finished',
      onfinish: null,
      oncancel: null,
      finished: Promise.resolve(),
    };
  };
}
