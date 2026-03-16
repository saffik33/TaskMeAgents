"""Chat command — interactive or batch conversation via WebSocket."""

from __future__ import annotations

import asyncio
import json

import typer
from rich.prompt import Prompt

from cli.output import (
    console,
    print_assistant,
    print_error,
    print_thinking,
    print_tool_request,
    print_tool_result,
    print_usage,
)

app = typer.Typer(no_args_is_help=True)


def _build_ws_url(server: str, api_key: str, agent_id: str, session_id: str | None) -> str:
    base = server.rstrip("/").replace("http://", "ws://").replace("https://", "wss://")
    url = f"{base}/ws/chat?api_key={api_key}&agent_id={agent_id}"
    if session_id:
        url += f"&session_id={session_id}"
    return url


async def _run_chat(server: str, api_key: str, agent_id: str, prompt: str | None, session_id: str | None) -> None:
    """Run the WebSocket chat loop."""
    import websockets

    url = _build_ws_url(server, api_key, agent_id, session_id)

    try:
        async with websockets.connect(url) as ws:
            # Wait for session_established
            raw = await ws.recv()
            msg = json.loads(raw)
            if msg.get("type") == "session_established":
                sid = msg["session_id"]
                console.print(f"[dim]Session: {sid}[/dim]\n")
            else:
                print_error(f"Unexpected first message: {msg}")
                return

            if prompt:
                # Batch mode: send single message, process response, exit
                await _send_and_process(ws, prompt)
            else:
                # Interactive mode
                console.print("[bold]TaskMe Agent Chat[/bold] (type 'exit' to quit, 'new' to reset)\n")
                while True:
                    try:
                        user_input = Prompt.ask("[bold green]You[/bold green]")
                    except (EOFError, KeyboardInterrupt):
                        user_input = "exit"

                    if not user_input.strip():
                        continue
                    if user_input.strip().lower() in ("exit", "quit"):
                        await ws.send(json.dumps({"type": "end_conversation", "reason": "User exited"}))
                        # Drain remaining messages
                        try:
                            async for raw_msg in ws:
                                msg = json.loads(raw_msg)
                                if msg.get("type") == "end":
                                    break
                        except Exception:
                            pass
                        break

                    await _send_and_process(ws, user_input)

    except websockets.exceptions.InvalidStatusCode as e:
        if e.status_code == 4001:
            print_error("Invalid API key")
        else:
            print_error(f"WebSocket connection failed: {e}")
    except ConnectionRefusedError:
        print_error(f"Cannot connect to server at {server}")
    except Exception as e:
        print_error(str(e))


async def _send_and_process(ws, content: str) -> None:
    """Send a user message and process all response messages."""
    await ws.send(json.dumps({"type": "user_message", "content": content}))

    while True:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=180)
        except asyncio.TimeoutError:
            print_error("Response timed out (3 minutes)")
            break

        msg = json.loads(raw)
        msg_type = msg.get("type", "")

        if msg_type == "assistant_message":
            print_assistant(msg.get("content", ""), msg.get("agent_id", ""), msg.get("is_final", False))
            if msg.get("is_final"):
                break

        elif msg_type == "assistant_thinking":
            print_thinking(msg.get("content", ""))

        elif msg_type == "tool_execution_request":
            print_tool_request(msg.get("tool_name", ""), msg.get("tool_type", "client"), msg.get("parameters", {}))
            # In simple CLI, auto-respond with empty result for client tools
            console.print("[dim]  (auto-responding — simple CLI)[/dim]")
            await ws.send(json.dumps({
                "type": "client_tool_result",
                "tool_use_id": msg.get("tool_use_id", ""),
                "tool_name": msg.get("tool_name", ""),
                "success": True,
                "content": "Tool execution not supported in simple CLI mode",
            }))

        elif msg_type == "tool_approval_request":
            print_tool_request(msg.get("tool_name", ""), "server", msg.get("parameters", {}))
            approved = Prompt.ask("  Approve?", choices=["y", "n"], default="y") == "y"
            await ws.send(json.dumps({
                "type": "server_tool_approval",
                "tool_use_id": msg.get("tool_use_id", ""),
                "tool_name": msg.get("tool_name", ""),
                "approved": approved,
                "rejection_reason": "" if approved else "User rejected",
            }))

        elif msg_type == "tool_result":
            print_tool_result(
                msg.get("tool_name", ""),
                msg.get("success", True),
                msg.get("content", ""),
                msg.get("was_auto_approved", False),
            )

        elif msg_type == "usage":
            print_usage(msg)

        elif msg_type == "error":
            print_error(msg.get("message", "Unknown error"))
            break

        elif msg_type == "end":
            break


@app.command("interactive")
def interactive(
    agent_id: str = typer.Argument(..., help="Agent ID to chat with"),
    server: str = typer.Option("http://localhost:8000", help="Server URL"),
    api_key: str = typer.Option(..., envvar="TASKME_API_KEY", help="API key"),
    session_id: str | None = typer.Option(None, help="Resume session ID"),
):
    """Start an interactive chat session with an agent."""
    asyncio.run(_run_chat(server, api_key, agent_id, None, session_id))


@app.command("send")
def send(
    agent_id: str = typer.Argument(..., help="Agent ID"),
    prompt: str = typer.Argument(..., help="Message to send"),
    server: str = typer.Option("http://localhost:8000", help="Server URL"),
    api_key: str = typer.Option(..., envvar="TASKME_API_KEY", help="API key"),
    session_id: str | None = typer.Option(None, help="Session ID"),
):
    """Send a single message (batch mode)."""
    asyncio.run(_run_chat(server, api_key, agent_id, prompt, session_id))
