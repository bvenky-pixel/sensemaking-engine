<script>
  // Home's decorative hero orb (2026-07-18, see frontend/decisions.md
  // "Home hero: orb + inline modes") -- fills the mostly-empty space a
  // new or journey-less Home screen used to leave with nothing but one
  // button, per direct founder feedback ("since we are leaving most of
  // the page empty how can we use it better").
  //
  // Same breathing-cycle math as components/AmbientPresence.svelte,
  // duplicated rather than shared -- this codebase's own "small utility
  // functions deliberately duplicated across modules rather than
  // shared, to avoid cross-module coupling" convention (see
  // src/orchestrator/modes.py's own module docstring for the backend-
  // side precedent this follows). Genuinely simpler here, not just a
  // copy: no pulseCount/slowdown mechanic, because nothing on Home is
  // "considering" anything -- AmbientPresence's own docstring explains
  // that mechanic exists specifically to reflect real backend stage-
  // completion events during a live turn, which Home never has. This
  // is pure ambient decoration (aria-hidden, no role="status") -- a
  // calm, alive focal point, not a status indicator.
  //
  // "Buddhist zen vibe" (2026-07-18, see frontend/decisions.md "Orb as
  // consciousness"): direct founder framing -- "the orb is Confidant,
  // it is consciousness" -- so this is the one place in the app that
  // gets to look like it, rather than only behave like it (breathing).
  // Two additions, both purely visual, no change to the pulse mechanic
  // above: an enso (the traditional zen brush-stroke circle -- an
  // intentionally incomplete ring, not a flaw to fix) drawn as a static
  // SVG behind the breathing core, and a slower cycle than before --
  // AmbientPresence stays at 5000ms (that orb is honestly reporting live
  // backend activity, not meditating), but nothing is "happening" here
  // to report, so a longer, calmer breath reads truer to the vibe asked
  // for.
  //
  // `compact` (2026-07-18, see frontend/decisions.md "The orb stays"):
  // direct founder feedback -- "once the first response comes in the
  // orb suddenly disappears, this is jarring, let's continue having the
  // orb." Journey.svelte now keeps a small idle orb in the same slot
  // AmbientPresence occupies while sending, for the entire rest of the
  // conversation, rather than showing nothing between turns. `compact`
  // renders at AmbientPresence's own 72px/36px sizing (no enso -- the
  // brush-stroke ring is the one reflective, attention-holding moment,
  // right for Home's hero; this is a small, recurring companion that
  // shouldn't compete with the transcript for attention turn after
  // turn) so the transition between idle-BreathingOrb and active-
  // AmbientPresence in the same spot is a change in intensity, not a
  // size jump.
  import { onDestroy } from 'svelte';

  let { compact = false } = $props();

  const CYCLE_MS = 7000;

  let dotEl;
  let glowEl;
  let rafHandle = null;
  let elapsed = 0;
  let lastFrameTime = null;
  let reducedMotion = $state(false);

  function tick(now) {
    if (lastFrameTime === null) lastFrameTime = now;
    const delta = now - lastFrameTime;
    lastFrameTime = now;
    elapsed += delta;
    const phase = (elapsed % CYCLE_MS) / CYCLE_MS;
    const eased = (1 - Math.cos(phase * 2 * Math.PI)) / 2;
    if (dotEl) {
      dotEl.style.transform = `scale(${(0.85 + eased * 0.3).toFixed(3)})`;
      dotEl.style.opacity = (0.7 + eased * 0.3).toFixed(3);
    }
    if (glowEl) {
      glowEl.style.transform = `scale(${(1.2 + eased * 0.5).toFixed(3)})`;
      glowEl.style.opacity = (0.25 + eased * 0.25).toFixed(3);
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

  onDestroy(() => {
    if (rafHandle) cancelAnimationFrame(rafHandle);
  });
</script>

<div class="hero-orb" class:compact aria-hidden="true">
  {#if !compact}
    <svg class="enso" viewBox="0 0 100 100">
      <circle class="enso-ring" cx="50" cy="50" r="46" />
    </svg>
  {/if}
  <div class="glow" class:reduced={reducedMotion} bind:this={glowEl}></div>
  <div class="core" class:reduced={reducedMotion} bind:this={dotEl}></div>
</div>

<style>
  .hero-orb {
    position: relative;
    width: 108px;
    height: 108px;
    margin: 0 auto var(--space-3);
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .hero-orb.compact {
    width: 72px;
    height: 72px;
    margin: 0;
  }

  /* The enso -- one brush stroke, deliberately not a closed circle
     (the gap is the point: wholeness that doesn't need to be
     perfect). Static, not breathing -- stillness is part of the
     vibe too, a fixed frame around the one thing in this component
     that moves. --ink-muted rather than --accent so it reads as ink,
     not as another light source competing with the glow. */
  .enso {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
  }

  .enso-ring {
    fill: none;
    stroke: var(--ink-muted);
    stroke-width: 2.5;
    stroke-linecap: round;
    stroke-dasharray: 255 289;
    transform: rotate(-56deg);
    transform-origin: 50px 50px;
    opacity: 0.32;
  }

  .glow {
    position: absolute;
    width: 88px;
    height: 88px;
    border-radius: 50%;
    background: radial-gradient(circle, var(--accent) 0%, transparent 70%);
    filter: blur(10px);
    opacity: 0.3;
  }

  .compact .glow {
    width: 72px;
    height: 72px;
  }

  .glow.reduced {
    opacity: 0.22;
  }

  .core {
    position: relative;
    width: 48px;
    height: 48px;
    border-radius: 50%;
    background: radial-gradient(circle at 35% 30%, #FFD4BE, var(--accent) 70%);
    opacity: 0.85;
  }

  .compact .core {
    width: 36px;
    height: 36px;
  }

  .core.reduced {
    opacity: 0.75;
  }
</style>
