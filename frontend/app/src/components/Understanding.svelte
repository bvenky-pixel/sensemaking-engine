<script>
  // Renders the real Clarity Brief endpoint's content directly -- no
  // raw backend vocabulary (no "confidence", "Judgment", "epistemic
  // tier") anywhere here, per frontend-philosophy-v1.md and
  // trust-and-privacy-ux-v1.md. Realizes two of v4's five moments:
  // Growing understanding (the brief itself) and Named uncertainty
  // (remainingUnknowns).
  //
  // Direct founder feedback (2026-07-22, screen overhaul round): the
  // panel had unlabeled prose below every card -- secondary_issues and
  // stagnation_notes, rendered as bare .aside paragraphs with no
  // ui-label heading, the only unframed content here -- reading as
  // exposed raw judgment analysis rather than a deliberate part of the
  // experience. Backend still computes and serves both fields
  // (ClarityBriefResponse, GET /clarity-brief) -- this component simply
  // no longer surfaces them; no card treatment was judged worth giving
  // this content either, so it's dropped rather than reframed.
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
  //
  // Orb as consciousness (2026-07-18, see frontend/decisions.md "Orb as
  // consciousness"): direct founder framing -- "the orb is Confidant, it
  // is consciousness... the clarity notes... should seem that they are
  // the orb's consciousness's perspective or thought" -- explicitly UI
  // only, no change to any generated text. Everything below is styling:
  // a small static orb-signature (the same radial-gradient recipe as
  // BreathingOrb/AmbientPresence's own core, just not animated -- a
  // seal marking this section as the orb's, not a third moving orb
  // competing for attention), gradient dots replacing default list
  // markers so each item reads as one thought rather than a form field,
  // and italic applied consistently across the region's own prose --
  // .voice already meant "Confidant's own reading" before this round
  // (see tokens.css's own comment on that class); this just applies it
  // everywhere in here instead of only on current_direction/asides, so
  // the whole panel reads as one continuous voice rather than a mix of
  // voiced and unvoiced text. ui-label headings stay upright on
  // purpose -- they're navigation chrome, not the orb's own words, and
  // that contrast is what makes the voiced content read as content.
  //
  // Clarity Brief v2 (2026-07-22, see engine/decisions.md and
  // clarity-brief-specification-v1.md "The Eight Sections"): three new
  // cards below (known_facts, competing_priorities, contradictions),
  // same settled-card treatment as key_insights/decisions -- each is a
  // curated Judgment/Executor conclusion, not open/pending content.
  // `brief.emerging_patterns` deliberately does NOT get a fourth new
  // card of its own, even though it's now a named ClarityBrief field --
  // it's the exact same tier2 content "Putting it together" already
  // renders (the spec's own "reframe, not new build" framing), and this
  // component keeps sourcing that card from the separate `tier2` prop
  // rather than `brief.emerging_patterns` for one structural reason:
  // Tier 2 computes and this component renders it even with NO Clarity
  // Brief yet (`brief` can be null while `tier2` is populated -- see
  // this file's own test suite,
  // "renders tier2 content even when there is no clarity brief yet").
  // Switching the source to `brief.emerging_patterns` would silently
  // drop that case. Adding a second, brief-sourced card for the same
  // content would recreate the exact "two adjacent panels both claiming
  // to be the current understanding" problem this spec explicitly
  // named as the reason to fold Tier 2 into the Brief in the first
  // place -- so the existing tier2-prop card stays the ONE home for
  // this content, unchanged.
  //
  // `whatChanged` (new, replaces the old client-side
  // `deepeningClarityNote` prop) is computed SERVER-SIDE now
  // (src/executor/engine.py::diff_clarity_briefs, per the spec's own
  // "Decided" section -- "not a presentation concern, a product
  // intelligence concern") and can be a real, multi-item list, not a
  // single generic sentence -- rendered as its own small list inside
  // the callout rather than one flat sentence.
  let { brief, tier2 = [], whatChanged = [] } = $props();
</script>

