<script>
  // Kept deliberately small (information-architecture-v1.md): privacy
  // controls, account basics, data management -- nothing else belongs
  // here.
  //
  // Privacy, made real (2026-07-18, see frontend/decisions.md): the
  // section was a static sentence with nothing behind it until now.
  // Three real controls: a toggle for cross-session learning (see
  // src/api/db.py's `privacy_settings` table docstring for exactly
  // what it gates -- Learning/Insight Engine/POM, never anything
  // in-session), a full data export, and "Forget everything" -- the
  // same two-step-confirm pattern Data's per-Journey Remove already
  // established below, just wider in scope (irreversible, deletes
  // every Journey at once, not one). Account remains a placeholder --
  // there is still no auth/user system anywhere in this codebase (see
  // src/api/db.py's own "single-user simplification" note), so
  // populating it with fields would mean building fake account state
  // rather than something real.
  //
  // Data (added 2026-07-15, see engine/decisions.md "Frontend UX
  // pass"): the first of the three sections to get a real control --
  // removing a Journey. Two-step confirm inline (click "Remove" once to
  // ask, again to actually delete) rather than a native `confirm()`
  // dialog, matching this app's own calm, custom-styled aesthetic
  // rather than a browser chrome interruption. Irreversible, same as
  // the backend's own delete_session -- no undo exists yet.
  //
  // Warm & Alive redesign, organizing pass (2026-07-18, see
  // frontend/decisions.md): the three sections previously ran together
  // as loose, unbordered paragraphs -- "messy," per direct founder
  // feedback. Now each is its own card with a small color-coded marker
  // dot, same scannability device ModeSelect already established for
  // its six modes, so a person can tell the three sections apart at a
  // glance rather than reading every label.
  //
  // Reduce motion (2026-07-18, see frontend/decisions.md "Reduce
  // motion, as a real setting"): direct founder request, following a
  // question about whether the breathing orb honored the OS-level
  // accessibility setting -- it did, but had no in-app control of its
  // own. Lives in Account rather than a new fourth section: this is a
  // personal preference about how the app behaves for this person, not
  // a Privacy or Data concern, and information-architecture-v1.md is
  // explicit that these three sections are the whole surface.
  import { onMount } from 'svelte';
  import { fade } from 'svelte/transition';
  import {
    listSessions,
    deleteSession,
    getPrivacySettings,
    setCrossSessionLearningEnabled,
    exportPrivacyData,
    resetAllData,
  } from '../lib/api.js';
  import { getReduceMotionOverride, setReduceMotionOverride, applyReduceMotionAttribute } from '../lib/motionPreference.js';

  let { onBack } = $props();

  let sessions = $state([]);
  let pendingDeleteId = $state(null);
  let reduceMotion = $state(false);
  let crossSessionLearning = $state(true);
  let exporting = $state(false);
  let pendingReset = $state(false);
  let resetting = $state(false);

  onMount(async () => {
    sessions = await listSessions();
    reduceMotion = getReduceMotionOverride();
    const privacy = await getPrivacySettings();
    crossSessionLearning = privacy.cross_session_learning_enabled;
  });

  function toggleReduceMotion() {
    reduceMotion = !reduceMotion;
    setReduceMotionOverride(reduceMotion);
    applyReduceMotionAttribute();
  }

  async function toggleCrossSessionLearning() {
    crossSessionLearning = !crossSessionLearning;
    await setCrossSessionLearningEnabled(crossSessionLearning);
  }

  // Blob -> object URL -> a throwaway <a download> click is the
  // standard browser pattern for triggering a save-file dialog from a
  // fetch response -- no server-side redirect or extra endpoint needed.
  async function handleExport() {
    exporting = true;
    try {
      const blob = await exportPrivacyData();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'confidant-export.json';
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      exporting = false;
    }
  }

  function askToReset() {
    pendingReset = true;
  }

  function cancelReset() {
    pendingReset = false;
  }

  async function confirmReset() {
    resetting = true;
    try {
      await resetAllData();
      sessions = [];
      pendingReset = false;
    } finally {
      resetting = false;
    }
  }

  function askToRemove(sessionId) {
    pendingDeleteId = sessionId;
  }

  function cancelRemove() {
    pendingDeleteId = null;
  }

  async function confirmRemove(sessionId) {
    await deleteSession(sessionId);
    sessions = sessions.filter((s) => s.id !== sessionId);
    pendingDeleteId = null;
  }
</script>

