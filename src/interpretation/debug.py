from src.interpretation.schema import Interpretation


def analyze_interpretation(interp: Interpretation):
    print("\n=== INTERPRETATION DEBUG ===")

    print("\n[Phase 1 -- Prepare]")
    print(f"- urgency: {interp.urgency} | stakes: {interp.stakes}")
    for e in interp.emotional_signals:
        print(f"- emotion: {e.emotion} | intensity={e.intensity} | conf={e.confidence}")

    print("\n[Phase 2 -- Discover]")
    print(f"- surface complaint: {interp.surface_complaint}")
    print(f"- core question: {interp.core_question} (confidence={interp.core_question_confidence})")

    print("\n[Phase 3 -- Discern]")
    for f in interp.facts:
        print(f"- fact: {f}")
    for a in interp.assumptions:
        flag = "TREATED AS FACT" if a.stated_as_fact else "acknowledged as belief"
        print(f"- assumption: {a.assumption} [{flag}]")
    for u in interp.unknowns:
        print(f"- unknown: {u}")
    for b in interp.biases:
        print(f"- bias: {b.bias} (evidence: \"{b.evidence}\", conf={b.confidence})")

    print("\n[System Health]")
    if interp.core_question_confidence < 0.3:
        print("i  Real question not yet found -- still in Discover phase")
    if not interp.assumptions and not interp.biases:
        print("!  No assumptions or biases surfaced yet (expected early in a conversation)")
    if interp.emotional_signals:
        print("OK emotional state captured")
    if interp.facts and interp.assumptions:
        print("OK facts/assumptions distinguished -- discernment forming")

    print("============================\n")