{#if brief || tier2?.length}
  <div class="understanding-region" aria-label="What we understand so far">
    <div class="orb-signature" aria-hidden="true"></div>

    {#if whatChanged?.length}
      <div class="voice callout">
        <ul>
          {#each whatChanged as change}
            <li>{change}</li>
          {/each}
        </ul>
      </div>
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

    {#if brief?.known_facts?.length}
      <section class="card card-settled card-secondary" aria-label="What I know" transition:fade={{ duration: 320 }}>
        <p class="ui-label">What I know</p>
        <ul>
          {#each brief.known_facts as fact}
            <li>{fact}</li>
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

    {#if brief?.competing_priorities?.length}
      <section class="card card-settled card-secondary" aria-label="Pulling you in different directions" transition:fade={{ duration: 320 }}>
        <p class="ui-label">Pulling you in different directions</p>
        <ul>
          {#each brief.competing_priorities as priority}
            <li>{priority}</li>
          {/each}
        </ul>
      </section>
    {/if}

    {#if brief?.contradictions?.length}
      <section class="card card-settled card-secondary" aria-label="Worth a second look" transition:fade={{ duration: 320 }}>
        <p class="ui-label">Worth a second look</p>
        <ul>
          {#each brief.contradictions as contradiction}
            <li>{contradiction}</li>
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

  </div>
{/if}

<style>
  .understanding-region {
    margin-top: var(--space-4);
  }

  /* The orb's seal -- same core gradient as BreathingOrb/AmbientPresence,
     static (no breathing, no glow) so it reads as a signature marking
     whose voice this section is, not a third animated orb on the
     screen. color-mix() against var(--accent), not a fixed peach hex
     (2026-07-22, see engine/decisions.md "Accent color picker") -- this
     was the one spot the earlier accent-theme round missed; the list-
     marker dots below get the identical fix for the same reason. */
  .orb-signature {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: radial-gradient(circle at 35% 30%, color-mix(in srgb, var(--accent) 45%, white 55%), var(--accent) 70%);
    margin: 0 auto var(--space-2);
    opacity: 0.7;
  }

  /* .card-settled needs no rules of its own -- the shared .card recipe
     from tokens.css (background/radius/shadow) already IS the settled
     treatment; this class only exists so markup can name the semantic
     distinction against .card-open below. */
  .card {
    padding: var(--space-3);
    margin-bottom: var(--space-2);
    /* A faint warm wash, same rgba value as the page-level ambient
       background in tokens.css -- these cards read as lit from the
       same source as the orb, not as flat form panels. */
    background-image: radial-gradient(120% 140% at 15% -10%, rgba(255, 122, 89, 0.05), transparent 60%);
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

  /* Consciousness's own voice throughout (see script comment above) --
     italic only, size/color untouched, so density stays the same and
     only the "whose words are these" signal changes. */
  .card p,
  .card li {
    font-style: italic;
  }

  .card ul {
    list-style: none;
    padding-left: var(--space-3);
  }

  .card li {
    position: relative;
  }

  /* A small gradient dot in place of the default marker, same recipe as
     .orb-signature above -- each item reads as one of the orb's own
     thoughts, not a bulleted form field. */
  .card li::before {
    content: '';
    position: absolute;
    left: -17px;
    top: 0.55em;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: radial-gradient(circle at 35% 30%, color-mix(in srgb, var(--accent) 45%, white 55%), var(--accent) 70%);
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

  /* what_changed (server-computed, see script comment above) can be a
     real multi-item list now, not one flat sentence -- same italic
     voice as everything else in this region, but its own marker color
     (matches .callout's own accent-2, not the orb-signature gradient
     dot the .card lists use) so it still reads as its own distinct
     kind of note. */
  .callout ul {
    list-style: none;
    margin: 0;
    padding-left: var(--space-3);
  }

  .callout li {
    font-style: italic;
    position: relative;
  }

  .callout li + li {
    margin-top: var(--space-1);
  }

  .callout li::before {
    content: '';
    position: absolute;
    left: -17px;
    top: 0.55em;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--accent-2);
  }
</style>
