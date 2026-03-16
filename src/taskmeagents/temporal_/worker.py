"""Temporal worker registration and startup.

Translated from go_companion/internal/temporal/worker.go
Registers workflows and activities, runs worker in background.
"""

from __future__ import annotations

import structlog
from temporalio.client import Client
from temporalio.worker import Worker

from taskmeagents.activities.conversation import (
    process_client_tool_result,
    process_end_conversation,
    process_user_message,
    reject_pending_tool,
)
from taskmeagents.activities.delegation import forward_to_child_workflow
from taskmeagents.activities.mcp_tools import execute_server_tool
from taskmeagents.activities.persistence import persist_messages
from taskmeagents.config import settings
from taskmeagents.workflow.cleanup import CleanupInactiveConversationsWorkflow, cleanup_inactive_conversations_activity
from taskmeagents.workflow.companion_workflow import CompanionWorkflow

logger = structlog.get_logger()


async def run_worker(client: Client) -> None:
    """Run the Temporal worker with all workflows and activities registered."""
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[
            CompanionWorkflow,
            CleanupInactiveConversationsWorkflow,
        ],
        activities=[
            process_user_message,
            process_client_tool_result,
            process_end_conversation,
            reject_pending_tool,
            execute_server_tool,
            forward_to_child_workflow,
            persist_messages,
            cleanup_inactive_conversations_activity,
        ],
    )

    logger.info(
        "temporal.worker.starting",
        task_queue=settings.temporal_task_queue,
        workflows=["CompanionWorkflow", "CleanupInactiveConversationsWorkflow"],
        activity_count=8,
    )

    await worker.run()
