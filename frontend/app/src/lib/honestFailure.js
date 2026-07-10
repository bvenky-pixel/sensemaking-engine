// Ported verbatim from frontend/mvp/index.html's honestFailureMessage --
// already correct per Principle 2 (partial completion shown honestly,
// not a generic error) and the vocabulary rules in interaction-model-v4.md.
export function honestFailureMessage(failedStage) {
  if (failedStage === 'interpretation') {
    return 'Something interrupted my understanding of that — would you mind trying again?';
  }
  if (failedStage === 'judgment' || failedStage === 'planner') {
    return 'I heard that clearly, but had trouble finishing my thought. Could you try again?';
  }
  if (failedStage === 'response') {
    return "I understood and thought this through, but couldn't quite find the words. One more try?";
  }
  return "Something didn't go as expected. Could you try again?";
}
