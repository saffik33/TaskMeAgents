"""Abstract history store interface.

Translated from go_companion/internal/history/store.go
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from taskmeagents.conversation.types import Attachment, Message, TokenUsage


@dataclass
class SessionData:
    id: str
    user_id: str
    agent_id: str
    parent_session_id: str | None = None
    status: str = "running"
    message_count_delta: int = 0
    turn_count: int = 0
    token_usage_delta: TokenUsage | None = None
    last_activity_at: datetime | None = None
    delegation_depth: int = 0


@dataclass
class MessageDocument:
    id: str  # "{session_id}-{sequence}"
    session_id: str
    sequence: int
    role: str
    content: dict[str, Any] = field(default_factory=dict)
    turn_number: int = 0
    created_at: datetime | None = None


@dataclass
class WriteResult:
    message_id: str
    inserted: bool


class HistoryStore(ABC):
    @abstractmethod
    async def upsert_session(self, session: SessionData) -> None: ...

    @abstractmethod
    async def write_messages(self, messages: list[MessageDocument]) -> list[WriteResult]: ...

    @abstractmethod
    async def persist_batch(self, session: SessionData, messages: list[MessageDocument]) -> list[WriteResult]: ...

    @abstractmethod
    async def get_messages(self, session_id: str, include_attachments: bool = False) -> list[MessageDocument]: ...

    @abstractmethod
    async def list_user_sessions(
        self, user_id: str, cursor: str | None = None, limit: int = 20
    ) -> tuple[list[SessionData], str | None]: ...

    @abstractmethod
    async def search_messages(self, user_id: str, query: str, limit: int = 20) -> list[MessageDocument]: ...

    @abstractmethod
    async def get_session(self, session_id: str) -> SessionData | None: ...

    @abstractmethod
    async def update_message(self, message: MessageDocument) -> None: ...

    @abstractmethod
    async def upload_and_strip_attachments(
        self, user_id: str, session_id: str, message_id: str, attachments: list[Attachment]
    ) -> None: ...

    @abstractmethod
    async def rehydrate_attachments(
        self, user_id: str, session_id: str, message_id: str, attachments: list[Attachment]
    ) -> None: ...

    @abstractmethod
    async def close(self) -> None: ...
