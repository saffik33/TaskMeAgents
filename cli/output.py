"""Terminal output formatting using Rich."""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

console = Console()


def print_assistant(content: str, agent_id: str = "", is_final: bool = False) -> None:
    """Print an assistant message with markdown rendering."""
    label = f"[bold cyan]Assistant[/bold cyan]"
    if agent_id:
        label += f" [dim]({agent_id})[/dim]"
    console.print(label)
    console.print(Markdown(content))
    if is_final:
        console.print()


def print_thinking(content: str) -> None:
    """Print thinking/reasoning content."""
    console.print(Panel(content, title="[dim]Thinking[/dim]", border_style="dim", expand=False))


def print_tool_request(tool_name: str, tool_type: str, parameters: dict[str, Any]) -> None:
    """Print a tool execution/approval request."""
    icon = "🔧" if tool_type == "client" else "🌐"
    console.print(f"\n{icon} [bold yellow]Tool Request:[/bold yellow] {tool_name}")
    if parameters:
        for k, v in parameters.items():
            val_str = str(v)
            if len(val_str) > 200:
                val_str = val_str[:200] + "..."
            console.print(f"  [dim]{k}:[/dim] {val_str}")


def print_tool_result(tool_name: str, success: bool, content: str, auto_approved: bool = False) -> None:
    """Print a tool execution result."""
    status = "[green]✓[/green]" if success else "[red]✗[/red]"
    auto = " [dim](auto)[/dim]" if auto_approved else ""
    console.print(f"{status} [bold]{tool_name}[/bold]{auto}: {content[:300]}")


def print_usage(data: dict[str, Any]) -> None:
    """Print token usage info."""
    console.print(
        f"[dim]Tokens: in={data.get('input_tokens', 0)} out={data.get('output_tokens', 0)} "
        f"cost=${data.get('request_cost', 0):.4f} total=${data.get('total_cost', 0):.4f}[/dim]"
    )


def print_error(message: str) -> None:
    """Print an error message."""
    console.print(f"[bold red]Error:[/bold red] {message}")


def print_agents_table(agents: list[dict[str, Any]]) -> None:
    """Print agents in a formatted table."""
    table = Table(title="Agents")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Model")
    table.add_column("Version", justify="right")
    table.add_column("Sub-agents", justify="right")

    for a in agents:
        table.add_row(
            a["agent_id"],
            a["name"],
            a["model"],
            str(a.get("version", 1)),
            str(len(a.get("sub_agents", []))),
        )
    console.print(table)


def print_models_table(models: list[dict[str, Any]]) -> None:
    """Print models in a formatted table."""
    table = Table(title="Available Models")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Vendor")
    table.add_column("Context", justify="right")
    table.add_column("Input $/1M", justify="right")
    table.add_column("Output $/1M", justify="right")
    table.add_column("Tools")
    table.add_column("Thinking")

    for m in models:
        table.add_row(
            m["id"],
            m["display_name"],
            m["vendor"],
            f"{m['context_window']:,}",
            f"${m['input_price']:.2f}",
            f"${m['output_price']:.2f}",
            "✓" if m.get("supports_tool_use") else "✗",
            m.get("thinking_support", "none"),
        )
    console.print(table)
