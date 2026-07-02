from src.interpretation.schema import Interpretation


def run_judgment(interp: Interpretation):
    """
    Deterministic judgment layer:
    Converts interpretation → prioritized understanding.
    """

    # 1. Identify dominant hypothesis
    dominant_hypothesis = None
    if interp.hypotheses:
        dominant_hypothesis = max(
            interp.hypotheses,
            key=lambda h: h.confidence
        )

    # 2. Identify emotional severity
    max_emotion = None
    if interp.emotional_signals:
        max_emotion = max(
            interp.emotional_signals,
            key=lambda e: e.intensity
        )

    # 3. Risk aggregation
    risk_score = 0.0

    if interp.risk_signals:
        risk_score += min(1.0, len(interp.risk_signals) * 0.2)

    if max_emotion:
        risk_score += max_emotion.intensity * 0.4

    if interp.clarity_score < 0.4:
        risk_score += 0.2

    risk_score = min(risk_score, 1.0)

    # 4. Decision framing (NOT advice, just framing)
    if risk_score > 0.7:
        stance = "high_attention"
    elif risk_score > 0.4:
        stance = "uncertain_monitoring"
    else:
        stance = "stable_context"

    # 5. Salience extraction
    top_salience = None
    if interp.salience_map:
        top_salience = max(
            interp.salience_map,
            key=lambda s: s.importance
        )

    return {
        "dominant_hypothesis": dominant_hypothesis.hypothesis if dominant_hypothesis else None,
        "dominant_hypothesis_confidence": dominant_hypothesis.confidence if dominant_hypothesis else None,
        "max_emotion": max_emotion.emotion if max_emotion else None,
        "risk_score": risk_score,
        "stance": stance,
        "top_salience": top_salience.item if top_salience else None,
    }