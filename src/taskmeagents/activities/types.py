"""Activity input/output types.

Translated from go_companion/internal/agent/activity_types.go
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from taskmeagents.conversation.types import ContextUpdate, Message


@dataclass
class ActivityInput:
    """Common parameters for all LLM activity calls.

    Built from ConversationState before each activity call.
    """

    workflow_id: str = ""
    agent_id: str = ""
    is_sub_agent: bool = False
    user_id: str = ""
    current_turn: int = 0
    context: ContextUpdate | None = None
    mcp_headers: dict[str, str] = field(default_factory=dict)

    # Messages not yet in PostgreSQL that must be included in conversation
    # history sent to the LLM. The activity merges these with DB history
    # in-memory but does NOT write them — PersistMessages handles all writes.
    pending_writes: list[Message] = field(default_factory=list)


@dataclass
class ActivityResult:
    """Everything the workflow needs for orchestration.

    LLM activities are read-only: they load history, call the LLM, and return
    the response delta. No DB writes occur in LLM activities.
    """

    # LLM response delta (NOT yet persisted — workflow calls PersistMessages)
    messages: list[Message] = field(default_factory=list)

    # True when return_to_parent_agent was detected
    should_terminate: bool = False

    # True when a guardrail triggered
    was_blocked: bool = False


@dataclass
class PersistInput:
    """Parameters for the PersistMessages activity."""

    workflow_id: str = ""
    agent_id: str = ""
    user_id: str = ""
    current_turn: int = 0

    # All messages to write, in order (pending + LLM response)
    messages: list[Message] = field(default_factory=list)

    # Session status: "running" (default), "completed", "failed"
    session_status: str = "running"
