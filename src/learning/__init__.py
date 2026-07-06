"""
Learning -- System Architecture v2's third component.

Implements the Learning section of
engine/specs/system-architecture-v2-specification.md, RESERVED SLOT ONLY.

Question answered: «What should Confidant learn over time?»

Responsibilities (per the spec, not yet implemented):
- Identifying durable patterns across many conversations and many
  Instrumentation records
- Producing calibration adjustments or durable, cross-conversation
  knowledge
- Improving future sensemaking
- Operating asynchronously, never inside a live conversation turn

Explicit scope boundary: Learning must never write directly into a live
WorldState. WorldState is a per-conversation Sensemaking Engine artifact
that Judgment reasons over; if Learning reached in and edited it
directly, Learning would become a de facto sensemaking process,
contradicting the System Architecture's own boundary of never reasoning
about the user's world. Learning's outputs feed INTO a future
Sensemaking Engine run as external input or configuration -- a future
Interpretation call, or a future WorldState-seeding step, decides what
that input means for a given conversation. Learning itself never makes
that decision.

STATUS: DELIBERATELY NOT IMPLEMENTED. Direct decision, confirmed twice --
once in engine/specs/system-architecture-v2-review.md's original
recommendation, and again when asked to "build Learning": there is no
persisted, real operational history to learn FROM yet.
Instrumentation's UsageTracker/AttemptRecord data (src/instrumentation/usage.py)
is per-process and never written to disk across runs -- this session's
real LLM call volume (a few dozen calls across several CI dispatches)
is nowhere near "durable pattern"-worthy, and there is no persistence
layer today that would let a later run even see an earlier run's data.
Building "identify durable patterns" logic against that would mean
inventing patterns from nothing, or building against fabricated data --
exactly the capability-ahead-of-evidence mistake this codebase has
corrected for repeatedly (Interpretation's multi-round hardening,
Judgment's "resist tuning until Planner exists," Planner's own restraint
at n=1/n=2 real samples).

`run_learning` exists only so this slot is a real, importable module --
proof the architecture reserves a place for it -- not a real entry
point. It raises NotImplementedError with this reasoning attached, on
purpose, so any future attempt to wire it in surfaces this decision
explicitly rather than silently doing nothing or guessing at a shape for
"durable knowledge" that no real data has justified yet. Implementing it
for real requires deliberately reopening this decision -- concretely,
that means at minimum a persistence layer for Instrumentation data
across runs (see engine/decisions.md), then real accumulated volume,
then this stub gets replaced, not extended in place.
"""

from __future__ import annotations


def run_learning(*args, **kwargs) -> None:
    raise NotImplementedError(
        "Learning is a reserved slot, not implemented. See src/learning/__init__.py's "
        "module docstring and engine/decisions.md for why: no persisted operational "
        "history exists yet to learn from. Implementing this requires deliberately "
        "reopening that decision, not extending this stub."
    )
