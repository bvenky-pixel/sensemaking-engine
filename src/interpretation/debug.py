from src.interpretation.schema import Interpretation


def analyze_interpretation(interp: Interpretation):
    print("\n=== INTERPRETATION DEBUG ===")

    # 1. Hypothesis diversity
    print("\n[Hypotheses]")
    for h in interp.hypotheses:
        print(f"- {h.hypothesis} ({h.confidence})")

    # 2. Emotional spread
    print("\n[Emotions]")
    for e in interp.emotional_signals:
        print(f"- {e.emotion} | intensity={e.intensity} | conf={e.confidence}")

    # 3. Uncertainty check
    print("\n[Uncertainties]")
    for u in interp.uncertainties:
        print(f"- {u}")

    # 4. Collapse detection
    hypothesis_count = len(interp.hypotheses)
    uncertainty_count = len(interp.uncertainties)
    emotion_count = len(interp.emotional_signals)

    print("\n[System Health]")
    if hypothesis_count <= 1:
        print("⚠️ Low hypothesis diversity (possible collapse)")
    if uncertainty_count == 0:
        print("⚠️ No uncertainty modeled")
    if emotion_count == 0:
        print("⚠️ No emotional signal detected")

    if hypothesis_count > 1 and uncertainty_count > 0:
        print("✅ Interpretation layer is healthy")

    print("============================\n")