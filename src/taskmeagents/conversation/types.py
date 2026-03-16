"""Core conversation types — provider-agnostic message representations.

Translated from go_companion/internal/conversation/types/types.go
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class ToolType(str, Enum):
    SERVER = "server"
    CLIENT = "client"
    AGENT = "agent"


@dataclass
class Attachment:
    filename: str
    mime_type: str
    data: bytes | None = None
    uri: str | None = None


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_read_tokens: int = 0
    total_cache_write_tokens: int = 0
    total_cost: float = 0.0
    request_cost: float = 0.0


@dataclass
class UserMessage:
    content: str
    attachments: list[Attachment] | None = None
    was_blocked: bool = False


@dataclass
class AssistantMessage:
    content: str
    thinking: str = ""
    is_final: bool = False
    was_blocked: bool = False


@dataclass
class ToolRequestMessage:
    tool_use_id: str
    tool_name: str
    tool_type: ToolType = ToolType.SERVER
    description: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    auto_approve: bool = False
    thought_signature: str | None = None  # Base64-encoded, preserved for future provider use


@dataclass
class ToolResultMessage:
    tool_use_id: str
    tool_name: str
    tool_type: ToolType = ToolType.SERVER
    success: bool = True
    content: str = ""
    data: dict[str, Any] | None = None
    was_auto_approved: bool = False
    attachments: list[Attachment] | None = None


@dataclass
class Message:
    id: str
    role: MessageRole
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    agent_id: str = ""
    turn_number: int = 0
    was_blocked: bool = False
    usage: TokenUsage | None = None
    user_message: UserMessage | None = None
    assistant_message: AssistantMessage | None = None
    tool_request: ToolRequestMessage | None = None
    tool_result: ToolResultMessage | None = None

    @property
    def is_tool_request(self) -> bool:
        return self.tool_request is not None

    @property
    def is_tool_result(self) -> bool:
        return self.tool_result is not None


@dataclass
class ContextUpdate:
    """Optional session context from client (e.g., current page, user preferences)."""

    data: dict[str, Any] = field(default_factory=dict)
