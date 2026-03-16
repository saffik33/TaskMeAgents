"""Stream handler — bridges WebSocket ↔ Temporal workflow.

Translated from go_companion/internal/workflow/stream_handler.go
(HandleStream + processAndStreamMessages)

Handles:
- Workflow lifecycle (create/resume)
- Message routing to update handlers
- Two-phase streaming (context → actions → auto-approve recursion)
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from starlette.websockets import WebSocket
from temporalio.client import Client, WorkflowHandle
from temporalio.service import RPCError

from taskmeagents.config import settings
from taskmeagents.conversation.types import Message, ToolType
from taskmeagents.schemas.chat import (
    WsAssistantMessage,
    WsAssistantThinking,
    WsEnd,
    WsError,
    WsToolApprovalRequest,
    WsToolExecutionRequest,
    WsToolResult,
    WsUsage,
)
from taskmeagents.workflow.companion_workflow import CompanionWorkflow
from taskmeagents.workflow.constants import (
    MAX_AUTO_APPROVE_DEPTH,
    UPDATE_PROCESS_AGENT_TOOL,
    UPDATE_PROCESS_CLIENT_TOOL_RESULT,
    UPDATE_PROCESS_END_CONVERSATION,
    UPDATE_PROCESS_SERVER_TOOL_APPROVAL,
    UPDATE_PROCESS_USER_MESSAGE,
)

logger = structlog.get_logger()


async def check_workflow_exists(client: Client, workflow_id: str) -> bool:
    """Check if a Temporal workflow exists and is running."""
    try:
        handle = client.get_workflow_handle(workflow_id)
        desc = await handle.describe()
        return desc.status is not None and desc.status.name in ("RUNNING", "COMPLETED")
    except RPCError:
        return False


async def ensure_workflow(
    client: Client,
    agent_id: str,
    user_id: str,
    session_id: str | None,
) -> str:
    """Ensure a workflow exists. Creates one if session_id is None or not found."""
    if session_id and await check_workflow_exists(client, session_id):
        return session_id

    workflow_id = session_id or str(uuid.uuid4())
    await client.start_workflow(
        CompanionWorkflow.run,
        args=[agent_id, 0, user_id],  # parentDepth=0 for root
        id=workflow_id,
        task_queue=settings.temporal_task_queue,
    )
    return workflow_id


async def send_workflow_update(
    client: Client,
    workflow_id: str,
    update_name: str,
    args: list[Any],
    update_id: str = "",
) -> list[Message]:
    """Send an update to the workflow and wait for result."""
    handle = client.get_workflow_handle(workflow_id)
    update_id = update_id or str(uuid.uuid4())

    # Map update name to the workflow method
    update_method = {
        UPDATE_PROCESS_USER_MESSAGE: CompanionWorkflow.process_user_message,
        UPDATE_PROCESS_SERVER_TOOL_APPROVAL: CompanionWorkflow.process_server_tool_approval,
        UPDATE_PROCESS_CLIENT_TOOL_RESULT: CompanionWorkflow.process_client_tool_result,
        UPDATE_PROCESS_END_CONVERSATION: CompanionWorkflow.process_end_conversation,
        UPDATE_PROCESS_AGENT_TOOL: CompanionWorkflow.process_agent_tool,
    }.get(update_name)

    if not update_method:
        raise ValueError(f"Unknown update name: {update_name}")

    result = await handle.execute_update(
        update_method,
        args=args,
        id=update_id,
    )
    return result or []


async def process_and_stream_messages(
    client: Client,
    ws: WebSocket,
    workflow_id: str,
    agent_id: str,
    messages: list[Message],
    mcp_headers: dict[str, str],
    depth: int = 0,
) -> None:
    """Two-phase message streaming with auto-approve recursion.

    Phase 1a: Stream assistant messages + tool results (context)
    Phase 1b: Stream tool approval/execution requests (actions)
    Phase 2: Execute deferred tools (agent + auto-approved server), recurse
    """
    if depth > MAX_AUTO_APPROVE_DEPTH:
        await ws.send_json(WsError(message="Recursion limit exceeded; possible tool loop", code="LOOP_DETECTED").model_dump())
        return

    deferred_tools: list[Message] = []
    approval_requests: list[Message] = []

    # Phase 1: classify and stream
    for msg in messages:
        # Agent tools → deferred
        if msg.tool_request and msg.tool_request.tool_type == ToolType.AGENT:
            deferred_tools.append(msg)
            continue

        # Auto-approved server tools → deferred
        if msg.tool_request and msg.tool_request.tool_type == ToolType.SERVER and msg.tool_request.auto_approve:
            deferred_tools.append(msg)
            continue

        # Non-auto-approved tool requests → approval requests (streamed after context)
        if msg.tool_request:
            approval_requests.append(msg)
            continue

        # Phase 1a: stream assistant messages, tool results, usage immediately
        await _stream_message(ws, msg, agent_id)

    # Phase 1b: stream approval/execution requests
    for msg in approval_requests:
        await _stream_tool_request(ws, msg)

    # Phase 2: handle deferred tools
    for msg in deferred_tools:
        tr = msg.tool_request

        if tr.tool_type == ToolType.AGENT:
            # Agent tool → delegate via ProcessAgentTool update
            new_messages = await send_workflow_update(
                client, workflow_id, UPDATE_PROCESS_AGENT_TOOL,
                [tr.tool_name, tr.tool_use_id, tr.parameters, mcp_headers],
            )
            await process_and_stream_messages(client, ws, workflow_id, agent_id, new_messages, mcp_headers, depth + 1)

        elif tr.tool_type == ToolType.SERVER and tr.auto_approve:
            # Auto-approved server tool → send approval
            new_messages = await send_workflow_update(
                client, workflow_id, UPDATE_PROCESS_SERVER_TOOL_APPROVAL,
                [tr.tool_use_id, tr.tool_name, True, "", mcp_headers],
            )
            # Mark results as auto-approved
            for m in new_messages:
                if m.tool_result:
                    m.tool_result.was_auto_approved = True
            await process_and_stream_messages(client, ws, workflow_id, agent_id, new_messages, mcp_headers, depth + 1)


async def _stream_message(ws: WebSocket, msg: Message, agent_id: str) -> None:
    """Stream a single message to the WebSocket client."""
    if msg.assistant_message:
        if msg.assistant_message.thinking:
            await ws.send_json(WsAssistantThinking(content=msg.assistant_message.thinking).model_dump())
        await ws.send_json(WsAssistantMessage(
            content=msg.assistant_message.content,
            is_final=msg.assistant_message.is_final,
            message_id=msg.id,
            agent_id=msg.agent_id or agent_id,
        ).model_dump())

    elif msg.tool_result:
        await ws.send_json(WsToolResult(
            tool_name=msg.tool_result.tool_name,
            tool_use_id=msg.tool_result.tool_use_id,
            success=msg.tool_result.success,
            content=msg.tool_result.content,
            data=msg.tool_result.data,
            was_auto_approved=msg.tool_result.was_auto_approved,
        ).model_dump())

    if msg.usage:
        await ws.send_json(WsUsage(
            input_tokens=msg.usage.input_tokens,
            output_tokens=msg.usage.output_tokens,
            cache_read_tokens=msg.usage.cache_read_tokens,
            cache_write_tokens=msg.usage.cache_write_tokens,
            total_input_tokens=msg.usage.total_input_tokens,
            total_output_tokens=msg.usage.total_output_tokens,
            total_cost=msg.usage.total_cost,
            request_cost=msg.usage.request_cost,
        ).model_dump())


async def _stream_tool_request(ws: WebSocket, msg: Message) -> None:
    """Stream a tool request (approval or execution) to the client."""
    tr = msg.tool_request
    if tr.tool_type == ToolType.CLIENT:
        await ws.send_json(WsToolExecutionRequest(
            tool_name=tr.tool_name,
            tool_use_id=tr.tool_use_id,
            parameters=tr.parameters,
            tool_type="client",
            description=tr.description,
        ).model_dump())
    else:
        await ws.send_json(WsToolApprovalRequest(
            tool_name=tr.tool_name,
            tool_use_id=tr.tool_use_id,
            parameters=tr.parameters,
            description=tr.description,
        ).model_dump())
