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
  import { onDestroy } from 'svelte';

  const CYCLE_MS = 5000;

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

<div class="hero-orb" aria-hidden="true">
  <div class="glow" class:reduced={reducedMotion} bind:this={glowEl}></div>
  <div class="core" class:reduced={reducedMotion} bind:this={dotEl}></div>
</div>

<style>
  .hero-orb {
    position: relative;
    width: 88px;
    height: 88px;
    margin: 0 auto var(--space-3);
    display: flex;
    align-items: center;
    justify-content: center;
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

  .core.reduced {
    opacity: 0.75;
  }
</style>
