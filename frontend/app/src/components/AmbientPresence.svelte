<script>
  // The concrete form of v4's Ambient Presence signal (see
  // frontend/specs/screen-design-v1.md): one continuous wordless
  // signal, paced like a slow breath, carrying no report of what stage
  // of reasoning is happening -- no percentage, no stage labels, no
  // text (see frontend/specs/motion-and-latency-philosophy-v1.md).
  //
  // Major update (2026-07-11, see engine/decisions.md "Major update"
  // Part 5): the backend can now report real stage-completion moments
  // (GET /sessions/{id}/stream, one event per pipeline stage), which
  // the philosophy doc's own "Future Considerations" section named as
  // its amendment trigger. Rejected design: a discrete visual pulse per
  // stage (deepen/reset the breath on each event) -- with real
  // inter-stage gaps of ~2-5s, four visually distinct pulses are
  // learnable, which a returning person could subconsciously count --
  // functionally a step-counter even unlabeled, violating Principle 4
  // ("never imply a countable, measurable task"). Chosen instead: the
  // breathing dot stays visually identical in shape; its cadence is now
  // JS-driven rather than a fixed CSS clock, and each real stage-
  // complete event gives the CURRENT breath phase a small, bounded,
  // imperceptible extension -- genuinely paced by backend activity
  // (honest per Principle 3) with no discrete countable tick a person
  // could ever enumerate.
  //
  // This component deliberately does NOT open the stream itself:
  // Journey.svelte's handleSend opens it synchronously, in the same
  // call as the POST that starts the turn, and passes stage arrivals
  // down as an incrementing `pulseCount` -- opening it here instead
  // would race Svelte's own render timing (this component only mounts
  // after `sending` flips true, which happens on a later microtask than
  // the POST fetch already being dispatched), risking missing the
  // "interpretation" stage's event on every single turn.
  import { onDestroy } from 'svelte';

  let { pulseCount = 0 } = $props();

  const CYCLE_MS = 5000;
  // A stage-complete event slows the clock briefly rather than jumping
  // the dot -- bounded and decaying, capped so several close-together
  // events can't produce a long, learnable slow patch (at most ~20% of
  // one full cycle, matching the "10-20% of the current inhale/exhale"
  // design bound).
  const SLOWDOWN_FACTOR = 0.8;
  const SLOWDOWN_MS = 600;
  const MAX_SLOWDOWN_MS = 1000;

  let dotEl;
  let rafHandle = null;
  let virtualElapsed = 0;
  let lastFrameTime = null;
  let slowdownRemaining = 0;
  let reducedMotion = $state(false);
  let isFirstPulseRun = true;

  function tick(now) {
    if (lastFrameTime === null) lastFrameTime = now;
    const delta = now - lastFrameTime;
    lastFrameTime = now;

    const factor = slowdownRemaining > 0 ? SLOWDOWN_FACTOR : 1;
    if (slowdownRemaining > 0) slowdownRemaining = Math.max(0, slowdownRemaining - delta);

    virtualElapsed += delta * factor;
    const phase = (virtualElapsed % CYCLE_MS) / CYCLE_MS;
    // Same ease-in-out shape as the original CSS keyframe: 0.85 -> 1.15
    // scale, 0.25 -> 0.5 opacity, peaking at the midpoint of the cycle.
    const eased = (1 - Math.cos(phase * 2 * Math.PI)) / 2;
    if (dotEl) {
      dotEl.style.transform = `scale(${(0.85 + eased * 0.3).toFixed(3)})`;
      dotEl.style.opacity = (0.25 + eased * 0.25).toFixed(3);
    }
    rafHandle = requestAnimationFrame(tick);
  }

  $effect(() => {
    reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reducedMotion) return;
    rafHandle = requestAnimationFrame(tick);
    return () => {
      if (rafHandle) cancelAnimationFrame(rafHandle);
      rafHandle = null;
    };
  });

  $effect(() => {
    pulseCount; // eslint-disable-line -- tracked so this effect reruns per pulse
    if (isFirstPulseRun) {
      isFirstPulseRun = false;
    } else {
      slowdownRemaining = Math.min(slowdownRemaining + SLOWDOWN_MS, MAX_SLOWDOWN_MS);
    }
  });

  onDestroy(() => {
    if (rafHandle) cancelAnimationFrame(rafHandle);
  });
</script>

<div class="ambient-presence" role="status" aria-label="Confidant is considering what you shared">
  <div class="breath" class:reduced={reducedMotion} bind:this={dotEl}></div>
</div>

<style>
  .ambient-presence {
    display: flex;
    justify-content: flex-start;
    padding: var(--space-2) 0;
  }

  .breath {
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: var(--accent);
    opacity: 0.4;
  }

  .breath.reduced {
    opacity: 0.35;
  }
</style>
