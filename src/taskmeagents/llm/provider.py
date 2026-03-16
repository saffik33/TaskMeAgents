"""LLM provider abstraction with streaming support.

Translated from go_companion/internal/llm/provider.go
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from taskmeagents.conversation.types import Message, TokenUsage
from taskmeagents.tools.types import Tool


class StopReason(str, Enum):
    END_TURN = "end_turn"
    MAX_TOKENS = "max_tokens"
    TOOL_USE = "tool_use"
    CONTENT_FILTERED = "content_filtered"
    STOP_SEQUENCE = "stop_sequence"
    ERROR = "error"


class SystemBlockType(str, Enum):
    TEXT = "text"
    CACHE_POINT = "cache_point"


@dataclass
class SystemBlock:
    type: SystemBlockType
    content: str = ""


@dataclass
class GenerateRequest:
    system_prompt: list[SystemBlock]
    messages: list[Message]
    tools: list[Tool]
    temperature: float = 0.7
    max_tokens: int = 4096
    context: dict[str, Any] | None = None
    use_caching: bool = False


# --- Stream Events ---

@dataclass
class StreamEvent:
    pass


@dataclass
class MessageEvent(StreamEvent):
    message: Message | None = field(default=None)


@dataclass
class UsageEvent(StreamEvent):
    usage: TokenUsage = field(default_factory=TokenUsage)
    stop_reason: StopReason = StopReason.END_TURN


@dataclass
class ErrorEvent(StreamEvent):
    error: Exception | None = field(default=None)


# --- Provider ABC ---

class Provider(ABC):
    @abstractmethod
    async def generate(self, request: GenerateRequest) -> AsyncIterator[StreamEvent]:
        """Stream LLM response events. Yields MessageEvent, UsageEvent, ErrorEvent."""
        ...

    @abstractmethod
    def get_model(self) -> Any:
        """Returns a Model instance from llm.models."""
        ...

    @abstractmethod
    async def close(self) -> None:
        ...
