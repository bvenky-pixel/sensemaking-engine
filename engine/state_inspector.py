from dataclasses import asdict
from rich.console import Console
from rich.table import Table

console = Console()

def render(state):
    """
    Render the current ConversationState as a table.
    """

    table = Table(title="Conversation State")

    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")

    for field, value in asdict(state).items():
        table.add_row(field, str(value))

    console.print(table)
    