<script>
  // The concrete form of v4's Ambient Presence signal (see
  // frontend/specs/screen-design-v1.md): one continuous wordless
  // signal, paced like a slow breath, carrying no report of what stage
  // of reasoning is happening. No percentage, no stage labels, no text.
  // Honest to the backend as it exists today, which only ever reports
  // two moments -- start-of-turn and end-of-turn/failure -- never
  // intermediate progress.
</script>

<div class="ambient-presence" role="status" aria-label="Confidant is considering what you shared">
  <div class="breath"></div>
</div>

<style>
  .ambient-presence {
    display: flex;
    justify-content: flex-start;
    padding: var(--space-2) 0;
  }

  .breath {
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: var(--accent);
    opacity: 0.4;
    animation: breathe 5s ease-in-out infinite;
  }

  @keyframes breathe {
    0%,
    100% {
      transform: scale(0.85);
      opacity: 0.25;
    }
    50% {
      transform: scale(1.15);
      opacity: 0.5;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .breath {
      animation: none;
      opacity: 0.35;
    }
  }
</style>
