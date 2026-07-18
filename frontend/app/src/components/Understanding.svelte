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
  //
  // Major update (2026-07-11, see engine/decisions.md): brief.key_insights
  // was already sent by GET /clarity-brief but never rendered here --
  // the richest content Judgment actually produces (primary_problem +
  // risks + opportunities) was silently invisible. Given a settled card
  // treatment, same as situation/current_direction -- this is Judgment's
  // own assessed reading of what's going on, not still-open like
  // remaining_unknowns.
  //
  // Added 2026-07-15 (see engine/decisions.md "Tier 2 design"/
  // "implementation"/frontend wiring): GET /sessions/{id}/understanding's
  // tier2 statements, the first content this component gets from
  // src/understanding/ rather than src/executor/'s Clarity Brief.
  // Deliberately does NOT also render tier1 here -- Tier 1 is a raw,
  // unranked, per-item render of WorldState that substantially
  // duplicates what situation/key_insights/decisions/remaining_unknowns
  // above already show via Judgment/Planner's own curation, and its own
  // growth is confirmed unbounded with no prioritization design yet
  // (see the validation report's Area 5/7 findings) -- surfacing it raw
  // here would add repetition and an unbounded list, not new value.
  // Tier 2 is different: LLM-synthesized, genuinely additive content
  // (a connection across candidates, not a restatement of one), and
  // naturally bounded by what synthesis produces rather than by turn
  // count. Given the settled-card treatment, same as key_insights --
  // this is a considered reading of the conversation, not open/pending.
  //
  // Fixed 2026-07-15 (see engine/decisions.md "Frontend UX pass"): the
  // "Where things stand" card had no visible heading (only an
  // aria-label, screen-reader-only) -- every other card here has a
  // plain-text ui-label, so this one looked like a stray, disconnected
  // paragraph rather than a labeled section, confirmed live.
  let { brief, tier2 = [], deepeningClarityNote } = $props();
</script>

{#if brief || tier2?.length}
  <div class="understanding-region" aria-label="What we understand so far">
    {#if deepeningClarityNote}
      <p class="voice callout">{deepeningClarityNote}</p>
    {/if}

    {#if brief?.situation || brief?.current_direction}
      <section class="card card-settled" aria-label="Where things stand" transition:fade={{ duration: 320 }}>
        <p class="ui-label">Where things stand</p>
        {#if brief.situation}
          <p>{brief.situation}</p>
        {/if}
        {#if brief.current_direction}
          <p class="voice">{brief.current_direction}</p>
        {/if}
      </section>
    {/if}

    {#if brief?.key_insights?.length}
      <section class="card card-settled card-secondary" aria-label="What matters here" transition:fade={{ duration: 320 }}>
        <p class="ui-label">What matters here</p>
        <ul>
          {#each brief.key_insights as insight}
            <li>{insight}</li>
          {/each}
        </ul>
      </section>
    {/if}

    {#if tier2?.length}
      <section class="card card-settled card-secondary" aria-label="Putting it together" transition:fade={{ duration: 320 }}>
        <p class="ui-label">Putting it together</p>
        <ul>
          {#each tier2 as statement}
            <li>{statement.text}</li>
          {/each}
        </ul>
      </section>
    {/if}

    {#if brief?.remaining_unknowns?.length}
      <section class="card card-open" aria-label="Still uncertain" transition:fade={{ duration: 320 }}>
        <p class="ui-label">Still uncertain</p>
        <ul>
          {#each brief.remaining_unknowns as unknown}
            <li>{unknown}</li>
          {/each}
        </ul>
      </section>
    {/if}

    {#if brief?.decisions?.length}
      <section class="card card-settled card-secondary" aria-label="In play" transition:fade={{ duration: 320 }}>
        <p class="ui-label">In play</p>
        <ul>
          {#each brief.decisions as decision}
            <li>{decision}</li>
          {/each}
        </ul>
      </section>
    {/if}

    {#each brief?.secondary_issues ?? [] as aside}
      <p class="voice aside">{aside}</p>
    {/each}
    {#each brief?.stagnation_notes ?? [] as aside}
      <p class="voice aside">{aside}</p>
    {/each}
  </div>
{/if}

<style>
  .understanding-region {
    margin-top: var(--space-4);
  }

  /* .card-settled needs no rules of its own -- the shared .card recipe
     from tokens.css (background/radius/shadow) already IS the settled
     treatment; this class only exists so markup can name the semantic
     distinction against .card-open below. */
  .card {
    padding: var(--space-3);
    margin-bottom: var(--space-2);
  }

  .card-secondary {
    margin-top: var(--space-1);
  }

  /* Deliberately less anchored than a settled card -- no shadow, a soft
     dashed edge instead of a solid line -- matching that this content
     is open, not resolved. Kept from v1's own semantic distinction,
     just re-executed in the warmer visual language. */
  .card-open {
    background: transparent;
    box-shadow: none;
    border: 2px dashed var(--line);
  }

  .card p,
  .card ul {
    margin: 0 0 var(--space-2);
  }

  .card ul {
    padding-left: var(--space-3);
  }

  .card p:last-child,
  .card ul:last-child {
    margin-bottom: 0;
  }

  .callout {
    color: var(--accent-2);
    margin: 0 0 var(--space-3);
    padding: var(--space-2) var(--space-3);
    background: color-mix(in srgb, var(--accent-2) 10%, transparent);
    border-radius: var(--radius-sm);
  }

  .aside {
    color: var(--ink-muted);
  }
</style>
