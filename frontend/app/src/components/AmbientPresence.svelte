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
  import { prefersReducedMotion } from '../lib/motionPreference.js';

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
  let glowEl;
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
    // Same ease-in-out shape as before -- only the visual scale/opacity
    // RANGE changed (v2 "Warm & Alive" redesign, see
    // frontend/decisions.md): a bigger, softer glowing orb instead of a
    // 14px dot, so the same honest, bounded, wordless breathing signal
    // now reads as genuinely alive rather than a barely-visible tick.
    //
    // Round 2 (2026-07-18, "use it similar to Claude during chat to let
    // users know things are happening" -- see frontend/decisions.md
    // "Orb, round two"): grown again, from a 40px orb to 72px (see
    // .orb-wrap below) -- same math here, just a wider scale/opacity
    // swing so the bigger element still reads as breathing, not static.
    const eased = (1 - Math.cos(phase * 2 * Math.PI)) / 2;
    if (dotEl) {
      dotEl.style.transform = `scale(${(0.82 + eased * 0.34).toFixed(3)})`;
      dotEl.style.opacity = (0.6 + eased * 0.4).toFixed(3);
    }
    if (glowEl) {
      // Outer glow trails the core by design -- a slightly larger,
      // slower-feeling halo reads as a soft light source, not a second
      // countable pulse (still driven by the exact same phase/eased
      // value, so it can never desync into its own learnable rhythm).
      glowEl.style.transform = `scale(${(1.3 + eased * 0.5).toFixed(3)})`;
      glowEl.style.opacity = (0.22 + eased * 0.26).toFixed(3);
    }
    rafHandle = requestAnimationFrame(tick);
  }

  $effect(() => {
    reducedMotion = prefersReducedMotion();
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
  <div class="orb-wrap">
    <div class="glow" class:reduced={reducedMotion} bind:this={glowEl}></div>
    <div class="breath" class:reduced={reducedMotion} bind:this={dotEl}></div>
  </div>
</div>

<style>
  .ambient-presence {
    display: flex;
    justify-content: flex-start;
    align-items: center;
    padding: var(--space-3) 0;
  }

  /* Round 2 size (see script comment above): 72px, up from 40px --
     "let users know things are happening" needed genuine visual
     presence in the conversation flow, not something easy to miss
     between messages. Still no text/label next to it (role="status"'s
     aria-label carries that for screen readers only) -- v1's "no
     percentage, no stage labels, no text of any kind" principle is one
     of the ones the Warm & Alive redesign deliberately KEPT, not
     overridden; a bigger orb communicates "something is happening"
     just as honestly as a small one, growing it doesn't invite adding
     words next to it. */
  .orb-wrap {
    position: relative;
    width: 72px;
    height: 72px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  /* The soft halo -- larger, blurred, low-opacity, positioned behind
     the core dot. */
  .glow {
    position: absolute;
    width: 72px;
    height: 72px;
    border-radius: 50%;
    background: radial-gradient(circle, var(--accent) 0%, transparent 70%);
    filter: blur(8px);
    opacity: 0.22;
  }

  .glow.reduced {
    opacity: 0.18;
  }

  /* The core -- a warm gradient orb rather than a flat dot.
     color-mix(), not a fixed peach hex (2026-07-21, see
     engine/decisions.md "Accent color picker") -- same reasoning as
     BreathingOrb.svelte's identical change: this orb needs to relight
     with whichever accent theme is chosen, not stay orange underneath
     a re-tinted glow around it. */
  .breath {
    position: relative;
    width: 36px;
    height: 36px;
    border-radius: 50%;
    background: radial-gradient(circle at 35% 30%, color-mix(in srgb, var(--accent) 45%, white 55%), var(--accent) 70%);
    opacity: 0.75;
  }

  .breath.reduced {
    opacity: 0.65;
  }
</style>
