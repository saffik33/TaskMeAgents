"""Workflow tests for CompanionWorkflow using Temporal test environment.

These tests verify the workflow state machine and update handler logic
using mocked activities.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.temporal  # all tests in this file require Temporal
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from taskmeagents.activities.types import ActivityResult
from taskmeagents.conversation.types import AssistantMessage, Message, MessageRole
from taskmeagents.workflow.companion_workflow import CompanionWorkflow


from temporalio import activity as activity_mod


def _make_activity_result(content: str = "Hello!", should_terminate: bool = False) -> ActivityResult:
    msg = Message(
        id="resp-1",
        role=MessageRole.ASSISTANT,
        assistant_message=AssistantMessage(content=content, is_final=True),
    )
    return ActivityResult(messages=[msg], should_terminate=should_terminate)


# Mocked activities — must be decorated with @activity.defn and match registered names
@activity_mod.defn(name="ProcessUserMessage")
async def mock_process_user_message(*args) -> ActivityResult:
    return _make_activity_result("I got your message!")


@activity_mod.defn(name="ProcessEndConversation")
async def mock_process_end_conversation(*args) -> ActivityResult:
    return _make_activity_result("Goodbye!", should_terminate=False)


@activity_mod.defn(name="RejectPendingTool")
async def mock_reject_pending_tool(*args) -> ActivityResult:
    return _make_activity_result("Tool was rejected.")


@activity_mod.defn(name="PersistMessages")
async def mock_persist_messages(*args) -> None:
    return None


@activity_mod.defn(name="ExecuteServerTool")
async def mock_execute_server_tool(*args) -> ActivityResult:
    return _make_activity_result("Tool result: sunny")


@activity_mod.defn(name="ProcessClientToolResult")
async def mock_process_client_tool_result(*args) -> ActivityResult:
    return _make_activity_result("Got your tool result!")


@activity_mod.defn(name="ForwardToChildWorkflow")
async def mock_forward_to_child(*args) -> list[Message]:
    return []


@pytest.mark.asyncio
async def test_workflow_starts_and_waits():
    """Workflow starts, initializes state, and waits for termination."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test-queue",
            workflows=[CompanionWorkflow],
            activities=[
                mock_process_user_message, mock_persist_messages,
                mock_process_end_conversation, mock_reject_pending_tool,
                mock_execute_server_tool, mock_process_client_tool_result,
                mock_forward_to_child,
            ],
        ):
            handle = await env.client.start_workflow(
                CompanionWorkflow.run,
                args=["test-agent", 0, "user-1"],
                id="test-wf-1",
                task_queue="test-queue",
            )
            # Workflow should be running
            desc = await handle.describe()
            assert desc.status.name == "RUNNING"

            # End it
            await handle.execute_update(
                CompanionWorkflow.process_end_conversation,
                args=["done", "msg-end", {}],
            )

            # Should complete
            await handle.result()


@pytest.mark.asyncio
async def test_user_message_update():
    """Send user message update → activity called → messages returned."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test-queue",
            workflows=[CompanionWorkflow],
            activities=[
                mock_process_user_message, mock_persist_messages,
                mock_process_end_conversation, mock_reject_pending_tool,
                mock_execute_server_tool, mock_process_client_tool_result,
                mock_forward_to_child,
            ],
        ):
            handle = await env.client.start_workflow(
                CompanionWorkflow.run,
                args=["test-agent", 0, "user-1"],
                id="test-wf-2",
                task_queue="test-queue",
            )

            messages = await handle.execute_update(
                CompanionWorkflow.process_user_message,
                args=["Hello", "msg-1", {}],
            )

            assert len(messages) >= 1

            # Cleanup
            await handle.execute_update(
                CompanionWorkflow.process_end_conversation,
                args=["done", "msg-end", {}],
            )
            await handle.result()
