"""MCP tool execution activity.

Translated from the ExecuteServerTool part of go_companion/internal/agent/activities.go
Executes an MCP tool, then calls the LLM with the result.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from temporalio import activity

from taskmeagents.activities.types import ActivityInput, ActivityResult
from taskmeagents.conversation.types import Message, MessageRole, ToolResultMessage, ToolType

logger = structlog.get_logger()


@activity.defn(name="ExecuteServerTool")
async def execute_server_tool(
    input_: ActivityInput,
    tool_use_id: str,
    tool_name: str,
    parameters: dict[str, Any],
) -> ActivityResult:
    """Execute an MCP server tool, then call LLM with the result.

    Tool name format: "{serverName}_{toolName}"
    Parse to find server_id via agent's server_name_to_id map.
    """
    from taskmeagents.activities.conversation import _generate_and_aggregate, _get_agent, _load_and_merge_history
    from taskmeagents.mcp.registry import get_mcp_registry

    agent = await _get_agent(input_.agent_id, input_.is_sub_agent)
    registry = get_mcp_registry()

    # Parse tool name: "{serverName}_{actualToolName}"
    parts = tool_name.split("_", 1)
    if len(parts) != 2:
        # Return error result
        tool_result_msg = Message(
            id=str(uuid.uuid4()),
            role=MessageRole.USER,
            tool_result=ToolResultMessage(
                tool_use_id=tool_use_id,
                tool_name=tool_name,
                tool_type=ToolType.SERVER,
                success=False,
                content=f"Invalid tool name format: {tool_name}",
            ),
        )
        input_.pending_writes.append(tool_result_msg)
        history = await _load_and_merge_history(input_)
        return await _generate_and_aggregate(agent, history, input_.context)

    server_name, actual_tool_name = parts

    # Look up MCP server ID from agent's mapping
    server_id = agent.server_name_to_id.get(server_name, "")
    if not server_id:
        tool_result_msg = Message(
            id=str(uuid.uuid4()),
            role=MessageRole.USER,
            tool_result=ToolResultMessage(
                tool_use_id=tool_use_id,
                tool_name=tool_name,
                tool_type=ToolType.SERVER,
                success=False,
                content=f"MCP server not found for: {server_name}",
            ),
        )
        input_.pending_writes.append(tool_result_msg)
        history = await _load_and_merge_history(input_)
        return await _generate_and_aggregate(agent, history, input_.context)

    # Execute the tool
    try:
        text_content, result_data, is_error = await registry.execute_tool(
            server_id, actual_tool_name, parameters, input_.mcp_headers
        )
        tool_result_msg = Message(
            id=str(uuid.uuid4()),
            role=MessageRole.USER,
            tool_result=ToolResultMessage(
                tool_use_id=tool_use_id,
                tool_name=tool_name,
                tool_type=ToolType.SERVER,
                success=not is_error,
                content=text_content,
                data=result_data,
            ),
        )
    except Exception as e:
        logger.error("mcp.tool.execution.failed", tool_name=tool_name, error=str(e))
        tool_result_msg = Message(
            id=str(uuid.uuid4()),
            role=MessageRole.USER,
            tool_result=ToolResultMessage(
                tool_use_id=tool_use_id,
                tool_name=tool_name,
                tool_type=ToolType.SERVER,
                success=False,
                content=f"Tool execution failed: {e}",
            ),
        )

    # Add tool result to pending writes and call LLM
    input_.pending_writes.append(tool_result_msg)
    history = await _load_and_merge_history(input_)
    return await _generate_and_aggregate(agent, history, input_.context)
