"""Child workflow forwarding activity.

Translated from go_companion/internal/agent/activities.go (ForwardToChildWorkflow)
Sends an update to a child workflow via Temporal client.
"""

from __future__ import annotations

from typing import Any

import structlog
from temporalio import activity
from temporalio.client import Client

from taskmeagents.conversation.types import Message

logger = structlog.get_logger()


@activity.defn(name="ForwardToChildWorkflow")
async def forward_to_child_workflow(
    child_workflow_id: str,
    update_name: str,
    update_args: list[Any],
) -> list[Message]:
    """Forward a message to a child workflow by sending an update.

    Creates a Temporal client connection and sends the specified update
    to the child workflow, returning the response messages.
    """
    from taskmeagents.temporal_.client import get_temporal_client

    client = get_temporal_client()
    handle = client.get_workflow_handle(child_workflow_id)

    try:
        result = await handle.execute_update(
            update_name,
            args=update_args,
        )
        return result or []
    except Exception as e:
        logger.error(
            "activity.forward_to_child.failed",
            child_workflow_id=child_workflow_id,
            update_name=update_name,
            error=str(e),
        )
        raise
