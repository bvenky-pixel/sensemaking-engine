from dataclasses import dataclass, field
from typing import List


@dataclass
class ConversationState:
    # Phase 1 -- Prepare
    emotion: str = ""
    emotion_intensity: int = 0  # 0-10
    emotion_source: str = ""  # v0.9: "explicit" | "inferred" | "" (unset)
    urgency: str = "low"
    impact_domains: List[str] = field(default_factory=list)  # v0.9: renamed from `stakes`, now multi-label

    # Phase 2 -- Discover
    core_problem: str = ""
    core_problem_confidence: float = 0.0  # gates phase 2 -> 3 transition
    surface_complaint: str = ""

    # Phase 3 -- Discern (epistemic tiers -- see src/interpretation/schema.py)
    observed_facts: List[str] = field(default_factory=list)
    claims: List[str] = field(default_factory=list)
    goals: List[str] = field(default_factory=list)
    decision_options: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    inferences: List[str] = field(default_factory=list)
    unknowns: List[str] = field(default_factory=list)
    biases: List[str] = field(default_factory=list)

    stakeholders: List[str] = field(default_factory=list)

    clarity_level: float = 0.0

    # v0.9: agency_level was REMOVED here. It was declared, defaulted to
    # 0.0, and never written to anywhere in the pipeline -- confirmed by
    # direct code search, not inference. Displaying 0.0 in every state
    # table implied a computed value where none existed. See
    # engine/specs/interpretation-spec-v0.9.md Part 4 and
    # engine/decisions.md 2026-07-02. Re-add only once agency scoring is
    # actually designed and wired to something.

    # Where the conversation is in the Confidant Method.
    # prepare -> discover -> discern -> challenge -> resolve -> commit
    # (challenge/resolve/commit are undrafted in the constitution as of
    # Draft 0.1 -- state supports them but judgment logic doesn't yet.)
    phase: str = "prepare"

    decision: str = ""

    history_summary: str = ""
