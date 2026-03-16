"""E2E test for error recovery — fatal errors return generic message."""

from __future__ import annotations

import pytest
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

pytestmark = pytest.mark.temporal

from taskmeagents.activities.types import ActivityResult
from taskmeagents.workflow.companion_workflow import CompanionWorkflow


from temporalio import activity as activity_mod


@activity_mod.defn(name="ProcessUserMessage")
async def mock_failing_activity(*args):
    raise RuntimeError("Database connection lost")


@activity_mod.defn(name="PersistMessages")
async def mock_persist(*args):
    return None


@activity_mod.defn(name="ForwardToChildWorkflow")
async def mock_forward(*args):
    return []


@activity_mod.defn(name="RejectPendingTool")
async def mock_reject(*args):
    return ActivityResult(messages=[])


@activity_mod.defn(name="ExecuteServerTool")
async def mock_execute_tool(*args):
    return ActivityResult(messages=[])


@activity_mod.defn(name="ProcessClientToolResult")
async def mock_client_tool(*args):
    return ActivityResult(messages=[])


@activity_mod.defn(name="ProcessEndConversation")
async def mock_end(*args):
    return ActivityResult(messages=[], should_terminate=True)


@pytest.mark.asyncio
async def test_fatal_error_returns_generic_message():
    """When an activity crashes, the workflow returns a generic error message."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test-queue",
            workflows=[CompanionWorkflow],
            activities=[
                mock_failing_activity,  # ProcessUserMessage will fail
                mock_persist, mock_end, mock_reject,
                mock_execute_tool, mock_client_tool, mock_forward,
            ],
        ):
            handle = await env.client.start_workflow(
                CompanionWorkflow.run,
                args=["test-agent", 0, "user-1"],
                id="error-test-1",
                task_queue="test-queue",
            )

            messages = await handle.execute_update(
                CompanionWorkflow.process_user_message,
                args=["Hello", "msg-1", {}],
            )

            # Should get a generic error message, not the raw exception
            assert len(messages) >= 1
            error_msg = messages[0]
            assert error_msg.assistant_message is not None
            assert "internal error" in error_msg.assistant_message.content.lower()
