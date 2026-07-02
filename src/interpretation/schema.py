from pydantic import BaseModel
from typing import List

class Hypothesis(BaseModel):
    hypothesis: str
    confidence: float

class EmotionalSignal(BaseModel):
    emotion: str
    intensity: float
    confidence: float

class Event(BaseModel):
    event: str
    type: str
    confidence: float

class SalienceItem(BaseModel):
    item: str
    importance: float


class Interpretation(BaseModel):
    input_type: str
    primary_intent: str

    entities: List[str]

    events: List[Event]
    propositions: List[str]

    hypotheses: List[Hypothesis]
    uncertainties: List[str]

    salience_map: List[SalienceItem]

    emotional_signals: List[EmotionalSignal]

    valence: str
    clarity_score: float

    risk_signals: List[str]
    requires_clarification: bool