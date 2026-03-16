"""Agent management commands."""

from __future__ import annotations

import json
from typing import Any

import typer

from cli.client import RestClient
from cli.output import console, print_agents_table, print_error, print_models_table

app = typer.Typer(no_args_is_help=True)


def _client(server: str, api_key: str) -> RestClient:
    return RestClient(server, api_key)


@app.command("list")
def list_agents(
    server: str = typer.Option("http://localhost:8000", help="Server URL"),
    api_key: str = typer.Option(..., envvar="TASKME_API_KEY", help="API key"),
):
    """List all agents."""
    try:
        agents = _client(server, api_key).list_agents()
        if not agents:
            console.print("[dim]No agents found[/dim]")
            return
        print_agents_table(agents)
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)


@app.command("get")
def get_agent(
    agent_id: str = typer.Argument(..., help="Agent ID"),
    server: str = typer.Option("http://localhost:8000", help="Server URL"),
    api_key: str = typer.Option(..., envvar="TASKME_API_KEY", help="API key"),
):
    """Get agent details."""
    try:
        agent = _client(server, api_key).get_agent(agent_id)
        console.print_json(json.dumps(agent, indent=2, default=str))
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)


@app.command("create")
def create_agent(
    config_file: str = typer.Argument(..., help="Path to JSON config file"),
    server: str = typer.Option("http://localhost:8000", help="Server URL"),
    api_key: str = typer.Option(..., envvar="TASKME_API_KEY", help="API key"),
):
    """Create an agent from a JSON config file."""
    try:
        with open(config_file) as f:
            data = json.load(f)
        agent = _client(server, api_key).create_agent(data)
        console.print(f"[green]Created agent:[/green] {agent['agent_id']} (v{agent['version']})")
    except FileNotFoundError:
        print_error(f"Config file not found: {config_file}")
        raise typer.Exit(1)
    except json.JSONDecodeError as e:
        print_error(f"Invalid JSON: {e}")
        raise typer.Exit(1)
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)


@app.command("update")
def update_agent(
    agent_id: str = typer.Argument(..., help="Agent ID"),
    config_file: str = typer.Argument(..., help="Path to JSON config file with fields to update"),
    server: str = typer.Option("http://localhost:8000", help="Server URL"),
    api_key: str = typer.Option(..., envvar="TASKME_API_KEY", help="API key"),
):
    """Update an agent from a JSON config file (partial update)."""
    try:
        with open(config_file) as f:
            data = json.load(f)
        agent = _client(server, api_key).update_agent(agent_id, data)
        console.print(f"[green]Updated agent:[/green] {agent['agent_id']} (v{agent['version']})")
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)


@app.command("delete")
def delete_agent(
    agent_id: str = typer.Argument(..., help="Agent ID"),
    server: str = typer.Option("http://localhost:8000", help="Server URL"),
    api_key: str = typer.Option(..., envvar="TASKME_API_KEY", help="API key"),
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Delete an agent."""
    if not confirm:
        typer.confirm(f"Delete agent '{agent_id}'?", abort=True)
    try:
        _client(server, api_key).delete_agent(agent_id)
        console.print(f"[green]Deleted agent:[/green] {agent_id}")
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)


@app.command("models")
def list_models(
    server: str = typer.Option("http://localhost:8000", help="Server URL"),
    api_key: str = typer.Option(..., envvar="TASKME_API_KEY", help="API key"),
):
    """List available LLM models."""
    try:
        models = _client(server, api_key).list_models()
        print_models_table(models)
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)


@app.command("sessions")
def list_sessions(
    server: str = typer.Option("http://localhost:8000", help="Server URL"),
    api_key: str = typer.Option(..., envvar="TASKME_API_KEY", help="API key"),
):
    """List recent chat sessions."""
    try:
        data = _client(server, api_key).list_sessions()
        sessions = data.get("sessions", [])
        if not sessions:
            console.print("[dim]No sessions found[/dim]")
            return
        from rich.table import Table

        table = Table(title="Sessions")
        table.add_column("ID", style="cyan", max_width=36)
        table.add_column("Agent", style="bold")
        table.add_column("Status")
        table.add_column("Turns", justify="right")
        for s in sessions:
            status_style = "green" if s["status"] == "running" else "dim"
            table.add_row(s["id"], s["agent_id"], f"[{status_style}]{s['status']}[/{status_style}]", str(s["turn_count"]))
        console.print(table)
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)
