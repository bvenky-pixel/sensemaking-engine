<script>
  // Orb as consciousness (2026-07-18, see frontend/decisions.md "Orb as
  // consciousness"): direct founder framing -- "the orb is Confidant, it
  // is consciousness... I want the home screen orb to have a deep and
  // meaningful life quote that changes on every load." A real teaching
  // from the Buddhist/Zen/Taoist tradition BreathingOrb's own enso ring
  // now visually gestures at, rather than only decoration next to it.
  //
  // Picked once at component creation, same pattern as Journey.svelte's
  // OPENING_PROMPTS -- changes on every fresh page load (a new Home
  // mount), not on every re-render while the page is already open.
  const QUOTES = [
    { text: 'The mind is everything. What you think, you become.', author: 'Buddha' },
    { text: 'Peace comes from within. Do not seek it without.', author: 'Buddha' },
    { text: 'You only lose what you cling to.', author: 'Buddha' },
    { text: 'Three things cannot be long hidden: the sun, the moon, and the truth.', author: 'Buddha' },
    { text: 'Feelings come and go like clouds in a windy sky. Conscious breathing is my anchor.', author: 'Thich Nhat Hanh' },
    { text: 'The present moment is the only moment available to us, and it is the door to all moments.', author: 'Thich Nhat Hanh' },
    { text: 'Walk as if you are kissing the Earth with your feet.', author: 'Thich Nhat Hanh' },
    { text: 'Letting go gives us freedom, and freedom is the only condition for happiness.', author: 'Thich Nhat Hanh' },
    { text: 'Smile, breathe, and go slowly.', author: 'Thich Nhat Hanh' },
    { text: 'Nature does not hurry, yet everything is accomplished.', author: 'Lao Tzu' },
    { text: 'When I let go of what I am, I become what I might be.', author: 'Lao Tzu' },
    { text: 'A good traveler has no fixed plans and is not intent upon arriving.', author: 'Lao Tzu' },
    { text: 'The journey of a thousand miles begins with a single step.', author: 'Lao Tzu' },
    { text: 'You are the sky. Everything else is just the weather.', author: 'Pema Chödrön' },
    { text: 'Nothing ever goes away until it has taught us what we need to know.', author: 'Pema Chödrön' },
    { text: 'In the beginner’s mind there are many possibilities, but in the expert’s mind there are few.', author: 'Shunryu Suzuki' },
    { text: 'To study the self is to forget the self.', author: 'Dōgen' },
    { text: 'If you let go a little, you will have a little peace. If you let go a lot, you will have a lot of peace.', author: 'Ajahn Chah' },
    { text: 'Before enlightenment, chop wood, carry water. After enlightenment, chop wood, carry water.', author: 'Zen proverb' },
    { text: 'The obstacle is the path.', author: 'Zen proverb' },
    { text: 'Sitting quietly, doing nothing, spring comes, and the grass grows by itself.', author: 'Zen proverb' },
    { text: 'The wound is the place where the light enters you.', author: 'Rumi' },
    { text: 'What you seek is seeking you.', author: 'Rumi' },
  ];
  const quote = QUOTES[Math.floor(Math.random() * QUOTES.length)];
</script>

<figure class="zen-quote">
  <blockquote class="voice">&ldquo;{quote.text}&rdquo;</blockquote>
  <figcaption class="ui-label">&mdash; {quote.author}</figcaption>
</figure>

<style>
  .zen-quote {
    margin: 0 0 var(--space-2);
    text-align: center;
  }

  /* Compact mode picker (2026-07-21, see Home.svelte's own docstring
     and engine/decisions.md "Compact mode picker"): quote length varies
     (some run to 2-3 lines at this font size), which conflicts with a
     hard "always fits without scrolling" goal -- clamped to 2 lines
     with an ellipsis so this component's own height is bounded
     regardless of which quote gets picked, rather than only usually
     compact. */
  .zen-quote blockquote {
    margin: 0 0 var(--space-1);
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .zen-quote figcaption {
    opacity: 0.7;
  }
</style>
