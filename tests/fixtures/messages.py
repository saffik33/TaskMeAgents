"""Test message fixtures."""

from datetime import datetime, timezone

from taskmeagents.conversation.types import (
    AssistantMessage,
    Message,
    MessageRole,
    TokenUsage,
    ToolRequestMessage,
    ToolResultMessage,
    ToolType,
    UserMessage,
)


def make_user_message(content: str = "Hello", turn: int = 1, msg_id: str = "msg-u-1") -> Message:
    return Message(
        id=msg_id,
        role=MessageRole.USER,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        turn_number=turn,
        user_message=UserMessage(content=content),
    )


def make_assistant_message(
    content: str = "Hi there!", turn: int = 1, is_final: bool = True, msg_id: str = "msg-a-1"
) -> Message:
    return Message(
        id=msg_id,
        role=MessageRole.ASSISTANT,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        turn_number=turn,
        assistant_message=AssistantMessage(content=content, is_final=is_final),
    )


def make_tool_request(
    tool_name: str = "get_weather",
    tool_use_id: str = "tu-1",
    tool_type: ToolType = ToolType.SERVER,
    parameters: dict | None = None,
    auto_approve: bool = False,
    turn: int = 1,
    msg_id: str = "msg-tr-1",
) -> Message:
    return Message(
        id=msg_id,
        role=MessageRole.ASSISTANT,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        turn_number=turn,
        tool_request=ToolRequestMessage(
            tool_use_id=tool_use_id,
            tool_name=tool_name,
            tool_type=tool_type,
            parameters=parameters or {"city": "London"},
            auto_approve=auto_approve,
        ),
    )


def make_tool_result(
    tool_name: str = "get_weather",
    tool_use_id: str = "tu-1",
    content: str = "Sunny, 22C",
    success: bool = True,
    turn: int = 1,
    msg_id: str = "msg-tres-1",
) -> Message:
    return Message(
        id=msg_id,
        role=MessageRole.USER,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        turn_number=turn,
        tool_result=ToolResultMessage(
            tool_use_id=tool_use_id,
            tool_name=tool_name,
            success=success,
            content=content,
        ),
    )


def make_token_usage(inp: int = 100, out: int = 50) -> TokenUsage:
    return TokenUsage(input_tokens=inp, output_tokens=out, request_cost=0.001)
