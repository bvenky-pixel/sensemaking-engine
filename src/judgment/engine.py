"""
Deterministic judgment layer: converts one turn's Interpretation, plus the
accumulated WorldState, into a framing of where things stand and whether
the conversation is ready to move to the next phase of the Confidant
Method.

This layer never advises. It only frames -- consistent with Principle 14:
"The decision always belongs to the human."
"""

from src.interpretation.schema import Interpretation

# Minimum core_question_confidence before we consider the "real question"
# actually found (Phase 2 success: the conversation moves from "why is
# this happening" to "what can I do").
DISCOVER_TO_DISCERN_THRESHOLD = 0.6

# Phase 3 success (partial, MVP heuristic): at least one assumption or
# bias has been surfaced. The full success criterion in the constitution
# also requires the user to *recognize* it, which this layer can't judge
# on its own -- that needs a future turn's language, not this one.
DISCERN_MIN_SIGNALS = 1


def run_judgment(interp: Interpretation, state=None):
    """
    state is optional so this stays usable standalone (e.g. in tests) --
    pass the accumulated WorldState when available so phase transitions
    can consider history, not just this one turn.
    """

    dominant_emotion = None
    if interp.emotional_signals:
        dominant_emotion = max(interp.emotional_signals, key=lambda e: e.intensity)

    # Phase 1 framing: urgency + impact domains + emotional intensity, not a generic
    # "risk score" -- named to match what the constitution actually asks
    # Confidant to attend to before anything else.
    attention_score = 0.0
    if interp.urgency == "high":
        attention_score += 0.4
    elif interp.urgency == "medium":
        attention_score += 0.2
    if dominant_emotion:
        attention_score += dominant_emotion.intensity * 0.4
    if interp.clarity_score < 0.4:
        attention_score += 0.2
    attention_score = min(attention_score, 1.0)

    if attention_score > 0.7:
        stance = "high_attention"
    elif attention_score > 0.4:
        stance = "uncertain_monitoring"
    else:
        stance = "stable_context"

    # Phase transition recommendation. This is advisory for the caller
    # (e.g. a future response-generation layer) -- run_judgment itself
    # doesn't mutate state.
    next_phase = None
    current_phase = getattr(state, "phase", "prepare") if state is not None else "prepare"

    if current_phase == "prepare" and interp.surface_complaint:
        next_phase = "discover"
    elif current_phase == "discover" and interp.core_question_confidence >= DISCOVER_TO_DISCERN_THRESHOLD:
        next_phase = "discern"
    elif current_phase == "discern":
        signal_count = len(interp.assumptions) + len(interp.biases)
        if signal_count >= DISCERN_MIN_SIGNALS:
            next_phase = "discern"  # stays; advancing to challenge is undrafted in the constitution

    return {
        "dominant_emotion": dominant_emotion.emotion if dominant_emotion else None,
        "attention_score": attention_score,
        "stance": stance,
        "core_question": interp.core_question,
        "core_question_confidence": interp.core_question_confidence,
        "assumptions_surfaced": len(interp.assumptions),
        "biases_surfaced": len(interp.biases),
        "current_phase": current_phase,
        "recommended_next_phase": next_phase,
    }
