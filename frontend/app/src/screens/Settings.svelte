<script>
  // Kept deliberately small (information-architecture-v1.md): privacy
  // controls, account basics, data management -- nothing else belongs
  // here. No backend endpoints exist yet for any of these three
  // sections' actual controls; this is the structural placeholder they
  // fill in once those exist.
  let { onBack } = $props();
</script>

<div class="settings">
  <button type="button" class="back" onclick={onBack}>&larr; Home</button>

  <section>
    <p class="ui-label">Privacy</p>
    <p>Controls for what Confidant remembers and how it's used.</p>
  </section>

  <section>
    <p class="ui-label">Account</p>
    <p>Basic account details.</p>
  </section>

  <section>
    <p class="ui-label">Data</p>
    <p>Export or remove what's been shared here.</p>
  </section>
</div>

<style>
  .back {
    display: block;
    margin-bottom: var(--space-3);
  }

  section {
    margin-bottom: var(--space-3);
  }

  section p:last-child {
    color: var(--ink-muted);
  }
</style>
