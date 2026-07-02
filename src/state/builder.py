from src.interpretation.schema import Interpretation

def update_state(state, interp: Interpretation):

    state.facts = interp.propositions
    state.unknowns = interp.uncertainties
    state.stakeholders = interp.entities

    state.interpretations = [
        h.hypothesis for h in interp.hypotheses
    ]

    state.core_problem = interp.primary_intent
    state.clarity_level = interp.clarity_score

    if interp.emotional_signals:
        top = max(interp.emotional_signals, key=lambda x: x.intensity)
        state.emotion = top.emotion
        state.emotion_intensity = top.intensity

    state.risk_signals = interp.risk_signals

    return state