"""TaskMe Agents CLI — simple client for testing and management.

Commands:
  chat        — interactive or batch conversation
  agent       — agent CRUD management
  create-key  — create a new API key (bootstrap)
"""

from __future__ import annotations

import typer

from cli.commands.agent import app as agent_app
from cli.commands.chat import app as chat_app

app = typer.Typer(name="taskme-cli", help="TaskMe Agents CLI", no_args_is_help=True)
app.add_typer(chat_app, name="chat", help="Start a conversation with an agent")
app.add_typer(agent_app, name="agent", help="Manage agents")


@app.command()
def create_key(
    name: str = typer.Option("admin", help="Key name"),
    user_id: str = typer.Option("admin", help="User ID to associate"),
    server: str = typer.Option("http://localhost:8000", help="Server URL"),
):
    """Create a new API key (for bootstrapping — requires ADMIN_API_KEY env var on server)."""
    from cli.client import RestClient

    client = RestClient(server)
    # This uses a direct DB insert approach for bootstrap
    typer.echo(f"To create an API key, set ADMIN_API_KEY in .env and restart the server.")
    typer.echo(f"The key will be seeded automatically on startup.")
    typer.echo(f"Or use the REST API: POST /api/keys with X-API-Key header")


if __name__ == "__main__":
    app()
