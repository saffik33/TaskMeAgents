"""Mock tests for Anthropic LLM provider."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from taskmeagents.conversation.types import Message, UserMessage
from taskmeagents.llm.anthropic_provider import AnthropicProvider
from taskmeagents.llm.models import REGISTRY
from taskmeagents.llm.provider import (
    ErrorEvent,
    GenerateRequest,
    MessageEvent,
    SystemBlock,
    SystemBlockType,
    UsageEvent,
)


def _make_request(content: str = "Hello") -> GenerateRequest:
    msg = Message(id="m1", role="user", user_message=UserMessage(content=content))
    return GenerateRequest(
        system_prompt=[SystemBlock(type=SystemBlockType.TEXT, content="You are helpful.")],
        messages=[msg],
        tools=[],
    )


def _mock_final_message(text: str = "Hi!", stop_reason: str = "end_turn", tool_calls: list | None = None):
    usage = MagicMock()
    usage.input_tokens = 100
    usage.output_tokens = 50
    usage.cache_read_input_tokens = 10
    usage.cache_creation_input_tokens = 5
    msg = MagicMock()
    msg.usage = usage
    msg.stop_reason = stop_reason
    msg.content = [MagicMock(type="text", text=text)]
    return msg


class MockStreamContext:
    """Mock for `async with client.messages.stream() as stream:`"""

    def __init__(self, events, final_message):
        self.events = events
        self._final = final_message

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def __aiter__(self):
        return self._async_iter()

    async def _async_iter(self):
        for e in self.events:
            yield e

    def get_final_message(self):
        return self._final


def _text_event(text: str):
    e = MagicMock()
    e.type = "content_block_delta"
    e.delta = MagicMock()
    e.delta.type = "text_delta"
    e.delta.text = text
    return e


def _thinking_event(text: str):
    e = MagicMock()
    e.type = "content_block_delta"
    e.delta = MagicMock()
    e.delta.type = "thinking_delta"
    e.delta.thinking = text
    return e


def _tool_start_event(tool_id: str, name: str):
    e = MagicMock()
    e.type = "content_block_start"
    e.content_block = MagicMock()
    e.content_block.type = "tool_use"
    e.content_block.id = tool_id
    e.content_block.name = name
    return e


def _tool_delta_event(partial_json: str):
    e = MagicMock()
    e.type = "content_block_delta"
    e.delta = MagicMock()
    e.delta.type = "input_json_delta"
    e.delta.partial_json = partial_json
    return e


@pytest.mark.asyncio
async def test_stream_text_only():
    model = REGISTRY["claude-sonnet-4-6"]
    provider = AnthropicProvider(model, "fake-key")

    events = [_text_event("Hello "), _text_event("world!")]
    final = _mock_final_message("Hello world!")
    mock_stream = MockStreamContext(events, final)

    with patch.object(provider._client.messages, "stream", return_value=mock_stream):
        results = [e async for e in provider.generate(_make_request())]

    msg_events = [e for e in results if isinstance(e, MessageEvent)]
    assert len(msg_events) == 1
    assert msg_events[0].message.assistant_message.content == "Hello world!"
    assert msg_events[0].message.assistant_message.is_final is True


@pytest.mark.asyncio
async def test_stream_tool_use():
    model = REGISTRY["claude-sonnet-4-6"]
    provider = AnthropicProvider(model, "fake-key")

    events = [
        _tool_start_event("tu-1", "get_weather"),
        _tool_delta_event('{"city":'),
        _tool_delta_event('"London"}'),
    ]
    final = _mock_final_message("", stop_reason="tool_use")
    mock_stream = MockStreamContext(events, final)

    with patch.object(provider._client.messages, "stream", return_value=mock_stream):
        results = [e async for e in provider.generate(_make_request())]

    msg_events = [e for e in results if isinstance(e, MessageEvent)]
    tool_msgs = [e for e in msg_events if e.message.tool_request]
    assert len(tool_msgs) == 1
    assert tool_msgs[0].message.tool_request.tool_name == "get_weather"
    assert tool_msgs[0].message.tool_request.parameters == {"city": "London"}


@pytest.mark.asyncio
async def test_stream_text_plus_tool():
    model = REGISTRY["claude-sonnet-4-6"]
    provider = AnthropicProvider(model, "fake-key")

    events = [
        _text_event("Let me check."),
        _tool_start_event("tu-1", "search"),
        _tool_delta_event('{"q": "test"}'),
    ]
    final = _mock_final_message("Let me check.", stop_reason="tool_use")
    mock_stream = MockStreamContext(events, final)

    with patch.object(provider._client.messages, "stream", return_value=mock_stream):
        results = [e async for e in provider.generate(_make_request())]

    msg_events = [e for e in results if isinstance(e, MessageEvent)]
    text_msgs = [e for e in msg_events if e.message.assistant_message]
    tool_msgs = [e for e in msg_events if e.message.tool_request]
    assert len(text_msgs) == 1
    assert text_msgs[0].message.assistant_message.is_final is False  # has tool calls
    assert len(tool_msgs) == 1


@pytest.mark.asyncio
async def test_stream_thinking():
    model = REGISTRY["claude-sonnet-4-6"]
    provider = AnthropicProvider(model, "fake-key")

    events = [_thinking_event("Hmm... "), _thinking_event("let me think"), _text_event("Here's my answer.")]
    final = _mock_final_message("Here's my answer.")
    mock_stream = MockStreamContext(events, final)

    with patch.object(provider._client.messages, "stream", return_value=mock_stream):
        results = [e async for e in provider.generate(_make_request())]

    msg_events = [e for e in results if isinstance(e, MessageEvent)]
    assert msg_events[0].message.assistant_message.thinking == "Hmm... let me think"


@pytest.mark.asyncio
async def test_stream_usage():
    model = REGISTRY["claude-sonnet-4-6"]
    provider = AnthropicProvider(model, "fake-key")

    events = [_text_event("Hi")]
    final = _mock_final_message("Hi")
    mock_stream = MockStreamContext(events, final)

    with patch.object(provider._client.messages, "stream", return_value=mock_stream):
        results = [e async for e in provider.generate(_make_request())]

    usage_events = [e for e in results if isinstance(e, UsageEvent)]
    assert len(usage_events) == 1
    assert usage_events[0].usage.input_tokens == 100
    assert usage_events[0].usage.output_tokens == 50
    assert usage_events[0].usage.cache_read_tokens == 10


@pytest.mark.asyncio
async def test_api_error():
    import anthropic

    model = REGISTRY["claude-sonnet-4-6"]
    provider = AnthropicProvider(model, "fake-key")

    with patch.object(
        provider._client.messages, "stream",
        side_effect=anthropic.APIError(message="rate limited", request=MagicMock(), body=None),
    ):
        results = [e async for e in provider.generate(_make_request())]

    error_events = [e for e in results if isinstance(e, ErrorEvent)]
    assert len(error_events) == 1