<div class="settings">
  <button type="button" class="back" onclick={onBack}>&larr; Home</button>

  <p class="display">Settings</p>

  <section class="card setting-section">
    <div class="setting-heading">
      <span class="dot" style="--dot-tint: var(--accent-2)"></span>
      <p class="ui-label">Privacy</p>
    </div>
    <p class="setting-body">Controls for what Confidant remembers and how it's used.</p>

    <div class="toggle-row">
      <div>
        <p class="toggle-label">Learn across Journeys</p>
        <p class="toggle-hint">Lets Confidant notice patterns across your Journeys and build a standing sense of who you are over time. Turning this off keeps every Journey completely separate -- nothing said in one is ever used in another.</p>
      </div>
      <button
        type="button"
        class="toggle"
        class:on={crossSessionLearning}
        role="switch"
        aria-checked={crossSessionLearning}
        aria-label="Learn across Journeys"
        onclick={toggleCrossSessionLearning}
      >
        <span class="toggle-thumb"></span>
      </button>
    </div>

    <div class="privacy-actions">
      <button type="button" class="link-button" onclick={handleExport} disabled={exporting}>
        {exporting ? 'Preparing export…' : 'Export your data'}
      </button>

      {#if pendingReset}
        <span class="confirm">
          <span class="voice">Forget everything Confidant knows about you? This can't be undone.</span>
          <button type="button" class="link-button danger" onclick={confirmReset} disabled={resetting}>
            {resetting ? 'Forgetting…' : 'Yes, forget everything'}
          </button>
          <button type="button" class="link-button" onclick={cancelReset}>Cancel</button>
        </span>
      {:else}
        <button type="button" class="link-button danger" onclick={askToReset}>
          Forget everything
        </button>
      {/if}
    </div>
  </section>

  <section class="card setting-section">
    <div class="setting-heading">
      <span class="dot" style="--dot-tint: var(--accent-3)"></span>
      <p class="ui-label">Account</p>
    </div>
    <p class="setting-body">Basic account details.</p>

    <div class="toggle-row">
      <div>
        <p class="toggle-label">Reduce motion</p>
        <p class="toggle-hint">Calms the breathing orb and other motion throughout Confidant, on top of your device's own accessibility setting.</p>
      </div>
      <button
        type="button"
        class="toggle"
        class:on={reduceMotion}
        role="switch"
        aria-checked={reduceMotion}
        aria-label="Reduce motion"
        onclick={toggleReduceMotion}
      >
        <span class="toggle-thumb"></span>
      </button>
    </div>
  </section>

  <section class="card setting-section">
    <div class="setting-heading">
      <span class="dot" style="--dot-tint: var(--accent)"></span>
      <p class="ui-label">Data</p>
    </div>
    {#if sessions.length === 0}
      <p class="setting-body">Nothing shared here yet.</p>
    {:else}
      <ul class="journey-list">
        {#each sessions as session (session.id)}
          <li class="journey-row">
            <span class="preview">{session.preview_text || 'A new Journey'}</span>
            {#if pendingDeleteId === session.id}
              <span class="confirm">
                <span class="voice">Remove this Journey for good?</span>
                <button type="button" class="link-button danger" onclick={() => confirmRemove(session.id)}>
                  Yes, remove it
                </button>
                <button type="button" class="link-button" onclick={cancelRemove}>Cancel</button>
              </span>
            {:else}
              <button type="button" class="link-button" onclick={() => askToRemove(session.id)}>
                Remove
              </button>
            {/if}
          </li>
        {/each}
      </ul>
    {/if}
  </section>
</div>

<style>
  .back {
    display: block;
    margin-bottom: var(--space-3);
  }

  .display {
    margin: 0 0 var(--space-4);
  }

  .setting-section {
    padding: var(--space-3);
    margin-bottom: var(--space-2);
  }

  .setting-heading {
    display: flex;
    align-items: center;
    gap: var(--space-1);
  }

  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--dot-tint);
    flex-shrink: 0;
  }

  .setting-body {
    color: var(--ink-muted);
    margin: var(--space-1) 0 0;
  }

  /* Reduce motion toggle (see script comment) -- a real pill switch,
     not a checkbox, matching the app's rounded, tactile vocabulary
     (--radius-pill is already the same shape as .btn-primary). */
  .toggle-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    margin-top: var(--space-3);
    padding-top: var(--space-2);
    border-top: 1px solid var(--line);
  }

  .toggle-label {
    font-family: var(--font-body);
    color: var(--ink);
    font-weight: 600;
    margin: 0;
  }

  .toggle-hint {
    color: var(--ink-muted);
    font-size: 13px;
    margin: var(--space-1) 0 0;
  }

  .toggle {
    flex-shrink: 0;
    position: relative;
    width: 44px;
    height: 26px;
    border-radius: var(--radius-pill);
    background: var(--line);
    padding: 0;
    transition: background var(--motion-quick) ease-out;
  }

  .toggle.on {
    background: var(--accent);
  }

  .toggle-thumb {
    position: absolute;
    top: 3px;
    left: 3px;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: var(--paper-raised);
    box-shadow: var(--shadow-soft);
    transition: transform var(--motion-smooth);
  }

  .toggle.on .toggle-thumb {
    transform: translateX(18px);
  }

  /* Export/Forget everything (see script comment) -- same row rhythm
     as .toggle-row above (a border-top divider, not a full new card),
     since both are "controls under the Privacy heading," not
     independent sections of their own. */
  .privacy-actions {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--space-2) var(--space-3);
    margin-top: var(--space-3);
    padding-top: var(--space-2);
    border-top: 1px solid var(--line);
  }

  .journey-list {
    list-style: none;
    margin: var(--space-2) 0 0;
    padding: 0;
  }

  .journey-row {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: var(--space-2);
    padding: var(--space-2) 0;
    border-bottom: 1px solid var(--line);
  }

  .journey-row:last-child {
    border-bottom: none;
  }

  .preview {
    font-family: var(--font-body);
    color: var(--ink);
  }

  .link-button {
    flex-shrink: 0;
    font-family: var(--font-ui);
    font-size: 14px;
    font-weight: 700;
    color: var(--ink-muted);
    background: none;
    border: none;
    cursor: pointer;
    padding: 0;
  }

  .confirm {
    display: flex;
    align-items: baseline;
    flex-wrap: wrap;
    gap: var(--space-1) var(--space-2);
    /* min-width: 0 overrides flex items' default min-width: auto --
       without it, a flex item won't wrap its own text content below
       its max-content width, which is exactly wide enough to overflow
       a narrow card for a long confirm sentence like Privacy's own
       "Forget everything..." message below. */
    min-width: 0;
  }

  .confirm .voice {
    color: var(--ink-muted);
    font-size: 14px;
  }

  /* Warm & Alive redesign (see frontend/decisions.md): a real --danger
     color now exists in the palette, so this uses it directly rather
     than v1's ink-weight-only signal. */
  .link-button.danger {
    color: var(--danger);
  }
</style>
