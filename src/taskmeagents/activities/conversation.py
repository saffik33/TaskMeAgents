"""LLM conversation activities.

Translated from go_companion/internal/agent/activities.go + agent.go

Activities are read-only: they load history, call the LLM, and return
the response delta. No DB writes occur here — PersistMessages handles that.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from temporalio import activity

from taskmeagents.activities.types import ActivityInput, ActivityResult
from taskmeagents.conversation.masking import MaskingConfig, apply_observation_masking
from taskmeagents.conversation.types import (
    AssistantMessage,
    Message,
    MessageRole,
    TokenUsage,
    ToolRequestMessage,
    ToolResultMessage,
)
from taskmeagents.llm.models import calculate_cost
from taskmeagents.llm.provider import ErrorEvent, GenerateRequest, MessageEvent, StopReason, SystemBlock, SystemBlockType, UsageEvent
from taskmeagents.workflow.constants import RETURN_TO_PARENT_TOOL_NAME

logger = structlog.get_logger()


async def _get_agent(agent_id: str, is_sub_agent: bool):
    """Load agent from factory (cached)."""
    from taskmeagents.services.agent_factory import get_agent_factory
    factory = get_agent_factory()
    return await factory.get_agent(agent_id, is_sub_agent)


async def _load_and_merge_history(input_: ActivityInput) -> list[Message]:
    """Load history from PostgreSQL and merge with pending writes."""
    from taskmeagents.services.agent_factory import get_history_store
    store = get_history_store()
    docs = await store.get_messages(input_.workflow_id)

    # Convert MessageDocuments to Messages
    messages = []
    for doc in docs:
        msg = _doc_to_message(doc)
        if msg:
            messages.append(msg)

    # Merge pending writes (not yet in DB)
    messages.extend(input_.pending_writes)
    return messages


def _doc_to_message(doc) -> Message | None:
    """Convert a MessageDocument to a Message."""
    content = doc.content or {}
    role_str = doc.role

    msg = Message(
        id=doc.id,
        role=MessageRole.USER if role_str in ("user", "tool_result") else MessageRole.ASSISTANT,
        turn_number=doc.turn_number,
    )

    if role_str == "user" and "content" in content:
        from taskmeagents.conversation.types import UserMessage
        msg.user_message = UserMessage(content=content["content"])
    elif role_str == "assistant" and "content" in content:
        msg.assistant_message = AssistantMessage(content=content["content"], thinking=content.get("thinking", ""))
    elif role_str == "tool_request":
        msg.tool_request = ToolRequestMessage(
            tool_use_id=content.get("tool_use_id", ""),
            tool_name=content.get("tool_name", ""),
            parameters=content.get("parameters", {}),
        )
    elif role_str == "tool_result":
        msg.tool_result = ToolResultMessage(
            tool_use_id=content.get("tool_use_id", ""),
            tool_name=content.get("tool_name", ""),
            success=content.get("success", True),
            content=content.get("content", ""),
        )

    return msg


async def _generate_and_aggregate(agent, history: list[Message], context: Any) -> ActivityResult:
    """Call LLM and aggregate streaming response into messages."""
    model = agent.provider.get_model()

    # Apply observation masking
    masking_cfg = agent.config.get("observation_masking", {})
    masked_history = apply_observation_masking(
        history,
        current_turn=max((m.turn_number for m in history), default=0),
        config=MaskingConfig(
            enabled=masking_cfg.get("enabled", True),
            recent_window_turns=masking_cfg.get("recent_window_turns", 3),
        ),
        total_tokens=0,  # Approximation — full token counting would require tokenizer
        max_context_tokens=model.context_window,
    )

    # Build system prompt
    system_blocks = [SystemBlock(type=SystemBlockType.TEXT, content=agent.config.get("system_prompt", ""))]

    request = GenerateRequest(
        system_prompt=system_blocks,
        messages=masked_history,
        tools=agent.all_tools,
        temperature=agent.config.get("temperature", 0.7),
        max_tokens=agent.config.get("max_tokens", 4096),
        use_caching=agent.config.get("use_prompt_cache", False),
    )

    messages: list[Message] = []
    should_terminate = False
    was_blocked = False

    async for event in agent.provider.generate(request):
        if isinstance(event, MessageEvent) and event.message:
            msg = event.message
            msg.agent_id = agent.config.get("agent_id", "")

            # Check for return_to_parent_agent
            if msg.tool_request and msg.tool_request.tool_name == RETURN_TO_PARENT_TOOL_NAME:
                should_terminate = True

            # Enrich tool requests with type/auto_approve from agent's tool definitions
            if msg.tool_request:
                _enrich_tool_request(msg.tool_request, agent.all_tools)

            messages.append(msg)

        elif isinstance(event, UsageEvent):
            cost = calculate_cost(model.id, event.usage)
            event.usage.request_cost = cost
            # Attach usage to last assistant message
            for m in reversed(messages):
                if m.assistant_message or m.tool_request:
                    m.usage = event.usage
                    break
            if event.stop_reason == StopReason.CONTENT_FILTERED:
                was_blocked = True

        elif isinstance(event, ErrorEvent):
            logger.error("llm.generate.error", error=str(event.error))
            raise event.error

    return ActivityResult(messages=messages, should_terminate=should_terminate, was_blocked=was_blocked)


def _enrich_tool_request(tool_req: ToolRequestMessage, all_tools: list) -> None:
    """Set tool_type and auto_approve from agent's tool definitions."""
    for tool in all_tools:
        if tool.name == tool_req.tool_name:
            tool_req.tool_type = tool.tool_type
            tool_req.auto_approve = tool.auto_approve
            tool_req.description = tool.description
            return


# --- Activity Definitions ---

@activity.defn(name="ProcessUserMessage")
async def process_user_message(input_: ActivityInput) -> ActivityResult:
    agent = await _get_agent(input_.agent_id, input_.is_sub_agent)
    history = await _load_and_merge_history(input_)
    return await _generate_and_aggregate(agent, history, input_.context)


@activity.defn(name="ProcessClientToolResult")
async def process_client_tool_result(input_: ActivityInput) -> ActivityResult:
    agent = await _get_agent(input_.agent_id, input_.is_sub_agent)
    history = await _load_and_merge_history(input_)
    return await _generate_and_aggregate(agent, history, input_.context)


@activity.defn(name="ProcessEndConversation")
async def process_end_conversation(input_: ActivityInput) -> ActivityResult:
    agent = await _get_agent(input_.agent_id, input_.is_sub_agent)
    history = await _load_and_merge_history(input_)
    return await _generate_and_aggregate(agent, history, input_.context)


@activity.defn(name="RejectPendingTool")
async def reject_pending_tool(input_: ActivityInput) -> ActivityResult:
    agent = await _get_agent(input_.agent_id, input_.is_sub_agent)
    history = await _load_and_merge_history(input_)
    return await _generate_and_aggregate(agent, history, input_.context)
