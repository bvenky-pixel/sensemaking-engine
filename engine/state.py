from dataclasses import dataclass, field
from typing import List


@dataclass
class ConversationState:
    emotion: str = ""
    emotion_intensity: int = 0

    urgency: str = "low"

    core_problem: str = ""

    facts: List[str] = field(default_factory=list)
    interpretations: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    unknowns: List[str] = field(default_factory=list)

    stakeholders: List[str] = field(default_factory=list)

    agency_level: float = 0.0
    clarity_level: float = 0.0

    decision: str = ""

    history_summary: str = ""
