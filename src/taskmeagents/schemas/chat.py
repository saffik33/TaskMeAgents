"""WebSocket message schemas for chat.

Defines the JSON message format for bidirectional WebSocket communication.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


# --- Client → Server ---

class WsClientMessage(BaseModel):
    type: str  # user_message, client_tool_result, server_tool_approval, end_conversation
    # user_message fields
    content: str | None = None
    message_id: str | None = None
    # client_tool_result fields
    tool_use_id: str | None = None
    tool_name: str | None = None
    success: bool | None = None
    result_data: dict[str, Any] | None = None
    # server_tool_approval fields
    approved: bool | None = None
    rejection_reason: str | None = None
    # end_conversation fields
    reason: str | None = None


# --- Server → Client ---

class WsSessionEstablished(BaseModel):
    type: str = "session_established"
    session_id: str


class WsAssistantMessage(BaseModel):
    type: str = "assistant_message"
    content: str
    is_final: bool = False
    message_id: str = ""
    agent_id: str = ""


class WsAssistantThinking(BaseModel):
    type: str = "assistant_thinking"
    content: str


class WsToolExecutionRequest(BaseModel):
    type: str = "tool_execution_request"
    tool_name: str
    tool_use_id: str
    parameters: dict[str, Any] = {}
    tool_type: str = "client"
    description: str = ""


class WsToolApprovalRequest(BaseModel):
    type: str = "tool_approval_request"
    tool_name: str
    tool_use_id: str
    parameters: dict[str, Any] = {}
    description: str = ""


class WsToolResult(BaseModel):
    type: str = "tool_result"
    tool_name: str
    tool_use_id: str
    success: bool
    content: str = ""
    data: dict[str, Any] | None = None
    was_auto_approved: bool = False


class WsUsage(BaseModel):
    type: str = "usage"
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost: float = 0.0
    request_cost: float = 0.0


class WsError(BaseModel):
    type: str = "error"
    message: str
    code: str = "INTERNAL"


class WsEnd(BaseModel):
    type: str = "end"
    reason: str = "completed"
