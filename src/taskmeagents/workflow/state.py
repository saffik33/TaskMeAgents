"""Conversation workflow state.

Translated from go_companion/internal/conversation/state/state.go

Pure orchestration state — activities own all conversation data via PostgreSQL.
The workflow never creates, modifies, or sequences conversation messages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from taskmeagents.conversation.types import ContextUpdate, Message, TokenUsage, ToolRequestMessage


@dataclass
class ConversationState:
    # Identity
    workflow_id: str = ""
    agent_id: str = ""
    parent_workflow_id: str = ""  # empty for root agents
    user_id: str = ""

    # Delegation
    delegation_depth: int = 0
    active_child_workflow_id: str = ""
    active_agent_tool_use_id: str = ""

    # Termination
    should_terminate: bool = False

    # Tool orchestration
    # Maps tool_use_id → pending tool Message (deferred until tool_result arrives)
    pending_tool_ids: dict[str, Message] = field(default_factory=dict)
    # Unsequenced messages to flush in next activity call
    pending_writes: list[Message] = field(default_factory=list)
    # FIFO queue for parallel agent tool requests
    queued_agent_tools: list[ToolRequestMessage] = field(default_factory=list)

    # Session metadata
    cumulative_usage: TokenUsage = field(default_factory=TokenUsage)
    current_turn: int = 0
    context: ContextUpdate | None = None

    def find_pending_tool_by_id(self, tool_use_id: str) -> tuple[Message | None, bool]:
        """Find pending tool request by exact tool use ID."""
        msg = self.pending_tool_ids.get(tool_use_id)
        return msg, msg is not None

    def find_pending_tool_by_name(self, tool_name: str) -> tuple[str, Message | None, bool]:
        """Find pending tool request by tool name (backward compat)."""
        for tid, msg in self.pending_tool_ids.items():
            if msg.tool_request and msg.tool_request.tool_name == tool_name:
                return tid, msg, True
        return "", None, False

    def accumulate_usage(self, usage: TokenUsage | None) -> None:
        """Add per-request usage to cumulative totals and update message totals."""
        if usage is None:
            return
        self.cumulative_usage.total_input_tokens += usage.input_tokens
        self.cumulative_usage.total_output_tokens += usage.output_tokens
        self.cumulative_usage.total_cache_read_tokens += usage.cache_read_tokens
        self.cumulative_usage.total_cache_write_tokens += usage.cache_write_tokens
        self.cumulative_usage.total_cost += usage.request_cost

        # Copy cumulative totals back to message for client
        usage.total_input_tokens = self.cumulative_usage.total_input_tokens
        usage.total_output_tokens = self.cumulative_usage.total_output_tokens
        usage.total_cache_read_tokens = self.cumulative_usage.total_cache_read_tokens
        usage.total_cache_write_tokens = self.cumulative_usage.total_cache_write_tokens
        usage.total_cost = self.cumulative_usage.total_cost
