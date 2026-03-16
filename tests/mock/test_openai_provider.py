"""Mock tests for OpenAI LLM provider."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from taskmeagents.conversation.types import Message, UserMessage
from taskmeagents.llm.models import REGISTRY
from taskmeagents.llm.openai_provider import OpenAIProvider
from taskmeagents.llm.provider import (
    ErrorEvent,
    GenerateRequest,
    MessageEvent,
    StopReason,
    SystemBlock,
    SystemBlockType,
    UsageEvent,
)


def _make_request() -> GenerateRequest:
    msg = Message(id="m1", role="user", user_message=UserMessage(content="Hello"))
    return GenerateRequest(
        system_prompt=[SystemBlock(type=SystemBlockType.TEXT, content="Be helpful.")],
        messages=[msg],
        tools=[],
    )


def _make_chunk(content: str | None = None, tool_call=None, finish_reason=None, usage=None):
    chunk = MagicMock()
    chunk.usage = usage
    choice = MagicMock()
    choice.finish_reason = finish_reason
    delta = MagicMock()
    delta.content = content
    delta.tool_calls = [tool_call] if tool_call else None
    choice.delta = delta
    chunk.choices = [choice]
    return chunk


def _make_tool_call_delta(index: int, tc_id: str | None, name: str | None, args: str | None):
    tc = MagicMock()
    tc.index = index
    tc.id = tc_id
    tc.function = MagicMock()
    tc.function.name = name
    tc.function.arguments = args
    return tc


class _MockAsyncStream:
    """Awaitable async iterable — mimics OpenAI's stream response."""
    def __init__(self, chunks):
        self._chunks = chunks
    def __await__(self):
        async def _ret(): return self
        return _ret().__await__()
    def __aiter__(self):
        return self._gen()
    async def _gen(self):
        for c in self._chunks:
            yield c


@pytest.mark.asyncio
async def test_stream_text():
    model = REGISTRY["gpt-4o"]
    provider = OpenAIProvider(model, "fake-key")

    chunks = [
        _make_chunk(content="Hello "),
        _make_chunk(content="world!", finish_reason="stop"),
        _make_chunk(content=None, usage=MagicMock(prompt_tokens=50, completion_tokens=20)),
    ]
    chunks[-1].choices = []  # usage-only chunk

    with patch.object(provider._client.chat.completions, "create", return_value=_MockAsyncStream(chunks)):
        results = [e async for e in provider.generate(_make_request())]

    msg_events = [e for e in results if isinstance(e, MessageEvent)]
    assert msg_events[0].message.assistant_message.content == "Hello world!"


@pytest.mark.asyncio
async def test_stream_tool_calls():
    model = REGISTRY["gpt-4o"]
    provider = OpenAIProvider(model, "fake-key")

    chunks = [
        _make_chunk(tool_call=_make_tool_call_delta(0, "call-1", "search", '{"q":')),
        _make_chunk(tool_call=_make_tool_call_delta(0, None, None, ' "test"}')),
        _make_chunk(finish_reason="tool_calls"),
        _make_chunk(content=None, usage=MagicMock(prompt_tokens=50, completion_tokens=20)),
    ]
    chunks[-1].choices = []

    with patch.object(provider._client.chat.completions, "create", return_value=_MockAsyncStream(chunks)):
        results = [e async for e in provider.generate(_make_request())]

    msg_events = [e for e in results if isinstance(e, MessageEvent)]
    tool_msgs = [e for e in msg_events if e.message.tool_request]
    assert len(tool_msgs) == 1
    assert tool_msgs[0].message.tool_request.tool_name == "search"
    assert tool_msgs[0].message.tool_request.parameters == {"q": "test"}


@pytest.mark.asyncio
async def test_stream_finish_reason_mapping():
    model = REGISTRY["gpt-4o"]
    provider = OpenAIProvider(model, "fake-key")

    for reason, expected in [("stop", StopReason.END_TURN), ("length", StopReason.MAX_TOKENS),
                              ("content_filter", StopReason.CONTENT_FILTERED)]:
        chunks = [
            _make_chunk(content="x", finish_reason=reason),
            _make_chunk(content=None, usage=MagicMock(prompt_tokens=10, completion_tokens=5)),
        ]
        chunks[-1].choices = []

        with patch.object(provider._client.chat.completions, "create", return_value=_MockAsyncStream(chunks)):
            results = [e async for e in provider.generate(_make_request())]

        usage_events = [e for e in results if isinstance(e, UsageEvent)]
        assert usage_events[0].stop_reason == expected


@pytest.mark.asyncio
async def test_stream_usage():
    model = REGISTRY["gpt-4o"]
    provider = OpenAIProvider(model, "fake-key")

    usage_mock = MagicMock(prompt_tokens=100, completion_tokens=50)
    chunks = [
        _make_chunk(content="Hi", finish_reason="stop"),
        _make_chunk(content=None, usage=usage_mock),
    ]
    chunks[-1].choices = []

    with patch.object(provider._client.chat.completions, "create", return_value=_MockAsyncStream(chunks)):
        results = [e async for e in provider.generate(_make_request())]

    usage_events = [e for e in results if isinstance(e, UsageEvent)]
    assert usage_events[0].usage.input_tokens == 100
    assert usage_events[0].usage.output_tokens == 50


@pytest.mark.asyncio
async def test_api_error():
    import openai

    model = REGISTRY["gpt-4o"]
    provider = OpenAIProvider(model, "fake-key")

    with patch.object(
        provider._client.chat.completions, "create",
        side_effect=openai.APIError(message="quota exceeded", request=MagicMock(), body=None),
    ):
        results = [e async for e in provider.generate(_make_request())]

    assert any(isinstance(e, ErrorEvent) for e in results)
