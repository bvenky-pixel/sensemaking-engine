"""
Learning v1 -- Phase 1's first real slice, replacing (not extending)
src/learning/__init__.py's reserved-slot stub, per that stub's own
docstring's instruction: "at minimum a persistence layer for
Instrumentation data across runs [src/api/db.py's behavioral_events
table]... then real accumulated volume, then this stub gets replaced,
not extended in place."

Scoped narrowly to the Behavioral Pattern System only -- one of nine
systems the founder's uploaded Personal Operating Model vision document
describes -- because it's a direct generalization of
src/judgment/engine.py::compute_stagnation_signals, which already ships:
mechanical, evidence-counted, non-LLM. The other eight systems (Identity,
Motivation scored against Self-Determination Theory dimensions, Belief,
Relationship, Learning, Stress, Narrative, Theory of Mind) would require
inventing scored psychological dimensions with no evidence behind them
-- explicitly not attempted here.

Deliberately narrower than the vision document's own richer example
("delays decisions while seeking more certainty") -- that needs semantic
clustering across differently-worded content, which no infrastructure
exists for yet. This module only counts/ratios by event_type and
new_status, the same mechanical style compute_stagnation_signals already
established: a pure function, an explicitly-uncalibrated threshold
constant with an honest comment, plain-language evidence output, never
an LLM call. Not an LLM call on purpose -- inventing a new hallucination
surface on a feature whose whole point is "don't invent patterns without
evidence" would defeat its own purpose.

Non-goals preserved from engine/specs/system-architecture-v2-specification.md:
runs only offline (scripts/run_learning.py), never inside a live
request; never writes to a live WorldState; output (this module's
`Pattern` list) feeds forward only as far as GET /patterns today -- NOT
wired into any live Interpretation/WorldState-seeding step yet, a
separate, later, deliberately unstarted increment.
"""

from __future__ import annotations

from collections import Counter
from typing import List

from pydantic import BaseModel

from src.instrumentation.events import BehavioralEvent

# First-cut, NOT empirically calibrated -- same honest-uncalibrated-
# threshold style as compute_stagnation_signals's STAGNATION_TURN_THRESHOLD.
# Chosen so a single reaffirmation or a two-event coincidence can never
# be reported as a pattern; revisit once this runs against real usage.
MIN_EVIDENCE = 3


class Pattern(BaseModel):
    """One mechanically-computed behavioral pattern -- observation-derived,
    not a diagnosis. `detail` is plain language; `evidence_count` is the
    exact number of BehavioralEvents backing it, always >= MIN_EVIDENCE,
    following the same {statement, confidence/evidence_count} explainability
    shape the founder's Data Security vision document names as a
    requirement -- already this project's instinct via stagnation_notes/
    provenance, just not yet a formally named universal pattern."""

    pattern_type: str
    detail: str
    evidence_count: int


def compute_behavioral_patterns(
    events: List[BehavioralEvent], min_evidence: int = MIN_EVIDENCE
) -> List[Pattern]:
    """
    Pure function, no side effects, no persistence -- same category as
    compute_stagnation_signals. Groups events by (event_type, new_status)
    and reports a pattern only for a group whose count meets min_evidence.
    A session/turn with too little evidence produces an empty list, not a
    weak pattern -- silence is the correct, intended output below the
    floor, not a bug to work around.
    """
    counts = Counter((event.event_type, event.new_status) for event in events)

    patterns: List[Pattern] = []
    for (event_type, new_status), count in counts.items():
        if count < min_evidence:
            continue
        subject = "decisions" if event_type == "decision_status_changed" else "goals"
        patterns.append(
            Pattern(
                pattern_type=event_type,
                detail=f"{count} of your {subject} have moved to {new_status!r} status.",
                evidence_count=count,
            )
        )
    return patterns
