"""Anthropic Claude provider using direct SDK.

Replaces go_companion/internal/llm/providers/bedrock/bedrock.go
Uses anthropic Python SDK with streaming, tool use, thinking, and prompt caching.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

import anthropic

from taskmeagents.conversation.types import (
    AssistantMessage,
    Message,
    MessageRole,
    TokenUsage,
    ToolRequestMessage,
    ToolType,
)
from taskmeagents.llm.models import Model
from taskmeagents.llm.provider import (
    ErrorEvent,
    GenerateRequest,
    MessageEvent,
    Provider,
    StopReason,
    StreamEvent,
    SystemBlockType,
    UsageEvent,
)
from taskmeagents.llm.thinking import ThinkingConfig, ThinkingMode


class AnthropicProvider(Provider):
    def __init__(self, model: Model, api_key: str, thinking: ThinkingConfig | None = None):
        self._model = model
        self._thinking = thinking or ThinkingConfig()
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    def get_model(self) -> Model:
        return self._model

    async def close(self) -> None:
        await self._client.close()

    async def generate(self, request: GenerateRequest) -> AsyncIterator[StreamEvent]:
        try:
            kwargs = self._build_request(request)
            async with self._client.messages.stream(**kwargs) as stream:
                accumulated_text = ""
                thinking_text = ""
                tool_calls: list[dict[str, Any]] = []

                async for event in stream:
                    if event.type == "content_block_start":
                        if event.content_block.type == "tool_use":
                            tool_calls.append({
                                "id": event.content_block.id,
                                "name": event.content_block.name,
                                "input": "",
                            })
                    elif event.type == "content_block_delta":
                        if event.delta.type == "text_delta":
                            accumulated_text += event.delta.text
                        elif event.delta.type == "thinking_delta":
                            thinking_text += event.delta.thinking
                        elif event.delta.type == "input_json_delta":
                            if tool_calls:
                                tool_calls[-1]["input"] += event.delta.partial_json

                final_message = stream.get_final_message()

                # Emit assistant text message
                if accumulated_text:
                    msg = Message(
                        id=str(uuid.uuid4()),
                        role=MessageRole.ASSISTANT,
                        assistant_message=AssistantMessage(
                            content=accumulated_text,
                            thinking=thinking_text,
                            is_final=not tool_calls,
                        ),
                    )
                    yield MessageEvent(message=msg)

                # Emit tool request messages
                for tc in tool_calls:
                    try:
                        params = json.loads(tc["input"]) if tc["input"] else {}
                    except json.JSONDecodeError:
                        params = {}
                    msg = Message(
                        id=str(uuid.uuid4()),
                        role=MessageRole.ASSISTANT,
                        tool_request=ToolRequestMessage(
                            tool_use_id=tc["id"],
                            tool_name=tc["name"],
                            tool_type=ToolType.SERVER,
                            parameters=params,
                        ),
                    )
                    yield MessageEvent(message=msg)

                # Emit usage
                usage = final_message.usage
                stop = self._map_stop_reason(final_message.stop_reason)
                yield UsageEvent(
                    usage=TokenUsage(
                        input_tokens=usage.input_tokens,
                        output_tokens=usage.output_tokens,
                        cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
                        cache_write_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
                    ),
                    stop_reason=stop,
                )

        except anthropic.APIError as e:
            yield ErrorEvent(error=e)

    def _build_request(self, request: GenerateRequest) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self._model.provider_model_id,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }

        # System prompt
        system_blocks = []
        for block in request.system_prompt:
            if block.type == SystemBlockType.TEXT:
                sb: dict[str, Any] = {"type": "text", "text": block.content}
                if request.use_caching:
                    sb["cache_control"] = {"type": "ephemeral"}
                system_blocks.append(sb)
        if system_blocks:
            kwargs["system"] = system_blocks

        # Messages
        kwargs["messages"] = self._convert_messages(request.messages, request.use_caching)

        # Tools
        if request.tools:
            kwargs["tools"] = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.input_schema.to_dict(),
                }
                for t in request.tools
            ]

        # Thinking
        if self._thinking.is_enabled:
            if self._thinking.mode == ThinkingMode.MANUAL:
                kwargs["thinking"] = {"type": "enabled", "budget_tokens": self._thinking.budget_tokens}
                kwargs["temperature"] = 1.0  # Required for thinking
            elif self._thinking.mode == ThinkingMode.ADAPTIVE:
                kwargs["thinking"] = {"type": "enabled"}
                kwargs["temperature"] = 1.0

        return kwargs

    def _convert_messages(self, messages: list[Message], use_caching: bool) -> list[dict[str, Any]]:
        result = []
        for msg in messages:
            if msg.user_message:
                content: list[dict[str, Any]] = [{"type": "text", "text": msg.user_message.content}]
                if use_caching and msg == messages[-1]:
                    content[-1]["cache_control"] = {"type": "ephemeral"}
                result.append({"role": "user", "content": content})
            elif msg.assistant_message:
                result.append({"role": "assistant", "content": msg.assistant_message.content})
            elif msg.tool_request:
                result.append({
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": msg.tool_request.tool_use_id,
                            "name": msg.tool_request.tool_name,
                            "input": msg.tool_request.parameters,
                        }
                    ],
                })
            elif msg.tool_result:
                result.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg.tool_result.tool_use_id,
                            "content": msg.tool_result.content,
                            "is_error": not msg.tool_result.success,
                        }
                    ],
                })
        return result

    @staticmethod
    def _map_stop_reason(reason: str | None) -> StopReason:
        mapping = {
            "end_turn": StopReason.END_TURN,
            "max_tokens": StopReason.MAX_TOKENS,
            "tool_use": StopReason.TOOL_USE,
            "stop_sequence": StopReason.STOP_SEQUENCE,
        }
        return mapping.get(reason or "", StopReason.END_TURN)
