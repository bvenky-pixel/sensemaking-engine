"""
One-time migration: backfill stable `id`s onto every already-persisted
WorldState knowledge item (Fact/Claim/Goal/Decision/Unknown/Entity/
Assumption/Inference) -- see src/state/world_state.py's KnowledgeItem.id
and engine/decisions.md "Understanding layer -- Journey-scoped identity".

Why this is required, not optional cleanup: `id` has a `default_factory`
so `WorldState.model_validate_json` never raises on an old session's JSON
(which has no "id" key at all) -- but that default means an
already-persisted item gets a DIFFERENT id on every deserialization until
it's actually written back. Every read-only endpoint (db.py's
`load_state`, `list_sessions`, `get_session_texts_for_insights`) calls
`model_validate_json` without ever re-saving, so without this script,
"stable identity" would be false for every pre-existing session
indefinitely.

Idempotent: once an item has a real persisted id, re-running this script
just parses that id back out of the JSON (Pydantic doesn't invoke
`default_factory` for a field that's actually present in the input), so
a second run is a safe no-op -- confirmed by --dry-run reporting zero
missing ids.

`--dry-run` deliberately does a raw `json.loads` pre-check rather than
`WorldState.model_validate_json` -- the latter's `default_factory` would
silently mask exactly the thing a dry run is supposed to report (every
item would already "have" an id, generated fresh, by the time Pydantic
handed it back).

Run manually, or via a GitHub Actions workflow_dispatch, once after this
change deploys and before Tier 1 rendering is exercised against
production sessions.

Usage: python scripts/backfill_knowledge_item_ids.py [--db-path PATH] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api import db
from src.state.world_state import WorldState

# Every WorldState field holding a list of KnowledgeItem subtypes --
# kept as an explicit list rather than introspecting WorldState's fields,
# since a future new tier should have to be added here deliberately, not
# silently picked up (or silently missed) by field-type sniffing.
_KNOWLEDGE_ITEM_FIELDS = [
    "facts", "claims", "goals", "decisions", "unknowns", "entities",
    "assumption_items", "inference_items",
]


def _count_missing_ids(world_state_json: str) -> int:
    """Raw dict inspection, deliberately NOT going through
    WorldState.model_validate_json -- see module docstring."""
    raw = json.loads(world_state_json)
    missing = 0
    for field in _KNOWLEDGE_ITEM_FIELDS:
        for item in raw.get(field, []):
            if "id" not in item:
                missing += 1
    return missing


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="Override CONFIDANT_DB_PATH for this run (defaults to db.py's own resolution).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report how many items are missing an id, without writing anything back.",
    )
    args = parser.parse_args()

    db.init_db(Path(args.db_path) if args.db_path else None)

    sessions = db.get_all_sessions_raw()
    print(f"Read {len(sessions)} session(s).")

    if args.dry_run:
        total_missing = 0
        sessions_affected = 0
        for session_id, world_state_json in sessions:
            missing = _count_missing_ids(world_state_json)
            if missing:
                sessions_affected += 1
                total_missing += missing
        print(
            f"[dry run] {total_missing} item(s) missing an id across "
            f"{sessions_affected} session(s) -- no changes written."
        )
        return

    sessions_touched = 0
    for session_id, world_state_json in sessions:
        missing_before = _count_missing_ids(world_state_json)
        if not missing_before:
            continue
        # default_factory stamps a fresh id on every item that's missing
        # one; items that already have one keep it exactly as parsed.
        state = WorldState.model_validate_json(world_state_json)
        db.save_world_state_for_backfill(session_id, state)
        sessions_touched += 1
        print(f"- {session_id}: backfilled {missing_before} item(s)")

    if sessions_touched == 0:
        print("No sessions needed backfilling -- every item already has a persisted id.")
    else:
        print(f"\nBackfilled {sessions_touched} session(s).")


if __name__ == "__main__":
    main()
