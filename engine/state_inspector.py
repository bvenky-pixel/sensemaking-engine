"""
state_inspector.py

Utility for the `engine` package that provides a human-readable
inspection tool for WorldState objects.

Usage:
    from engine.state_inspector import render
    from src.state.world_state import WorldState

    state = WorldState(...)
    render(state)
"""

import dataclasses

from rich.console import Console
from rich.table import Table


def _get_fields(state):
    """
    Return an iterable of (field_name, value) pairs for the given state.
    Handles dataclasses, Pydantic BaseModel instances (WorldState), and
    falls back to vars() for anything else.
    """
    if dataclasses.is_dataclass(state):
        return [(f.name, getattr(state, f.name)) for f in dataclasses.fields(state)]
    if hasattr(state, "model_fields"):  # Pydantic v2 BaseModel
        return [(name, getattr(state, name)) for name in state.model_fields]
    return list(vars(state).items())


def _format_value(value) -> str:
    """Typed list fields (Fact/Claim/Goal/...) render as one item per line
    showing just the content and status, rather than the default Pydantic
    repr for every item."""
    if isinstance(value, list) and value and hasattr(value[0], "model_dump"):
        lines = []
        for item in value:
            data = item.model_dump()
            content = data.pop("content", data.pop("name", ""))
            extras = ", ".join(f"{k}={v}" for k, v in data.items() if v)
            lines.append(f"- {content}" + (f" ({extras})" if extras else ""))
        return "\n".join(lines)
    return str(value)


def render(state) -> None:
    """Pretty-print every field of a WorldState using Rich."""
    console = Console()

    table = Table(title="World State", show_lines=False)
    table.add_column("Field", style="bold cyan", no_wrap=True)
    table.add_column("Value", style="white")

    for field_name, value in _get_fields(state):
        table.add_row(field_name, _format_value(value))

    console.print(table)
