"""Persistence activity — writes messages to PostgreSQL.

Translated from the PersistMessages part of go_companion/internal/agent/activities.go

This is the ONLY activity that writes to the database.
Uses atomic transactions with INSERT ON CONFLICT DO NOTHING for idempotency.
"""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from temporalio import activity

from taskmeagents.activities.types import PersistInput
from taskmeagents.conversation.types import Message
from taskmeagents.history.store import MessageDocument, SessionData

logger = structlog.get_logger()


def _message_to_doc(msg: Message, session_id: str, sequence: int) -> MessageDocument:
    """Convert a Message to a MessageDocument for persistence."""
    content: dict = {}

    if msg.user_message:
        role = "user"
        content = {"content": msg.user_message.content}
        if msg.user_message.was_blocked:
            content["was_blocked"] = True
    elif msg.assistant_message:
        role = "assistant"
        content = {"content": msg.assistant_message.content}
        if msg.assistant_message.thinking:
            content["thinking"] = msg.assistant_message.thinking
        if msg.assistant_message.is_final:
            content["is_final"] = True
    elif msg.tool_request:
        role = "tool_request"
        content = {
            "tool_use_id": msg.tool_request.tool_use_id,
            "tool_name": msg.tool_request.tool_name,
            "tool_type": msg.tool_request.tool_type.value if msg.tool_request.tool_type else "server",
            "parameters": msg.tool_request.parameters,
            "auto_approve": msg.tool_request.auto_approve,
        }
    elif msg.tool_result:
        role = "tool_result"
        content = {
            "tool_use_id": msg.tool_result.tool_use_id,
            "tool_name": msg.tool_result.tool_name,
            "success": msg.tool_result.success,
            "content": msg.tool_result.content,
        }
        if msg.tool_result.data:
            content["data"] = msg.tool_result.data
    else:
        role = "unknown"

    # Deterministic message ID: "{session_id}-{sequence}"
    doc_id = msg.id or f"{session_id}-{sequence}"

    return MessageDocument(
        id=doc_id,
        session_id=session_id,
        sequence=sequence,
        role=role,
        content=content,
        turn_number=msg.turn_number,
        created_at=msg.timestamp or datetime.now(timezone.utc),
    )


@activity.defn(name="PersistMessages")
async def persist_messages(input_: PersistInput) -> None:
    """Persist messages atomically to PostgreSQL.

    1. Load current message count for sequence numbering
    2. Convert messages to documents with sequential numbering
    3. Atomic transaction: session upsert + message writes
    """
    from taskmeagents.services.agent_factory import get_history_store
    store = get_history_store()

    # Get current message count for sequence numbering by counting existing messages
    existing_msgs = await store.get_messages(input_.workflow_id)
    start_sequence = len(existing_msgs)

    # Convert messages to documents
    docs = []
    for i, msg in enumerate(input_.messages):
        doc = _message_to_doc(msg, input_.workflow_id, start_sequence + i)
        docs.append(doc)

    # Build session data
    token_usage = None
    for msg in input_.messages:
        if msg.usage:
            token_usage = msg.usage
            break

    session_data = SessionData(
        id=input_.workflow_id,
        user_id=input_.user_id,
        agent_id=input_.agent_id,
        status=input_.session_status or "running",
        message_count_delta=len(docs),
        turn_count=input_.current_turn,
        token_usage_delta=token_usage,
        last_activity_at=datetime.now(timezone.utc),
    )

    # Atomic persist
    results = await store.persist_batch(session_data, docs)

    inserted_count = sum(1 for r in results if r.inserted)
    logger.info(
        "activity.persist_messages",
        workflow_id=input_.workflow_id,
        total=len(docs),
        inserted=inserted_count,
        status=input_.session_status,
    )
