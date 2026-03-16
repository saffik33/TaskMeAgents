"""Main Temporal workflow for conversation orchestration.

Translated from go_companion/internal/workflow/workflow.go + user_messages.go
+ server_tools.go + client_tools.go + state_helpers.go

Pure orchestration — activities handle all business logic.
Uses Update Handlers (not signals) for synchronous request-response semantics.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from taskmeagents.activities.types import ActivityInput, ActivityResult, PersistInput
    from taskmeagents.conversation.types import (
        AssistantMessage,
        ContextUpdate,
        Message,
        MessageRole,
        ToolRequestMessage,
        ToolResultMessage,
        UserMessage,
    )
    from taskmeagents.workflow.constants import (
        ACTIVITY_EXECUTE_SERVER_TOOL,
        ACTIVITY_PERSIST_MESSAGES,
        ACTIVITY_PROCESS_CLIENT_TOOL_RESULT,
        ACTIVITY_PROCESS_END_CONVERSATION,
        ACTIVITY_PROCESS_USER_MESSAGE,
        ACTIVITY_REJECT_PENDING_TOOL,
        ACTIVITY_RETRY_POLICY,
        ACTIVITY_START_TO_CLOSE_TIMEOUT,
        SESSION_STATUS_COMPLETED,
        UPDATE_PROCESS_CLIENT_TOOL_RESULT,
        UPDATE_PROCESS_END_CONVERSATION,
        UPDATE_PROCESS_SERVER_TOOL_APPROVAL,
        UPDATE_PROCESS_USER_MESSAGE,
    )
    from taskmeagents.workflow.state import ConversationState


# --- Helper Functions ---

def _generate_message_id() -> str:
    """Generate a deterministic UUID via workflow.side_effect for replay safety."""
    return str(workflow.uuid4())


def _build_activity_input(
    state: ConversationState,
    is_sub_agent: bool,
    mcp_headers: dict[str, str],
) -> ActivityInput:
    """Capture PendingWrites snapshot and clear them atomically."""
    pending = list(state.pending_writes)
    state.pending_writes = []

    return ActivityInput(
        workflow_id=state.workflow_id,
        agent_id=state.agent_id,
        is_sub_agent=is_sub_agent,
        user_id=state.user_id,
        current_turn=state.current_turn,
        context=state.context,
        mcp_headers=mcp_headers,
        pending_writes=pending,
    )


async def _execute_activity(activity_name: str, *args: Any, result_type: Any = None) -> Any:
    """Execute a Temporal activity with standard options."""
    return await workflow.execute_activity(
        activity_name,
        args=args,
        result_type=result_type,
        start_to_close_timeout=ACTIVITY_START_TO_CLOSE_TIMEOUT,
        retry_policy=ACTIVITY_RETRY_POLICY,
    )


async def _process_activity_result(
    state: ConversationState,
    result: ActivityResult,
    pending_writes: list[Message],
    session_status: str = "",
) -> list[Message]:
    """Handle orchestration signals, persist messages, return stream messages.

    Tool requests are routed to pending_tool_ids (deferred persistence).
    ShouldTerminate is set AFTER persist completes to prevent premature workflow exit.
    """
    if not result:
        return []

    stream_messages: list[Message] = []

    for msg in result.messages:
        if not msg.timestamp:
            msg.timestamp = workflow.now()
        if msg.role is None:
            msg.role = MessageRole.ASSISTANT

        state.accumulate_usage(msg.usage)

        # Route tool requests to pending_tool_ids for orchestration tracking
        if msg.tool_request is not None:
            state.pending_tool_ids[msg.tool_request.tool_use_id] = msg

        stream_messages.append(msg)

    # Persist: pending_writes + non-tool_use response messages
    to_persist = list(pending_writes)
    for msg in result.messages:
        if msg.tool_request is not None:
            continue  # deferred to pending_tool_ids
        to_persist.append(msg)

    if to_persist or session_status:
        persist_input = PersistInput(
            workflow_id=state.workflow_id,
            agent_id=state.agent_id,
            user_id=state.user_id,
            current_turn=state.current_turn,
            messages=to_persist,
            session_status=session_status,
        )
        await _execute_activity(ACTIVITY_PERSIST_MESSAGES, persist_input)

    # Set ShouldTerminate AFTER persist completes
    if result.should_terminate:
        state.should_terminate = True

    return stream_messages


def _handle_fatal_error(agent_id: str, err: Exception) -> tuple[list[Message], bool]:
    """Check for fatal errors, return generic user-facing message."""
    workflow.logger.error(f"Fatal error in workflow: {type(err).__name__}: {err}")
    error_msg = Message(
        id=_generate_message_id(),
        role=MessageRole.ASSISTANT,
        agent_id=agent_id,
        assistant_message=AssistantMessage(
            content="I'm sorry, but I encountered an internal error. Please try starting a new conversation.",
            is_final=True,
        ),
    )
    return [error_msg], True


# --- Update Handler Implementations ---

async def _handle_pending_tool_rejection(
    state: ConversationState,
    is_sub_agent: bool,
    rejection_reason: str,
    mcp_headers: dict[str, str],
) -> list[Message] | None:
    """Reject all pending tools. Returns messages if rejected, None if no pending tools."""
    if not state.pending_tool_ids:
        return None

    for tool_use_id, pending_msg in state.pending_tool_ids.items():
        if not pending_msg or not pending_msg.tool_request:
            continue
        # Add tool_use to pending_writes
        state.pending_writes.append(pending_msg)
        # Create rejection tool_result
        rejection = Message(
            id=_generate_message_id(),
            role=MessageRole.USER,
            tool_result=ToolResultMessage(
                tool_use_id=tool_use_id,
                tool_name=pending_msg.tool_request.tool_name,
                success=False,
                content=rejection_reason,
            ),
        )
        state.pending_writes.append(rejection)

    state.pending_tool_ids = {}

    input_ = _build_activity_input(state, is_sub_agent, mcp_headers)
    result: ActivityResult = await _execute_activity(ACTIVITY_REJECT_PENDING_TOOL, input_, result_type=ActivityResult)
    return await _process_activity_result(state, result, input_.pending_writes)


async def _process_user_message(
    state: ConversationState,
    is_sub_agent: bool,
    content: str,
    message_id: str,
    mcp_headers: dict[str, str],
) -> list[Message]:
    """Handle user conversational input."""
    # Handle implicit tool rejection if pending
    rejection_reason = f"Tool request was implicitly rejected. User said: {content}"
    rejection_msgs = await _handle_pending_tool_rejection(state, is_sub_agent, rejection_reason, mcp_headers)
    if rejection_msgs is not None:
        return rejection_msgs

    # Normal user message processing
    state.current_turn += 1

    current_message = Message(
        id=message_id,
        role=MessageRole.USER,
        timestamp=workflow.now(),
        turn_number=state.current_turn,
        user_message=UserMessage(content=content),
    )
    state.pending_writes.append(current_message)

    input_ = _build_activity_input(state, is_sub_agent, mcp_headers)
    result: ActivityResult = await _execute_activity(ACTIVITY_PROCESS_USER_MESSAGE, input_, result_type=ActivityResult)
    return await _process_activity_result(state, result, input_.pending_writes)


async def _process_server_tool_approval(
    state: ConversationState,
    is_sub_agent: bool,
    tool_use_id: str,
    tool_name: str,
    approved: bool,
    rejection_reason: str,
    mcp_headers: dict[str, str],
) -> list[Message]:
    """Handle server tool approval/rejection."""
    # Find pending tool
    found_id = ""
    pending_msg = None
    if tool_use_id:
        pending_msg, found = state.find_pending_tool_by_id(tool_use_id)
        if not found:
            raise ValueError(f"No pending request found for ToolUseId '{tool_use_id}'")
        found_id = tool_use_id
    else:
        found_id, pending_msg, found = state.find_pending_tool_by_name(tool_name)
        if not found:
            raise ValueError(f"No pending request found for tool '{tool_name}'")

    tool_request = pending_msg.tool_request
    del state.pending_tool_ids[found_id]
    state.pending_writes.append(pending_msg)

    if not approved:
        reason = rejection_reason or "User rejected the tool execution"
        rejection = Message(
            id=_generate_message_id(),
            role=MessageRole.USER,
            tool_result=ToolResultMessage(
                tool_use_id=tool_request.tool_use_id,
                tool_name=tool_request.tool_name,
                success=False,
                content=reason,
            ),
        )
        state.pending_writes.append(rejection)

        input_ = _build_activity_input(state, is_sub_agent, mcp_headers)
        result: ActivityResult = await _execute_activity(ACTIVITY_REJECT_PENDING_TOOL, input_, result_type=ActivityResult)
        return await _process_activity_result(state, result, input_.pending_writes)

    # Approved — execute the tool
    input_ = _build_activity_input(state, is_sub_agent, mcp_headers)
    result: ActivityResult = await _execute_activity(
        ACTIVITY_EXECUTE_SERVER_TOOL,
        input_,
        tool_request.tool_use_id,
        tool_request.tool_name,
        tool_request.parameters,
        result_type=ActivityResult,
    )
    return await _process_activity_result(state, result, input_.pending_writes)


async def _process_client_tool_result(
    state: ConversationState,
    is_sub_agent: bool,
    tool_use_id: str,
    tool_name: str,
    success: bool,
    content: str,
    data: dict[str, Any] | None,
    message_id: str,
    mcp_headers: dict[str, str],
) -> list[Message]:
    """Handle client tool execution result."""
    current_message = Message(
        id=message_id,
        role=MessageRole.USER,
        timestamp=workflow.now(),
        tool_result=ToolResultMessage(
            tool_use_id="",
            tool_name=tool_name,
            success=success,
            content=content,
            data=data,
        ),
    )

    # Find pending tool
    found_id = ""
    if tool_use_id:
        _, found = state.find_pending_tool_by_id(tool_use_id)
        if not found:
            raise ValueError(f"No pending request for ToolUseId '{tool_use_id}'")
        found_id = tool_use_id
    else:
        found_id, _, found = state.find_pending_tool_by_name(tool_name)
        if not found:
            raise ValueError(f"No pending request for tool '{tool_name}'")

    current_message.tool_result.tool_use_id = found_id
    pending_tool_use_msg = state.pending_tool_ids.get(found_id)
    del state.pending_tool_ids[found_id]

    # Buffer tool_use first, then tool_result (Bedrock requirement)
    if pending_tool_use_msg:
        state.pending_writes.append(pending_tool_use_msg)
    state.pending_writes.append(current_message)

    input_ = _build_activity_input(state, is_sub_agent, mcp_headers)
    result: ActivityResult = await _execute_activity(ACTIVITY_PROCESS_CLIENT_TOOL_RESULT, input_, result_type=ActivityResult)
    return await _process_activity_result(state, result, input_.pending_writes)


async def _process_end_conversation(
    state: ConversationState,
    is_sub_agent: bool,
    reason: str,
    message_id: str,
    mcp_headers: dict[str, str],
) -> list[Message]:
    """Handle conversation termination."""
    # Reject pending tools first
    rejection_reason = "Tool request was cancelled because the conversation was ended by the user."
    rejection_msgs = await _handle_pending_tool_rejection(state, is_sub_agent, rejection_reason, mcp_headers)
    if rejection_msgs is not None:
        return rejection_msgs

    state.current_turn += 1

    content = "User requested to end the conversation"
    if reason:
        content = f"User requested to end the conversation. Reason: {reason}"

    current_message = Message(
        id=message_id,
        role=MessageRole.USER,
        timestamp=workflow.now(),
        turn_number=state.current_turn,
        user_message=UserMessage(content=content),
    )
    state.pending_writes.append(current_message)

    input_ = _build_activity_input(state, is_sub_agent, mcp_headers)
    result: ActivityResult = await _execute_activity(ACTIVITY_PROCESS_END_CONVERSATION, input_, result_type=ActivityResult)
    return await _process_activity_result(state, result, input_.pending_writes, SESSION_STATUS_COMPLETED)


# --- Main Workflow Definition ---

@workflow.defn
class CompanionWorkflow:
    """Orchestrates conversation lifecycle using Update Handlers.

    Pure orchestration — activities handle business logic.
    Context comes with each update handler call, not at workflow start.
    """

    def __init__(self) -> None:
        self._state: ConversationState | None = None
        self._should_terminate = False
        self._is_sub_agent = False

    @workflow.run
    async def run(self, agent_id: str, parent_depth: int, user_id: str) -> None:
        info = workflow.info()
        workflow_id = info.workflow_id
        self._is_sub_agent = info.parent is not None
        delegation_depth = parent_depth + 1

        parent_workflow_id = ""
        if self._is_sub_agent and info.parent:
            parent_workflow_id = info.parent.workflow_id

        self._state = ConversationState(
            workflow_id=workflow_id,
            agent_id=agent_id,
            parent_workflow_id=parent_workflow_id,
            user_id=user_id,
            delegation_depth=delegation_depth,
        )

        workflow.logger.info(
            "Starting conversation workflow",
            extra={"workflow_id": workflow_id, "agent_id": agent_id, "delegation_depth": delegation_depth},
        )

        # Wait for termination
        await workflow.wait_condition(
            lambda: self._should_terminate or (self._state is not None and self._state.should_terminate)
        )

        workflow.logger.info("Conversation workflow completed", extra={"workflow_id": workflow_id})

    async def _wait_for_state(self) -> None:
        """Wait until run() has initialized self._state."""
        await workflow.wait_condition(lambda: self._state is not None)

    @workflow.update
    async def process_user_message(
        self, content: str, message_id: str, mcp_headers: dict[str, str]
    ) -> list[Message]:
        await self._wait_for_state()
        try:
            from taskmeagents.workflow.delegation import forward_to_child_if_active
            fwd_msgs, forwarded = await forward_to_child_if_active(
                self._state, UPDATE_PROCESS_USER_MESSAGE,
                [content, message_id, mcp_headers], mcp_headers,
            )
            if forwarded:
                return fwd_msgs

            messages = await _process_user_message(
                self._state, self._is_sub_agent, content, message_id, mcp_headers
            )
            return messages
        except Exception as err:
            fatal_msgs, terminate = _handle_fatal_error(self._state.agent_id, err)
            if terminate:
                self._should_terminate = True
                return fatal_msgs
            raise

    @workflow.update
    async def process_server_tool_approval(
        self,
        tool_use_id: str,
        tool_name: str,
        approved: bool,
        rejection_reason: str,
        mcp_headers: dict[str, str],
    ) -> list[Message]:
        await self._wait_for_state()
        try:
            from taskmeagents.workflow.delegation import forward_to_child_if_active
            fwd_msgs, forwarded = await forward_to_child_if_active(
                self._state, UPDATE_PROCESS_SERVER_TOOL_APPROVAL,
                [tool_use_id, tool_name, approved, rejection_reason, mcp_headers], mcp_headers,
            )
            if forwarded:
                return fwd_msgs

            messages = await _process_server_tool_approval(
                self._state, self._is_sub_agent,
                tool_use_id, tool_name, approved, rejection_reason, mcp_headers
            )
            return messages
        except Exception as err:
            fatal_msgs, terminate = _handle_fatal_error(self._state.agent_id, err)
            if terminate:
                self._should_terminate = True
                return fatal_msgs
            raise

    @workflow.update
    async def process_client_tool_result(
        self,
        tool_use_id: str,
        tool_name: str,
        success: bool,
        content: str,
        data: dict[str, Any] | None,
        message_id: str,
        mcp_headers: dict[str, str],
    ) -> list[Message]:
        await self._wait_for_state()
        try:
            from taskmeagents.workflow.delegation import forward_to_child_if_active
            fwd_msgs, forwarded = await forward_to_child_if_active(
                self._state, UPDATE_PROCESS_CLIENT_TOOL_RESULT,
                [tool_use_id, tool_name, success, content, data, message_id, mcp_headers], mcp_headers,
            )
            if forwarded:
                return fwd_msgs

            messages = await _process_client_tool_result(
                self._state, self._is_sub_agent,
                tool_use_id, tool_name, success, content, data, message_id, mcp_headers
            )
            return messages
        except Exception as err:
            fatal_msgs, terminate = _handle_fatal_error(self._state.agent_id, err)
            if terminate:
                self._should_terminate = True
                return fatal_msgs
            raise

    @workflow.update
    async def process_end_conversation(
        self, reason: str, message_id: str, mcp_headers: dict[str, str]
    ) -> list[Message]:
        await self._wait_for_state()
        try:
            from taskmeagents.workflow.delegation import forward_to_child_if_active
            fwd_msgs, forwarded = await forward_to_child_if_active(
                self._state, UPDATE_PROCESS_END_CONVERSATION,
                [reason, message_id, mcp_headers], mcp_headers,
            )
            if forwarded:
                return fwd_msgs

            messages = await _process_end_conversation(
                self._state, self._is_sub_agent, reason, message_id, mcp_headers
            )
            self._should_terminate = True
            return messages
        except Exception as err:
            fatal_msgs, terminate = _handle_fatal_error(self._state.agent_id, err)
            if terminate:
                self._should_terminate = True
                return fatal_msgs
            raise

    @workflow.update
    async def process_agent_tool(
        self,
        tool_name: str,
        tool_use_id: str,
        parameters: dict[str, Any],
        mcp_headers: dict[str, str],
    ) -> list[Message]:
        """Handle agent tool delegation — queue or start child workflow."""
        await self._wait_for_state()
        try:
            from taskmeagents.workflow.delegation import process_agent_tool_handler
            messages = await process_agent_tool_handler(
                self._state, tool_name, tool_use_id, parameters, mcp_headers,
            )
            return messages
        except Exception as err:
            fatal_msgs, terminate = _handle_fatal_error(self._state.agent_id, err)
            if terminate:
                self._should_terminate = True
                return fatal_msgs
            raise
