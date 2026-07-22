// Accent color picker (2026-07-21, direct founder instruction: "add an
// option in settings where users can choose and change the color of
// the orb and as a result the whole UI. Default remains the current
// color.") -- same shape as motionPreference.js's own established
// pattern for an app-level visual preference: plain localStorage (this
// app has no user accounts/auth field this could live on server-side
// yet -- see src/api/db.py's own "single-user simplification" note),
// applied by toggling a `<html>` attribute that tokens.css reacts to
// (data-accent-theme, mirroring data-reduce-motion), read fresh at
// startup and re-applied immediately after the Settings picker changes
// rather than requiring a reload.
//
// Five choices total, not an open color picker -- reuses the four
// existing mode-tint colors (see modeTints.js) as the non-default
// options, so this feature introduces zero new hex values needing
// their own light/dark pair; "coral" is simply the absence of the
// attribute, since that's --accent's own base definition already.
const STORAGE_KEY = 'confidant:accent-theme';

export const ACCENT_THEMES = [
  { id: 'coral', label: 'Coral (default)', previewVar: '--accent-default' },
  { id: 'periwinkle', label: 'Periwinkle', previewVar: '--accent-2' },
  { id: 'sage', label: 'Sage', previewVar: '--accent-3' },
  { id: 'lavender', label: 'Lavender', previewVar: '--accent-4' },
  { id: 'gold', label: 'Gold', previewVar: '--accent-5' },
];

const THEME_IDS = ACCENT_THEMES.map((t) => t.id);

export function getAccentTheme() {
  const stored = localStorage.getItem(STORAGE_KEY);
  return THEME_IDS.includes(stored) ? stored : 'coral';
}

export function setAccentTheme(theme) {
  if (theme === 'coral') {
    localStorage.removeItem(STORAGE_KEY);
  } else {
    localStorage.setItem(STORAGE_KEY, theme);
  }
}

// Mirrors the current preference onto <html data-accent-theme>, same
// "called once at startup, again immediately after the setting changes"
// pattern as applyReduceMotionAttribute -- see that function's own
// comment. Coral removes the attribute entirely rather than setting
// data-accent-theme="coral", since tokens.css has no rule for that
// value anyway (the default needs no override to apply).
export function applyAccentTheme() {
  const theme = getAccentTheme();
  if (theme === 'coral') {
    document.documentElement.removeAttribute('data-accent-theme');
  } else {
    document.documentElement.setAttribute('data-accent-theme', theme);
  }
}
