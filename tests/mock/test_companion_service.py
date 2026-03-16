"""Mock tests for the companion stream handler service."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from taskmeagents.conversation.types import (
    AssistantMessage,
    Message,
    MessageRole,
    ToolRequestMessage,
    ToolType,
)
from taskmeagents.services.companion import (
    check_workflow_exists,
    ensure_workflow,
    process_and_stream_messages,
)


@pytest.mark.asyncio
async def test_ensure_workflow_creates_new():
    mock_client = AsyncMock()
    mock_client.start_workflow = AsyncMock()

    with patch("taskmeagents.services.companion.check_workflow_exists", return_value=False):
        wf_id = await ensure_workflow(mock_client, "agent-1", "user-1", None)

    assert wf_id  # UUID generated
    mock_client.start_workflow.assert_called_once()


@pytest.mark.asyncio
async def test_ensure_workflow_resumes():
    mock_client = AsyncMock()

    with patch("taskmeagents.services.companion.check_workflow_exists", return_value=True):
        wf_id = await ensure_workflow(mock_client, "agent-1", "user-1", "existing-session")

    assert wf_id == "existing-session"
    mock_client.start_workflow.assert_not_called()


@pytest.mark.asyncio
async def test_two_phase_streaming_context_first():
    """Verify assistant messages stream before tool requests."""
    mock_ws = AsyncMock()
    mock_client = AsyncMock()
    sent_types = []

    async def track_send(data):
        sent_types.append(data.get("type"))

    mock_ws.send_json = track_send

    messages = [
        Message(id="1", role=MessageRole.ASSISTANT, tool_request=ToolRequestMessage(
            tool_use_id="tu-1", tool_name="search", tool_type=ToolType.CLIENT, parameters={})),
        Message(id="2", role=MessageRole.ASSISTANT, assistant_message=AssistantMessage(
            content="Let me search.", is_final=False)),
    ]

    await process_and_stream_messages(mock_client, mock_ws, "wf-1", "agent-1", messages, {})

    # Assistant message (context) should come before tool request (action)
    assert sent_types.index("assistant_message") < sent_types.index("tool_execution_request")


@pytest.mark.asyncio
async def test_auto_approve_recursion():
    """Auto-approved server tool triggers recursive execution."""
    mock_ws = AsyncMock()
    mock_ws.send_json = AsyncMock()
    mock_client = AsyncMock()

    # First call: auto-approved tool request
    auto_tool = Message(id="1", role=MessageRole.ASSISTANT, tool_request=ToolRequestMessage(
        tool_use_id="tu-1", tool_name="auto_tool", tool_type=ToolType.SERVER, auto_approve=True, parameters={}))

    # The recursive call after approval returns a final assistant message
    final_msg = Message(id="2", role=MessageRole.ASSISTANT, assistant_message=AssistantMessage(
        content="Done!", is_final=True))

    with patch("taskmeagents.services.companion.send_workflow_update", return_value=[final_msg]) as mock_update:
        await process_and_stream_messages(mock_client, mock_ws, "wf-1", "agent-1", [auto_tool], {})

    # Verify approval update was sent
    mock_update.assert_called_once()
    call_args = mock_update.call_args
    assert call_args[0][2] == "ProcessServerToolApproval"  # update_name


@pytest.mark.asyncio
async def test_agent_tool_delegation():
    """Agent tool triggers ProcessAgentTool update."""
    mock_ws = AsyncMock()
    mock_ws.send_json = AsyncMock()
    mock_client = AsyncMock()

    agent_tool = Message(id="1", role=MessageRole.ASSISTANT, tool_request=ToolRequestMessage(
        tool_use_id="tu-1", tool_name="_sub-agent", tool_type=ToolType.AGENT, parameters={"task": "research"}))

    final_msg = Message(id="2", role=MessageRole.ASSISTANT, assistant_message=AssistantMessage(
        content="Sub-agent done.", is_final=True))

    with patch("taskmeagents.services.companion.send_workflow_update", return_value=[final_msg]) as mock_update:
        await process_and_stream_messages(mock_client, mock_ws, "wf-1", "agent-1", [agent_tool], {})

    mock_update.assert_called_once()
    assert mock_update.call_args[0][2] == "ProcessAgentTool"
