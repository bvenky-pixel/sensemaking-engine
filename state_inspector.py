"""
state_inspector.py

Utility module for the `engine` package that provides a simple, human-readable
inspection tool for ConversationState objects.

Usage:
    from engine.state_inspector import render
    from engine.state import ConversationState

    state = ConversationState(...)
    render(state)

This prints a two-column table (Field / Value) to the terminal using the
Rich library, which is useful for debugging conversation state at any point
during a run.
"""

import dataclasses

from rich.console import Console
from rich.table import Table

# Import is deferred/optional at type-check time only; ConversationState is
# passed in by the caller, so we don't hard-require the import here to avoid
# circular-import issues between engine.state and engine.state_inspector.
# If you want static type checking, uncomment the line below:
# from engine.state import ConversationState


def _get_fields(state):
    """
    Return an iterable of (field_name, value) pairs for the given state object.

    Supports two common cases:
    1. `state` is a dataclass (preferred) -> use dataclasses.fields()
    2. `state` is a plain object/namespace -> fall back to vars()

    This keeps render() working even if ConversationState's implementation
    changes from a dataclass to a regular class later on.
    """
    if dataclasses.is_dataclass(state):
        return [
            (f.name, getattr(state, f.name))
            for f in dataclasses.fields(state)
        ]
    # Fallback for plain objects: use instance __dict__
    return list(vars(state).items())


def render(state) -> None:
    """
    Pretty-print every field of a ConversationState using Rich.

    Displays the state as a table with two columns: "Field" and "Value".
    Values are converted to strings via str() so nested objects (lists,
    dicts, dataclasses, enums, etc.) are still shown, just not deeply
    formatted.

    Args:
        state: A ConversationState instance (or any dataclass / simple
               object) to inspect.
    """
    console = Console()

    table = Table(title="ConversationState", show_lines=False)
    table.add_column("Field", style="bold cyan", no_wrap=True)
    table.add_column("Value", style="white")

    for field_name, value in _get_fields(state):
        table.add_row(field_name, str(value))

    console.print(table)
