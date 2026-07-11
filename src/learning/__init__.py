"""
Learning -- System Architecture v2's third component.

Implements the Learning section of
engine/specs/system-architecture-v2-specification.md.

Question answered: «What should Confidant learn over time?»

STATUS: Phase 1 IMPLEMENTED (see engine/specs/architecture-roadmap-v1.md
and engine/decisions.md), replacing this module's former reserved-slot
stub per that stub's own instruction: implementing it "requires
deliberately reopening this decision -- concretely, that means at
minimum a persistence layer for Instrumentation data across runs, then
real accumulated volume, then this stub gets replaced, not extended in
place." src/api/db.py's `behavioral_events` table is that persistence
layer; src/learning/engine.py::compute_behavioral_patterns is the real
implementation, scoped narrowly to the Behavioral Pattern System only
(see that module's docstring for the full scope-down reasoning).

Explicit scope boundary, preserved unchanged from the original reserved
slot: Learning must never write directly into a live WorldState.
WorldState is a per-conversation Sensemaking Engine artifact that
Judgment reasons over; if Learning reached in and edited it directly,
Learning would become a de facto sensemaking process, contradicting the
System Architecture's own boundary of never reasoning about the user's
world. Phase 1 respects this by stopping at GET /patterns (read-only,
offline-computed) -- feeding Learning's output into a live
Interpretation/WorldState-seeding step is a real, bigger change, named
in the roadmap as a deliberately separate, unstarted later increment,
not silently implied by this one.

Operates asynchronously, never inside a live conversation turn:
src/learning/engine.py's compute_behavioral_patterns is a pure function;
the only thing that calls it is scripts/run_learning.py, a standalone
offline script -- nothing in the live request path (src/api/server.py)
calls it.
"""

from __future__ import annotations

from src.learning.engine import Pattern, compute_behavioral_patterns

__all__ = ["Pattern", "compute_behavioral_patterns"]
