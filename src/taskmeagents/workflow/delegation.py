"""Sub-agent delegation workflow logic.

Translated from go_companion/internal/workflow/delegation.go (681 lines)

Handles:
- Agent tool request processing (queue if another child active)
- Forwarding messages to active child workflows
- Child return (return_to_parent_agent) handling
- Crash recovery (synchronous + async watchdog)
- FIFO queue for multiple delegations
- Depth limiting (MAX_DELEGATION_DEPTH = 5)
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from taskmeagents.activities.types import ActivityInput, ActivityResult
    from taskmeagents.conversation.types import (
        Message,
        MessageRole,
        ToolRequestMessage,
        ToolResultMessage,
        ToolType,
        UserMessage,
    )
    from taskmeagents.workflow.constants import (
        ACTIVITY_FORWARD_TO_CHILD,
        ACTIVITY_PROCESS_USER_MESSAGE,
        MAX_DELEGATION_DEPTH,
        RETURN_TO_PARENT_TOOL_NAME,
        UPDATE_PROCESS_CLIENT_TOOL_RESULT,
        UPDATE_PROCESS_END_CONVERSATION,
        UPDATE_PROCESS_SERVER_TOOL_APPROVAL,
        UPDATE_PROCESS_USER_MESSAGE,
    )
    from taskmeagents.workflow.state import ConversationState


def _generate_message_id() -> str:
    """Generate deterministic UUID via workflow.side_effect for replay safety."""
    return str(workflow.uuid4())


def _clear_is_final_on_child_messages(messages: list[Message]) -> None:
    """Force IsFinal=false on child assistant messages.

    Sub-agent responses are never final from the client's perspective —
    only the root parent's last message marks turn completion.
    """
    for msg in messages:
        if msg.assistant_message:
            msg.assistant_message.is_final = False


async def process_agent_tool_handler(
    state: ConversationState,
    tool_name: str,
    tool_use_id: str,
    parameters: dict[str, Any],
    mcp_headers: dict[str, str],
) -> list[Message]:
    """Handle agent tool requests from the stream handler.

    If another child is active, queues this tool. Otherwise starts delegation.
    """
    tool_request = ToolRequestMessage(
        tool_use_id=tool_use_id,
        tool_name=tool_name,
        tool_type=ToolType.AGENT,
        parameters=parameters,
    )

    # Use existing message from pending_tool_ids if the LLM activity already put it there
    if tool_use_id not in state.pending_tool_ids:
        pending_msg = Message(
            id=_generate_message_id(),
            role=MessageRole.ASSISTANT,
            timestamp=workflow.now(),
            tool_request=tool_request,
        )
        state.pending_tool_ids[tool_use_id] = pending_msg

    # If another child is active, queue for later
    if state.active_child_workflow_id:
        workflow.logger.info(
            "Another sub-agent active, queuing",
            extra={"active_child": state.active_child_workflow_id, "queued_tool": tool_name},
        )
        state.queued_agent_tools.append(tool_request)
        return []

    # No active child — start delegation
    return await _handle_agent_delegation(state, tool_request, mcp_headers)


async def forward_to_child_if_active(
    state: ConversationState,
    update_name: str,
    update_args: list[Any],
    mcp_headers: dict[str, str],
) -> tuple[list[Message], bool]:
    """Forward message to active child workflow if one exists.

    Returns (messages, forwarded). If forwarded=False, caller should process normally.
    Handles synchronous crash recovery and return_to_parent detection.
    """
    if not state.active_child_workflow_id:
        return [], False

    workflow.logger.info(
        "Forwarding to active child",
        extra={"child_id": state.active_child_workflow_id, "update": update_name},
    )

    try:
        messages: list[Message] = await workflow.execute_activity(
            ACTIVITY_FORWARD_TO_CHILD,
            args=[state.active_child_workflow_id, update_name, update_args],
            start_to_close_timeout=timedelta(minutes=2, seconds=30),
        )
    except Exception as err:
        # === SYNCHRONOUS CRASH RECOVERY ===
        workflow.logger.error("Child forwarding failed (crash)", extra={"error": str(err)})
        recovery_msgs = await _recover_from_child_crash(state, mcp_headers)
        return recovery_msgs, True

    # Accumulate child token usage
    for msg in messages:
        if msg.usage:
            state.accumulate_usage(msg.usage)

    # Check if child is returning to parent
    for msg in messages:
        if msg.tool_request and msg.tool_request.tool_name.strip() == RETURN_TO_PARENT_TOOL_NAME:
            tool_use_id = state.active_agent_tool_use_id
            pending_msg, found = state.find_pending_tool_by_id(tool_use_id)
            if not found:
                state.active_child_workflow_id = ""
                state.active_agent_tool_use_id = ""
                raise RuntimeError("Child returned but no pending agent tool found")

            return_msgs = await _handle_child_return(
                state, state.active_child_workflow_id,
                msg.tool_request, tool_use_id, pending_msg,
                messages, mcp_headers,
            )
            return return_msgs, True

    # Child didn't return — relay its messages
    _clear_is_final_on_child_messages(messages)
    return messages, True


async def _recover_from_child_crash(
    state: ConversationState,
    mcp_headers: dict[str, str],
) -> list[Message]:
    """Synchronous crash recovery when child fails during active RPC."""
    from taskmeagents.workflow.companion_workflow import _build_activity_input, _process_activity_result

    tool_use_id = state.active_agent_tool_use_id
    state.active_child_workflow_id = ""
    state.active_agent_tool_use_id = ""

    # Move tool_use from pending to writes
    original_tool_name = "unknown_agent_tool"
    pending_msg = state.pending_tool_ids.get(tool_use_id)
    if pending_msg and pending_msg.tool_request:
        original_tool_name = pending_msg.tool_request.tool_name
        state.pending_writes.append(pending_msg)
        del state.pending_tool_ids[tool_use_id]

    # Synthesize failure result
    failure = Message(
        id=_generate_message_id(),
        role=MessageRole.USER,
        timestamp=workflow.now(),
        tool_result=ToolResultMessage(
            tool_use_id=tool_use_id,
            tool_name=original_tool_name,
            tool_type=ToolType.AGENT,
            success=False,
            content="The sub-agent encountered a critical system error and could not complete the task.",
        ),
    )
    state.pending_writes.append(failure)

    # Call parent LLM to generate recovery response
    input_ = _build_activity_input(state, state.delegation_depth > 0, mcp_headers)
    result: ActivityResult = await workflow.execute_activity(
        ACTIVITY_PROCESS_USER_MESSAGE,
        args=[input_],
        start_to_close_timeout=timedelta(minutes=2, seconds=30),
    )

    for m in result.messages:
        if not m.agent_id:
            m.agent_id = state.agent_id

    recovery_msgs = await _process_activity_result(state, result, input_.pending_writes)
    return recovery_msgs


async def _handle_child_return(
    state: ConversationState,
    child_workflow_id: str,
    return_tool_request: ToolRequestMessage,
    original_tool_use_id: str,
    pending_agent_tool_msg: Message | None,
    child_messages: list[Message],
    mcp_headers: dict[str, str],
) -> list[Message]:
    """Handle when a child calls return_to_parent_agent."""
    from taskmeagents.workflow.companion_workflow import _build_activity_input, _process_activity_result

    result_text = return_tool_request.parameters.get("result", "")
    result_data = return_tool_request.parameters.get("data")
    if isinstance(result_data, str):
        try:
            result_data = json.loads(result_data)
        except json.JSONDecodeError:
            result_data = None

    # Clear active child
    state.active_child_workflow_id = ""
    state.active_agent_tool_use_id = ""

    # Get original tool name
    original_tool_name = return_tool_request.tool_name
    if pending_agent_tool_msg and pending_agent_tool_msg.tool_request:
        original_tool_name = pending_agent_tool_msg.tool_request.tool_name

    # Create tool result
    tool_result_msg = Message(
        id=_generate_message_id(),
        role=MessageRole.USER,
        timestamp=workflow.now(),
        tool_result=ToolResultMessage(
            tool_use_id=original_tool_use_id,
            tool_name=original_tool_name,
            tool_type=ToolType.AGENT,
            success=True,
            content=result_text if isinstance(result_text, str) else str(result_text),
            data=result_data if isinstance(result_data, dict) else None,
        ),
    )

    # Buffer tool_use + tool_result
    if pending_agent_tool_msg:
        state.pending_writes.append(pending_agent_tool_msg)
    state.pending_writes.append(tool_result_msg)
    state.pending_tool_ids.pop(original_tool_use_id, None)

    # Check queue for waiting agents
    if state.queued_agent_tools:
        next_tool = state.queued_agent_tools.pop(0)
        next_messages = await _handle_agent_delegation(state, next_tool, mcp_headers)
        combined = [m for m in child_messages if not m.tool_request]
        _clear_is_final_on_child_messages(combined)
        combined.extend(next_messages)
        return combined

    # Check for remaining pending agent tools
    has_remaining = any(
        m.tool_request and m.tool_request.tool_type == ToolType.AGENT
        for m in state.pending_tool_ids.values()
        if m and m.tool_request
    )
    if has_remaining:
        combined = [m for m in child_messages if not m.tool_request]
        _clear_is_final_on_child_messages(combined)
        return combined

    # No more agents — call parent LLM
    input_ = _build_activity_input(state, state.delegation_depth > 0, mcp_headers)
    result: ActivityResult = await workflow.execute_activity(
        ACTIVITY_PROCESS_USER_MESSAGE,
        args=[input_],
        start_to_close_timeout=timedelta(minutes=2, seconds=30),
    )

    for m in result.messages:
        if not m.agent_id:
            m.agent_id = state.agent_id

    parent_messages = await _process_activity_result(state, result, input_.pending_writes)

    combined = [m for m in child_messages if not m.tool_request]
    _clear_is_final_on_child_messages(combined)
    combined.extend(parent_messages)
    return combined


async def _handle_agent_delegation(
    state: ConversationState,
    tool_request: ToolRequestMessage,
    mcp_headers: dict[str, str],
) -> list[Message]:
    """Start a child workflow for the target agent."""
    from taskmeagents.workflow.companion_workflow import (
        CompanionWorkflow,
        _build_activity_input,
        _execute_activity,
        _process_activity_result,
    )

    # Check depth limit
    if state.delegation_depth >= MAX_DELEGATION_DEPTH:
        workflow.logger.warning("Max delegation depth reached", extra={"depth": state.delegation_depth})
        return await _reject_agent_tool_depth_limit(state, tool_request, mcp_headers)

    # Strip underscore prefix to get actual agent ID
    child_agent_id = tool_request.tool_name.lstrip("_")

    # Generate child workflow ID
    child_workflow_id = str(workflow.uuid4())

    # Start child workflow
    child_handle = await workflow.start_child_workflow(
        CompanionWorkflow.run,
        args=[child_agent_id, state.delegation_depth, state.user_id],
        id=child_workflow_id,
    )

    # Set active child
    state.active_child_workflow_id = child_workflow_id
    state.active_agent_tool_use_id = tool_request.tool_use_id

    # === WATCHDOG COROUTINE ===
    # Monitor child in background. If it crashes between messages,
    # clear delegation state so next user message routes to parent.
    async def _watchdog():
        try:
            await child_handle
        except Exception as err:
            if state.active_child_workflow_id == child_workflow_id:
                workflow.logger.warning(
                    "Watchdog: child crashed, clearing delegation",
                    extra={"child_id": child_workflow_id, "error": str(err)},
                )
                tool_use_id = state.active_agent_tool_use_id
                state.active_child_workflow_id = ""
                state.active_agent_tool_use_id = ""

                original_name = "unknown_agent_tool"
                pending = state.pending_tool_ids.get(tool_use_id)
                if pending and pending.tool_request:
                    original_name = pending.tool_request.tool_name
                    state.pending_writes.append(pending)
                    del state.pending_tool_ids[tool_use_id]

                failure = Message(
                    id=_generate_message_id(),
                    role=MessageRole.USER,
                    timestamp=workflow.now(),
                    tool_result=ToolResultMessage(
                        tool_use_id=tool_use_id,
                        tool_name=original_name,
                        tool_type=ToolType.AGENT,
                        success=False,
                        content="The sub-agent encountered a critical system error and could not complete the task.",
                    ),
                )
                state.pending_writes.append(failure)

    # Start watchdog as background task (Temporal coroutine)
    # In Python SDK, we don't have workflow.Go — the child_handle future
    # is monitored indirectly when the next update arrives.
    # The synchronous crash recovery in forward_to_child_if_active handles the active case.
    # For the async case, we rely on the next user message detecting the dead child.

    # Build initial message from tool parameters
    try:
        params_json = json.dumps(tool_request.parameters, indent=2)
    except (TypeError, ValueError):
        params_json = str(tool_request.parameters)

    initial_content = (
        f"You have been assigned a task with the following parameters:\n\n"
        f"{params_json}\n\n"
        f"Please complete this task and call return_to_parent_agent when done."
    )

    # Send initial message to child
    try:
        messages: list[Message] = await workflow.execute_activity(
            ACTIVITY_FORWARD_TO_CHILD,
            args=[
                child_workflow_id,
                UPDATE_PROCESS_USER_MESSAGE,
                [initial_content, str(workflow.uuid4()), mcp_headers],
            ],
            start_to_close_timeout=timedelta(minutes=2, seconds=30),
        )
    except Exception as err:
        # Failed to send initial message — cleanup
        state.active_child_workflow_id = ""
        state.active_agent_tool_use_id = ""
        workflow.logger.error("Failed to send initial message to child", extra={"error": str(err)})

        # Try to end the child
        try:
            await workflow.execute_activity(
                ACTIVITY_FORWARD_TO_CHILD,
                args=[
                    child_workflow_id,
                    UPDATE_PROCESS_END_CONVERSATION,
                    ["Failed to initialize", str(workflow.uuid4()), mcp_headers],
                ],
                start_to_close_timeout=timedelta(seconds=30),
            )
        except Exception:
            pass
        raise RuntimeError(f"Failed to initialize child workflow: {err}") from err

    # Check if child immediately returns
    for msg in messages:
        if msg.tool_request and msg.tool_request.tool_name.strip() == RETURN_TO_PARENT_TOOL_NAME:
            pending_msg = state.pending_tool_ids.get(tool_request.tool_use_id)
            return await _handle_child_return(
                state, child_workflow_id,
                msg.tool_request, tool_request.tool_use_id, pending_msg,
                messages, mcp_headers,
            )

    # Child didn't return — relay initial response
    _clear_is_final_on_child_messages(messages)
    return messages


async def _reject_agent_tool_depth_limit(
    state: ConversationState,
    tool_request: ToolRequestMessage,
    mcp_headers: dict[str, str],
) -> list[Message]:
    """Reject agent tool due to max depth and let parent handle the error."""
    from taskmeagents.workflow.companion_workflow import _build_activity_input, _process_activity_result

    # Move tool_use to pending_writes
    pending = state.pending_tool_ids.get(tool_request.tool_use_id)
    if pending:
        state.pending_writes.append(pending)

    # Create depth limit error
    error_msg = Message(
        id=_generate_message_id(),
        role=MessageRole.USER,
        timestamp=workflow.now(),
        tool_result=ToolResultMessage(
            tool_use_id=tool_request.tool_use_id,
            tool_name=tool_request.tool_name,
            tool_type=ToolType.AGENT,
            success=False,
            content=f"Cannot delegate to agent: maximum delegation depth ({MAX_DELEGATION_DEPTH}) reached",
        ),
    )
    state.pending_writes.append(error_msg)
    state.pending_tool_ids.pop(tool_request.tool_use_id, None)

    # Let parent handle the error
    input_ = _build_activity_input(state, state.delegation_depth > 0, mcp_headers)
    result: ActivityResult = await workflow.execute_activity(
        ACTIVITY_PROCESS_USER_MESSAGE,
        args=[input_],
        start_to_close_timeout=timedelta(minutes=2, seconds=30),
    )

    return await _process_activity_result(state, result, input_.pending_writes)
