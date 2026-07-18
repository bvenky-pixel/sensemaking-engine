<script>
  // Kept deliberately small (information-architecture-v1.md): privacy
  // controls, account basics -- nothing else belongs here.
  //
  // Privacy, made real (2026-07-18, see frontend/decisions.md): the
  // section was a static sentence with nothing behind it until now.
  // Three real controls: a toggle for cross-session learning (see
  // src/api/db.py's `privacy_settings` table docstring for exactly
  // what it gates -- Learning/Insight Engine/POM, never anything
  // in-session), a full data export, and "Forget everything"
  // (irreversible, deletes every Journey at once). Account remains a
  // placeholder -- there is still no auth/user system anywhere in this
  // codebase (see src/api/db.py's own "single-user simplification"
  // note), so populating it with fields would mean building fake
  // account state rather than something real.
  //
  // Warm & Alive redesign, organizing pass (2026-07-18, see
  // frontend/decisions.md): the sections previously ran together as
  // loose, unbordered paragraphs -- "messy," per direct founder
  // feedback. Now each is its own card with a small color-coded marker
  // dot, same scannability device ModeSelect already established for
  // its six modes, so a person can tell the sections apart at a glance
  // rather than reading every label.
  //
  // Reduce motion (2026-07-18, see frontend/decisions.md "Reduce
  // motion, as a real setting"): direct founder request, following a
  // question about whether the breathing orb honored the OS-level
  // accessibility setting -- it did, but had no in-app control of its
  // own. Lives in Account: a personal preference about how the app
  // behaves for this person, not a Privacy concern.
  //
  // Delete a Journey, from the Journey itself (2026-07-18, see
  // frontend/decisions.md): per-Journey deletion used to live here, in
  // a Data section that was really just a second, action-augmented
  // copy of Home's own journey list -- direct founder feedback moved
  // it to Journey.svelte instead, where a person actually is when
  // deciding to delete the one they're looking at. With that gone,
  // Data had no remaining content of its own (Privacy's export/reset
  // already cover "everything at once"), so the section was removed
  // rather than left as an empty shell -- information-architecture-v1.md's
  // three-named-sections framing is now two real ones (Privacy,
  // Account), not three where one is hollow.
  import { onMount } from 'svelte';
  import {
    getPrivacySettings,
    setCrossSessionLearningEnabled,
    exportPrivacyData,
    resetAllData,
  } from '../lib/api.js';
  import { getReduceMotionOverride, setReduceMotionOverride, applyReduceMotionAttribute } from '../lib/motionPreference.js';

  let { onBack } = $props();

  let reduceMotion = $state(false);
  let crossSessionLearning = $state(true);
  let exporting = $state(false);
  let pendingReset = $state(false);
  let resetting = $state(false);

  onMount(async () => {
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
      pendingReset = false;
    } finally {
      resetting = false;
    }
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
     independent sections of their own. .link-button/.confirm
     themselves now live in tokens.css (see that file's own comment) --
     Journey.svelte's delete action needs the identical recipe. */
  .privacy-actions {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--space-2) var(--space-3);
    margin-top: var(--space-3);
    padding-top: var(--space-2);
    border-top: 1px solid var(--line);
  }
</style>
