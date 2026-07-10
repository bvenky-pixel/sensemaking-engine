<script>
  // Renders the real Clarity Brief endpoint's content directly -- no
  // raw backend vocabulary (no "confidence", "Judgment", "epistemic
  // tier") anywhere here, per frontend-philosophy-v1.md and
  // trust-and-privacy-ux-v1.md. Realizes three of v4's five moments:
  // Growing understanding (the brief itself), Named uncertainty
  // (remainingUnknowns), and Quiet discovery (secondaryIssues /
  // stagnationNotes -- both already held back by Judgment unless
  // genuinely significant, so nothing further to filter here).
  let { brief, deepeningClarityNote } = $props();
</script>

{#if brief}
  <section class="understanding" aria-label="What we understand so far">
    {#if deepeningClarityNote}
      <p class="voice callout">{deepeningClarityNote}</p>
    {/if}

    {#if brief.situation}
      <p>{brief.situation}</p>
    {/if}

    {#if brief.current_direction}
      <p class="voice">{brief.current_direction}</p>
    {/if}

    {#if brief.remaining_unknowns.length}
      <p class="ui-label">Still uncertain</p>
      <ul>
        {#each brief.remaining_unknowns as unknown}
          <li>{unknown}</li>
        {/each}
      </ul>
    {/if}

    {#if brief.decisions.length}
      <p class="ui-label">In play</p>
      <ul>
        {#each brief.decisions as decision}
          <li>{decision}</li>
        {/each}
      </ul>
    {/if}

    {#each brief.secondary_issues ?? [] as aside}
      <p class="voice aside">{aside}</p>
    {/each}
    {#each brief.stagnation_notes ?? [] as aside}
      <p class="voice aside">{aside}</p>
    {/each}
  </section>
{/if}

<style>
  .understanding {
    background: var(--paper-raised);
    border-radius: var(--radius);
    box-shadow: 0 1px 0 var(--line);
    padding: var(--space-3);
    margin-top: var(--space-4);
  }

  .understanding p {
    margin: 0 0 var(--space-2);
  }

  .understanding ul {
    margin: 0 0 var(--space-2);
    padding-left: var(--space-2);
  }

  .callout {
    color: var(--accent);
  }

  .aside {
    color: var(--ink-muted);
  }
</style>
