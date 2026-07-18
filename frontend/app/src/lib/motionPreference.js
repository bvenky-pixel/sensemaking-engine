// Reduce motion (2026-07-18, see frontend/decisions.md "Reduce motion,
// as a real setting"): BreathingOrb.svelte and AmbientPresence.svelte
// already respected the OS-level `prefers-reduced-motion` media query,
// but had no in-app way to ask for it independently -- direct founder
// request, "add a toggle for it in settings."
//
// Deliberately one-directional: an app-level toggle can only ADD the
// reduced-motion treatment, never remove it. A person whose OS already
// says reduce motion never has that overridden by Confidant's own
// setting being left off -- this app has no way to know why someone's
// system asks for reduced motion, so it only ever agrees or defers,
// never contradicts.
//
// Plain localStorage, not a backend field -- this app has no user
// accounts/auth anywhere yet (see src/api/db.py's own "single-user
// simplification" note), so there's no server-side place for a
// per-person preference to live. Read fresh on each component mount
// (BreathingOrb/AmbientPresence's own existing $effect already runs
// once per mount) rather than a live cross-screen store -- App.svelte
// fully unmounts/remounts each screen on navigation (see its own {#if
// screen === ...} routing), so returning to Home/Journey after
// changing this in Settings already re-reads it correctly with no
// extra plumbing.
const STORAGE_KEY = 'confidant:reduce-motion';

export function getReduceMotionOverride() {
  return localStorage.getItem(STORAGE_KEY) === 'true';
}

export function setReduceMotionOverride(value) {
  if (value) {
    localStorage.setItem(STORAGE_KEY, 'true');
  } else {
    localStorage.removeItem(STORAGE_KEY);
  }
}

export function prefersReducedMotion() {
  return getReduceMotionOverride() || window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

// Mirrors the current preference onto <html data-reduce-motion> so
// tokens.css's app-wide transition/animation rule (the same one that
// already reacts to the OS-level media query) can react to the app-
// level override too, without every CSS `transition:`/svelte
// `transition:fade`/`fly` call site needing to import and check this
// module individually. Called once at startup (main.js) and again
// right after the Settings toggle changes, so the effect is immediate
// in the current tab -- not just on the next reload/navigation.
export function applyReduceMotionAttribute() {
  document.documentElement.toggleAttribute('data-reduce-motion', prefersReducedMotion());
}
