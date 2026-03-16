"""Workflow tests for CleanupInactiveConversationsWorkflow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

pytestmark = pytest.mark.temporal

from taskmeagents.workflow.cleanup import (
    CleanupInactiveConversationsWorkflow,
    CleanupResult,
    cleanup_inactive_conversations_activity,
)


from temporalio import activity as activity_mod


@activity_mod.defn(name="cleanup_inactive_conversations_activity")
async def mock_cleanup_activity(threshold_minutes: int) -> CleanupResult:
    """Mock cleanup that reports finding and cleaning 2 workflows."""
    return CleanupResult(found_count=2, canceled_count=2)


@pytest.mark.asyncio
async def test_cleanup_workflow_runs():
    """Cleanup workflow executes activity and returns result."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test-queue",
            workflows=[CleanupInactiveConversationsWorkflow],
            activities=[mock_cleanup_activity],
        ):
            result = await env.client.execute_workflow(
                CleanupInactiveConversationsWorkflow.run,
                args=[30],
                id="cleanup-test-1",
                task_queue="test-queue",
            )

            assert result.found_count == 2
            assert result.canceled_count == 2
