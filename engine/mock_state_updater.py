from __future__ import annotations

from dataclasses import replace

from engine.state import ConversationState


class MockStateUpdater:
    """
    A deterministic replacement for the real StateUpdater.

    This class never calls an API. Instead, it updates the
    ConversationState using simple keyword-based rules so that
    we can develop and test the reasoning engine offline.
    """

    def update(
        self,
        state: ConversationState,
        transcript: str,
    ) -> ConversationState:
        """
        Update the conversation state using simple rules.
        """

        updated = replace(state)

        text = transcript.lower()

        # -------------------------------
        # Emotion Detection
        # -------------------------------
        if any(word in text for word in ["anxious", "worried", "stress", "stressed"]):
            updated.emotion = "anxious"
            updated.emotion_intensity = 7

        elif any(word in text for word in ["angry", "frustrated", "furious"]):
            updated.emotion = "angry"
            updated.emotion_intensity = 7

        elif any(word in text for word in ["happy", "excited", "great"]):
            updated.emotion = "positive"
            updated.emotion_intensity = 6

        return updated