<script>
  // POM surfaced to users (2026-07-18, see frontend/decisions.md "POM
  // surfaced to users") -- the Personal Operating Model
  // (src/pom/schema.py, engine/decisions.md "Personal Operating
  // Model") has existed as a backend concept since that round, but
  // GET /personal-operating-model had zero frontend consumers until
  // now. Lives inside Settings as a third section ("You") rather than
  // a new screen -- information-architecture-v1.md treats Home/Journey/
  // Settings as exhaustive and requires a real justification for a 4th
  // space, which nothing here clears; this also matches the founder's
  // own framing of the eventual goal as "surface POM without
  // intimidating," which argues for folding it into an existing,
  // already-understood space rather than a new dashboard-like one.
  //
  // Same "no raw backend vocabulary" discipline Understanding.svelte
  // already established for Clarity Brief/Tier 2 content (see that
  // component's own docstring) -- nothing here ever shows a raw
  // ConfidenceLevel string ("high"/"moderate"/"unclear") or an academic
  // framework name (Self-Determination Theory, Narrative Identity
  // Theory) as a label. A confidence level is used ONLY as a gate
  // (skip a sub-system entirely below "unclear" or empty evidence) --
  // the actual visible content is always the real, grounded evidence
  // sentence(s) src/pom/engine.py already extracted, never an invented
  // felt-language translation of a coarse category. This is a
  // deliberate, narrower choice than Understanding.svelte's
  // card-per-item treatment: POM's underlying frameworks are
  // genuinely interpretive and only lightly calibrated (see
  // src/pom/schema.py's own caveat that Motivation/Narrative use
  // textbook framings, not the founder's own verified spec) -- staying
  // close to the real evidence text is the honest choice until that's
  // verified, rather than inventing confident-sounding narrative
  // prose a coarse "moderate" doesn't actually support.
  //
  // Any sub-system with nothing grounded yet is omitted entirely, same
  // "omit rather than show a hollow signal" discipline already used
  // elsewhere (e.g. Home's mode-filter chips only showing modes
  // actually present). If POM hasn't been computed at all yet
  // (scripts/run_pom_computation.py never run), one quiet line instead
  // of a section with nothing in it.
  //
  // Visual language deliberately matches Settings' own existing
  // Privacy/Account sections (one .card.setting-section, plain content
  // rows inside) rather than importing Understanding.svelte's separate
  // nested-card-per-item treatment -- the two live in different
  // contexts (a floating region next to an active conversation vs. a
  // single settled screen a person visits deliberately), and stacking
  // Understanding's own shadowed cards inside a Settings card would
  // double up the "raised" treatment for no reason. `.voice` (already
  // meaning "Confidant's own reading" throughout this app) marks every
  // synthesized/grounded sentence here too, so the section still reads
  // as the same voice, just in Settings' own layout.
  import { onMount } from 'svelte';
  import { getPersonalOperatingModel } from '../lib/api.js';
  import PomFeedback from './PomFeedback.svelte';

  let pom = $state(null);
  let loaded = $state(false);

  onMount(async () => {
    pom = await getPersonalOperatingModel();
    loaded = true;
  });

  const MOTIVATION_LABELS = {
    autonomy: 'Doing things your own way',
    competence: 'Feeling capable and effective',
    relatedness: 'Feeling connected to others',
  };

  let motivationRows = $derived(
    pom
      ? ['autonomy', 'competence', 'relatedness']
          .filter((dim) => pom.motivation[dim] !== 'unclear' && pom.motivation[`${dim}_evidence`]?.length > 0)
          .map((dim) => ({
            dim,
            label: MOTIVATION_LABELS[dim],
            evidence: pom.motivation[`${dim}_evidence`].join(' '),
          }))
      : []
  );

  let hasStress = $derived(!!pom && pom.stress.level !== 'unclear' && pom.stress.evidence.length > 0);
  let hasNarrative = $derived(!!pom && pom.narrative.arc !== 'unclear' && !!pom.narrative.summary);

  let hasAnything = $derived(
    !!pom &&
      (pom.belief.beliefs.length > 0 ||
        pom.relationship.relationships.length > 0 ||
        !!pom.identity.self_concept ||
        motivationRows.length > 0 ||
        !!pom.learning_style.style ||
        hasStress ||
        hasNarrative ||
        pom.theory_of_mind.entries.length > 0)
  );

  // computed_at staleness signal (2026-07-19, backlog #271, mirrors
  // BehavioralPatterns.svelte's own #269 -- see engine/decisions.md
  // "Learning/POM: surface computed_at staleness signal").
  function formatComputedAt(isoString) {
    return new Date(isoString).toLocaleDateString(undefined, {
      year: 'numeric', month: 'short', day: 'numeric',
    });
  }
