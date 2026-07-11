<script>
  // Renders the real Clarity Brief endpoint's content directly -- no
  // raw backend vocabulary (no "confidence", "Judgment", "epistemic
  // tier") anywhere here, per frontend-philosophy-v1.md and
  // trust-and-privacy-ux-v1.md. Realizes three of v4's five moments:
  // Growing understanding (the brief itself), Named uncertainty
  // (remainingUnknowns), and Quiet discovery (secondaryIssues /
  // stagnationNotes -- both already held back by Judgment unless
  // genuinely significant, so nothing further to filter here).
  //
  // Frontend redesign increment 1 (see frontend/decisions.md, and
  // interaction-model-v4.md's "Novelty is not the goal" guardrail,
  // relaxed 2026-07-11): distinct kinds of understanding get distinct
  // surfaces instead of one undifferentiated block, echoing Apple
  // Journal's "cards, not rows" form lesson -- settled content
  // (situation/current_direction, decisions) gets the raised, shadowed
  // treatment; still-open content (remaining_unknowns) gets a visually
  // lighter, unshadowed card, matching what it actually is. Quiet
  // Discovery (secondary_issues/stagnation_notes) stays outside every
  // card on purpose -- v4 requires it read as a passing notice, never
  // promoted to the same weight as settled content.
  let { brief, deepeningClarityNote } = $props();
</script>

{#if brief}
  <div class="understanding-region" aria-label="What we understand so far">
    {#if deepeningClarityNote}
      <p class="voice callout">{deepeningClarityNote}</p>
    {/if}

    {#if brief.situation || brief.current_direction}
      <section class="card card-settled" aria-label="Where things stand">
        {#if brief.situation}
          <p>{brief.situation}</p>
        {/if}
        {#if brief.current_direction}
          <p class="voice">{brief.current_direction}</p>
        {/if}
      </section>
    {/if}

    {#if brief.remaining_unknowns.length}
      <section class="card card-open" aria-label="Still uncertain">
        <p class="ui-label">Still uncertain</p>
        <ul>
          {#each brief.remaining_unknowns as unknown}
            <li>{unknown}</li>
          {/each}
        </ul>
      </section>
    {/if}

    {#if brief.decisions.length}
      <section class="card card-settled card-secondary" aria-label="In play">
        <p class="ui-label">In play</p>
        <ul>
          {#each brief.decisions as decision}
            <li>{decision}</li>
          {/each}
        </ul>
      </section>
    {/if}

    {#each brief.secondary_issues ?? [] as aside}
      <p class="voice aside">{aside}</p>
    {/each}
    {#each brief.stagnation_notes ?? [] as aside}
      <p class="voice aside">{aside}</p>
    {/each}
  </div>
{/if}

<style>
  .understanding-region {
    margin-top: var(--space-4);
  }

  .card {
    border-radius: var(--radius);
    padding: var(--space-3);
    margin-bottom: var(--space-2);
  }

  .card-settled {
    background: var(--paper-raised);
    box-shadow: 0 1px 0 var(--line);
  }

  .card-secondary {
    margin-top: var(--space-1);
  }

  /* Deliberately less anchored than a settled card -- no shadow, base
     paper background -- matching that this content is open, not resolved. */
  .card-open {
    background: var(--paper);
    border: 1px solid var(--line);
  }

  .card p,
  .card ul {
    margin: 0 0 var(--space-2);
  }

  .card ul {
    padding-left: var(--space-2);
  }

  .card p:last-child,
  .card ul:last-child {
    margin-bottom: 0;
  }

  .callout {
    color: var(--accent);
    margin: 0 0 var(--space-2);
  }

  .aside {
    color: var(--ink-muted);
  }
</style>
