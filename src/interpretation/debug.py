from src.interpretation.schema import Interpretation


def analyze_interpretation(interp: Interpretation):
    print("\n=== INTERPRETATION DEBUG ===")

    print("\n[Phase 1 -- Prepare]")
    print(f"- urgency: {interp.urgency} | impact_domains: {interp.impact_domains}")
    for e in interp.emotional_signals:
        print(f"- emotion: {e.emotion} | intensity={e.intensity} | confidence={e.confidence} | source={e.source}")

    print("\n[Phase 2 -- Discover]")
    print(f"- surface complaint: {interp.surface_complaint}")
    print(f"- core question: {interp.core_question} (confidence={interp.core_question_confidence})")

    print("\n[Phase 3 -- Discern: epistemic tiers]")
    for f in interp.observed_facts:
        print(f"- observed fact: {f}")
    for c in interp.claims:
        print(f"- claim: {c}")
    for g in interp.goals:
        print(f"- goal: {g}")
    for d in interp.decision_options:
        print(f"- decision option: {d}")
    for a in interp.assumptions:
        print(f"- assumption: {a}")
    for inf in interp.inferences:
        print(f"- inference: {inf.reading} (confidence={inf.confidence})")
    for u in interp.unknowns:
        print(f"- unknown: {u}")
    for b in interp.biases:
        print(f"- bias: {b.bias} (evidence: \"{b.evidence}\", conf={b.confidence})")

    print("\n[Phase 3b -- Lifecycle/enrichment signals (v1.1)]")
    for gu in interp.goal_updates:
        print(f"- goal update: {gu.goal!r} -> {gu.status}")
    for de in interp.decision_events:
        print(f"- decision event: {de.option!r} -> {de.event}")
    for eau in interp.entity_attribute_updates:
        print(f"- entity attribute update: {eau.entity!r}.{eau.attribute} = {eau.value!r}")
    if not (interp.goal_updates or interp.decision_events or interp.entity_attribute_updates):
        print("- (none this turn)")

    print("\n[System Health]")
    if interp.core_question_confidence < 0.3:
        print("i  Real question not yet found -- still in Discover phase")
    if not interp.assumptions and not interp.biases:
        print("!  No assumptions or biases surfaced yet (expected early in a conversation)")
    if interp.observed_facts and interp.claims:
        print("OK observed facts and claims kept distinct")
    if interp.inferences:
        print("OK inferences carrying explicit confidence")

    print("============================\n")
