<script>
  // Learning surfaced to users (2026-07-18, see engine/decisions.md
  // "Learning made per-account", frontend/specs/trust-and-privacy-ux-v1.md's
  // Principle 6) -- the Behavioral Pattern System
  // (src/learning/engine.py) has existed as a real, computed backend
  // concept since Phase 1, with zero frontend consumers until now.
  // Lives inside Settings as its own card, right alongside
  // PersonalOperatingModel.svelte -- same "You" section, same reasoning
  // for folding into an existing space rather than a new one.
  //
  // Deliberately DIFFERENT disclosure treatment than POM's own card:
  // POM hides its raw confidence level entirely and only uses it as a
  // display gate, because POM's frameworks are interpretive and only
  // lightly calibrated (see PersonalOperatingModel.svelte's own
  // docstring). A behavioral pattern is the opposite case -- purely
  // mechanical, evidence-counted, never LLM-inferred (see
  // src/learning/engine.py::compute_behavioral_patterns) -- so
  // Principle 6's own requirement applies directly here: "a noticed
  // pattern must never be presented with more confidence than its
  // evidence count actually earns -- visible undercount is safer than
  // invisible overreach." Each pattern's own `detail` (already a real,
  // grounded plain-language sentence, e.g. "3 of your decisions have
  // moved to 'deferred' status.") is shown as-is, with its
  // `evidence_count` right alongside it -- the number a person could
  // use to judge for themselves how much weight to give it, not hidden
  // behind a coarse label.
  //
  // Same "omit rather than show a hollow signal" discipline every
  // other Settings card here already follows: empty until
  // scripts/run_learning.py has computed something for this account,
  // and stays empty below MIN_EVIDENCE by design -- a brand-new
  // account correctly sees nothing, not an error.
  import { onMount } from 'svelte';
  import { getBehavioralPatterns } from '../lib/api.js';

  let patterns = $state([]);
  let loaded = $state(false);

  onMount(async () => {
    patterns = await getBehavioralPatterns();
    loaded = true;
  });
</script>

<section class="card setting-section">
  <div class="setting-heading">
    <span class="dot" style="--dot-tint: var(--accent-3)"></span>
    <p class="ui-label">Patterns</p>
  </div>
  <p class="setting-body">Things noticed across your Journeys, purely by counting -- never a diagnosis.</p>

  {#if loaded}
    {#if patterns.length === 0}
      <p class="voice patterns-empty">Nothing noticed yet -- this needs a few Journeys with a real, repeated pattern before it says anything.</p>
    {:else}
      <ul class="patterns-list">
        {#each patterns as pattern}
          <li>
            <span class="voice">{pattern.detail}</span>
            <span class="evidence-count">Noticed {pattern.evidence_count} times</span>
          </li>
        {/each}
      </ul>
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

  .patterns-empty {
    margin: var(--space-3) 0 0;
  }

  .patterns-list {
    margin: var(--space-3) 0 0;
    padding-top: var(--space-2);
    border-top: 1px solid var(--line);
    list-style: none;
  }

  .patterns-list li {
    margin-bottom: var(--space-2);
  }

  .patterns-list li:last-child {
    margin-bottom: 0;
  }

  .evidence-count {
    display: block;
    color: var(--ink-muted);
    font-size: 13px;
    margin-top: 2px;
  }
</style>