</script>

<section class="card setting-section">
  <div class="setting-heading">
    <span class="dot" style="--dot-tint: var(--accent-4)"></span>
    <p class="ui-label">You</p>
  </div>
  <p class="setting-body">A standing sense of you, built up across every Journey.</p>

  {#if loaded}
    {#if !hasAnything}
      <p class="voice pom-empty">Nothing standing yet -- this builds up the more we talk.</p>
    {:else}
      <div class="pom-blocks">
        {#if pom.belief.beliefs.length > 0}
          <div class="pom-block">
            <p class="pom-heading">What you've told me you believe</p>
            <ul class="pom-list">
              {#each pom.belief.beliefs as belief}
                <li>
                  {belief}
                  <PomFeedback system="belief" statement={belief} />
                </li>
              {/each}
            </ul>
          </div>
        {/if}

        {#if pom.relationship.relationships.length > 0}
          <div class="pom-block">
            <p class="pom-heading">People who come up</p>
            <ul class="pom-list">
              {#each pom.relationship.relationships as relationship}
                <li>
                  {relationship}
                  <PomFeedback system="relationship" statement={relationship} />
                </li>
              {/each}
            </ul>
          </div>
        {/if}

        {#if pom.identity.self_concept}
          <div class="pom-block">
            <p class="pom-heading">How you seem to see yourself</p>
            <p class="voice">{pom.identity.self_concept}</p>
            <PomFeedback system="identity" statement={pom.identity.self_concept} />
          </div>
        {/if}

        {#if motivationRows.length > 0}
          <div class="pom-block">
            <p class="pom-heading">What seems to drive you</p>
            <ul class="pom-list">
              {#each motivationRows as row}
                <li>
                  <strong>{row.label}.</strong> <span class="voice">{row.evidence}</span>
                  <PomFeedback system={`motivation.${row.dim}`} statement={row.evidence} />
                </li>
              {/each}
            </ul>
          </div>
        {/if}

        {#if pom.learning_style.style}
          <div class="pom-block">
            <p class="pom-heading">How you seem to learn and take things in</p>
            <p class="voice">{pom.learning_style.style}</p>
            <PomFeedback system="learning_style" statement={pom.learning_style.style} />
          </div>
        {/if}

        {#if hasStress}
          <div class="pom-block">
            <p class="pom-heading">Stress</p>
            <p class="voice">{pom.stress.evidence.join(' ')}</p>
            <PomFeedback system="stress" statement={pom.stress.evidence.join(' ')} />
          </div>
        {/if}

        {#if hasNarrative}
          <div class="pom-block">
            <p class="pom-heading">The shape of your story so far</p>
            <p class="voice">{pom.narrative.summary}</p>
            <PomFeedback system="narrative" statement={pom.narrative.summary} />
          </div>
        {/if}

        {#if pom.theory_of_mind.entries.length > 0}
          <div class="pom-block">
            <p class="pom-heading">What I've noticed about people in your life</p>
            <ul class="pom-list">
              {#each pom.theory_of_mind.entries as entry}
                <li>
                  <strong>{entry.entity_name}:</strong> <span class="voice">{entry.inferred_perspective}</span>
                  <PomFeedback
                    system="theory_of_mind"
                    statement={`${entry.entity_name}: ${entry.inferred_perspective}`}
                  />
                </li>
              {/each}
            </ul>
          </div>
        {/if}
      </div>
      {#if pom.computed_at}
        <p class="computed-at">Last updated {formatComputedAt(pom.computed_at)}</p>
      {/if}
    {/if}
  {/if}
</section>

<style>
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

  .pom-empty {
    margin: var(--space-3) 0 0;
  }

  .pom-blocks {
    margin-top: var(--space-3);
    padding-top: var(--space-2);
    border-top: 1px solid var(--line);
  }

  .pom-block {
    margin-bottom: var(--space-3);
  }

  .pom-block:last-child {
    margin-bottom: 0;
  }

  .pom-heading {
    font-family: var(--font-body);
    color: var(--ink);
    font-weight: 600;
    margin: 0 0 var(--space-1);
  }

  .pom-list {
    margin: 0;
    padding-left: var(--space-3);
  }

  .pom-list li {
    margin-bottom: var(--space-1);
  }

  .pom-list li:last-child {
    margin-bottom: 0;
  }
</style>
