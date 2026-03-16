"""Scheduled cleanup workflow for inactive conversations.

Translated from go_companion/internal/workflow/cleanup.go

Scans for running CompanionWorkflow instances whose LastActivityTime
exceeds the inactivity threshold and sends EndConversation to each.
Falls back to CancelWorkflow if the update fails.
"""

from __future__ import annotations

import uuid as uuid_mod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from temporalio import activity, workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    import structlog
    from taskmeagents.workflow.companion_workflow import CompanionWorkflow

logger = structlog.get_logger()


@dataclass
class CleanupResult:
    found_count: int = 0
    canceled_count: int = 0


# --- Workflow ---

@workflow.defn
class CleanupInactiveConversationsWorkflow:
    """Scheduled workflow that cleans up inactive conversation workflows.

    Triggered on a schedule (e.g., every 10 minutes via Temporal Schedule).
    Queries for running CompanionWorkflows with stale LastActivityTime,
    sends EndConversation to each, and falls back to cancel if that fails.
    """

    @workflow.run
    async def run(self, inactivity_threshold_minutes: int = 30) -> CleanupResult:
        workflow.logger.info(
            "Starting cleanup of inactive conversations",
            extra={"threshold_minutes": inactivity_threshold_minutes},
        )

        result: CleanupResult = await workflow.execute_activity(
            cleanup_inactive_conversations_activity,
            args=[inactivity_threshold_minutes],
            start_to_close_timeout=timedelta(minutes=15),
            heartbeat_timeout=timedelta(minutes=2),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=1),
                maximum_interval=timedelta(minutes=1),
                backoff_coefficient=2.0,
            ),
        )

        workflow.logger.info(
            "Cleanup completed",
            extra={"found": result.found_count, "canceled": result.canceled_count},
        )
        return result


# --- Activity ---

@activity.defn
async def cleanup_inactive_conversations_activity(
    inactivity_threshold_minutes: int,
) -> CleanupResult:
    """Scan inactive workflows and send EndConversation to each.

    Uses Temporal's visibility query with LastActivityTime search attribute.
    Falls back to CancelWorkflow if EndConversation update fails.
    """
    from taskmeagents.temporal_.client import get_temporal_client

    client = get_temporal_client()
    result = CleanupResult()

    threshold_time = datetime.now(timezone.utc) - timedelta(minutes=inactivity_threshold_minutes)
    query = (
        f'WorkflowType="CompanionWorkflow" '
        f'AND ExecutionStatus="Running" '
        f'AND LastActivityTime < "{threshold_time.strftime("%Y-%m-%dT%H:%M:%SZ")}"'
    )

    logger.info(
        "cleanup.activity.started",
        threshold_minutes=inactivity_threshold_minutes,
        query=query,
    )

    reason = "Session ended due to inactivity"

    async for workflow_exec in client.list_workflows(query):
        result.found_count += 1
        wf_id = workflow_exec.id

        # Heartbeat before each workflow operation
        activity.heartbeat(result)

        # Check for cancellation
        if activity.is_cancelled():
            logger.info(
                "cleanup.activity.cancelled",
                found=result.found_count,
                canceled=result.canceled_count,
            )
            break

        # Try graceful EndConversation first
        try:
            handle = client.get_workflow_handle(wf_id)
            message_id = str(uuid_mod.uuid4())
            await handle.execute_update(
                CompanionWorkflow.process_end_conversation,
                args=[reason, message_id, {}],
                id=str(uuid_mod.uuid4()),
            )
            result.canceled_count += 1
            logger.info("cleanup.activity.ended_conversation", workflow_id=wf_id)

        except Exception as update_err:
            logger.warning(
                "cleanup.activity.end_conversation_failed",
                workflow_id=wf_id,
                error=str(update_err),
            )

            # Fallback: cancel the workflow directly
            try:
                handle = client.get_workflow_handle(wf_id)
                await handle.cancel()
                result.canceled_count += 1
                logger.info("cleanup.activity.cancelled_workflow", workflow_id=wf_id)
            except Exception as cancel_err:
                logger.error(
                    "cleanup.activity.cancel_failed",
                    workflow_id=wf_id,
                    error=str(cancel_err),
                )

    logger.info(
        "cleanup.activity.completed",
        found=result.found_count,
        canceled=result.canceled_count,
    )
    return result
