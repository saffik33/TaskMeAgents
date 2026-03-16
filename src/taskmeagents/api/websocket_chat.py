"""WebSocket chat endpoint — bidirectional conversation streaming.

Replaces Go's gRPC bidirectional ExtChat stream.
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from taskmeagents.auth.api_key import validate_api_key
from taskmeagents.database import async_session_factory
from taskmeagents.mcp.passthrough import extract_all_mcp_headers
from taskmeagents.schemas.chat import WsClientMessage, WsEnd, WsError, WsSessionEstablished
from taskmeagents.services.companion import (
    ensure_workflow,
    process_and_stream_messages,
    send_workflow_update,
)
from taskmeagents.temporal_.client import get_temporal_client
from taskmeagents.workflow.constants import (
    UPDATE_PROCESS_CLIENT_TOOL_RESULT,
    UPDATE_PROCESS_END_CONVERSATION,
    UPDATE_PROCESS_SERVER_TOOL_APPROVAL,
    UPDATE_PROCESS_USER_MESSAGE,
)

logger = structlog.get_logger()
router = APIRouter()


@router.websocket("/ws/chat")
async def websocket_chat(
    ws: WebSocket,
    api_key: str,
    agent_id: str,
    session_id: str | None = None,
):
    """Bidirectional WebSocket for AI agent conversations.

    Query params:
    - api_key: API key for authentication
    - agent_id: Agent to converse with
    - session_id: Optional session to resume
    """
    # Validate API key BEFORE accepting the WebSocket connection
    async with async_session_factory() as db:
        key_record = await validate_api_key(db, api_key)
    if not key_record:
        await ws.close(code=4001, reason="Invalid API key")
        return

    await ws.accept()
    user_id = key_record.user_id

    try:
        try:
            client = get_temporal_client()
        except RuntimeError:
            await ws.send_json(WsError(message="Service temporarily unavailable", code="SERVICE_UNAVAILABLE").model_dump())
            await ws.close()
            return

        # Ensure workflow exists
        workflow_id = await ensure_workflow(client, agent_id, user_id, session_id)

        # Send session established
        await ws.send_json(WsSessionEstablished(session_id=workflow_id).model_dump())

        # Extract MCP headers from initial WebSocket headers
        ws_headers = dict(ws.headers)
        mcp_headers = extract_all_mcp_headers(ws_headers) or {}

        # Message loop
        while True:
            raw = await ws.receive_json()
            msg = WsClientMessage(**raw)

            message_id = msg.message_id or str(uuid.uuid4())

            try:
                if msg.type == "user_message":
                    messages = await send_workflow_update(
                        client, workflow_id, UPDATE_PROCESS_USER_MESSAGE,
                        [msg.content or "", message_id, mcp_headers],
                        update_id=message_id,
                    )
                    await process_and_stream_messages(
                        client, ws, workflow_id, agent_id, messages, mcp_headers,
                    )

                elif msg.type == "client_tool_result":
                    messages = await send_workflow_update(
                        client, workflow_id, UPDATE_PROCESS_CLIENT_TOOL_RESULT,
                        [
                            msg.tool_use_id or "",
                            msg.tool_name or "",
                            msg.success if msg.success is not None else True,
                            msg.content or "",
                            msg.result_data,
                            message_id,
                            mcp_headers,
                        ],
                        update_id=message_id,
                    )
                    await process_and_stream_messages(
                        client, ws, workflow_id, agent_id, messages, mcp_headers,
                    )

                elif msg.type == "server_tool_approval":
                    messages = await send_workflow_update(
                        client, workflow_id, UPDATE_PROCESS_SERVER_TOOL_APPROVAL,
                        [
                            msg.tool_use_id or "",
                            msg.tool_name or "",
                            msg.approved if msg.approved is not None else True,
                            msg.rejection_reason or "",
                            mcp_headers,
                        ],
                    )
                    await process_and_stream_messages(
                        client, ws, workflow_id, agent_id, messages, mcp_headers,
                    )

                elif msg.type == "end_conversation":
                    messages = await send_workflow_update(
                        client, workflow_id, UPDATE_PROCESS_END_CONVERSATION,
                        [msg.reason or "", message_id, mcp_headers],
                        update_id=message_id,
                    )
                    await process_and_stream_messages(
                        client, ws, workflow_id, agent_id, messages, mcp_headers,
                    )
                    await ws.send_json(WsEnd(reason="completed").model_dump())
                    break

                else:
                    await ws.send_json(WsError(message=f"Unknown message type: {msg.type}").model_dump())

            except Exception as e:
                logger.error("ws.message.error", error=str(e), workflow_id=workflow_id)
                await ws.send_json(WsError(message="An internal error occurred. Please try again.").model_dump())

    except WebSocketDisconnect:
        logger.info("ws.disconnected", workflow_id=session_id or "unknown")
    except Exception as e:
        logger.error("ws.fatal", error=str(e))
        try:
            await ws.send_json(WsError(message="Connection error").model_dump())
            await ws.close()
        except Exception:
            pass
