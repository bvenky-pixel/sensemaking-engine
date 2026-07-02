from dataclasses import dataclass, field
from typing import List


@dataclass
class ConversationState:
    # Phase 1 -- Prepare
    emotion: str = ""
    emotion_intensity: int = 0  # 0-10
    urgency: str = "low"
    stakes: str = ""

    # Phase 2 -- Discover
    core_problem: str = ""
    core_problem_confidence: float = 0.0  # gates phase 2 -> 3 transition
    surface_complaint: str = ""

    # Phase 3 -- Discern
    facts: List[str] = field(default_factory=list)
    interpretations: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    unknowns: List[str] = field(default_factory=list)
    biases: List[str] = field(default_factory=list)

    stakeholders: List[str] = field(default_factory=list)

    agency_level: float = 0.0
    clarity_level: float = 0.0

    # Where the conversation is in the Confidant Method.
    # prepare -> discover -> discern -> challenge -> resolve -> commit
    # (challenge/resolve/commit are undrafted in the constitution as of
    # Draft 0.1 -- state supports them but judgment logic doesn't yet.)
    phase: str = "prepare"

    decision: str = ""

    history_summary: str = ""
