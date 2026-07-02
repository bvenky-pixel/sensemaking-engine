"""
state_inspector.py

Utility for the `engine` package that provides a human-readable
inspection tool for ConversationState objects.

Usage:
    from engine.state_inspector import render
    from engine.state import ConversationState

    state = ConversationState(...)
    render(state)
"""

import dataclasses

from rich.console import Console
from rich.table import Table


def _get_fields(state):
    """
    Return an iterable of (field_name, value) pairs for the given state.
    Falls back to vars() for non-dataclass objects so this keeps working
    if ConversationState's implementation ever changes.
    """
    if dataclasses.is_dataclass(state):
        return [(f.name, getattr(state, f.name)) for f in dataclasses.fields(state)]
    return list(vars(state).items())


def render(state) -> None:
    """Pretty-print every field of a ConversationState using Rich."""
    console = Console()

    table = Table(title="Conversation State", show_lines=False)
    table.add_column("Field", style="bold cyan", no_wrap=True)
    table.add_column("Value", style="white")

    for field_name, value in _get_fields(state):
        table.add_row(field_name, str(value))

    console.print(table)
