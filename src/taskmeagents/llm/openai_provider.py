"""OpenAI provider using direct SDK.

Replaces go_companion/internal/llm/providers/google/google.go
Uses openai Python SDK with streaming and function calling.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

import openai

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


class OpenAIProvider(Provider):
    def __init__(self, model: Model, api_key: str):
        self._model = model
        self._client = openai.AsyncOpenAI(api_key=api_key)

    def get_model(self) -> Model:
        return self._model

    async def close(self) -> None:
        await self._client.close()

    async def generate(self, request: GenerateRequest) -> AsyncIterator[StreamEvent]:
        try:
            kwargs = self._build_request(request)
            stream = await self._client.chat.completions.create(**kwargs, stream=True, stream_options={"include_usage": True})

            accumulated_text = ""
            tool_calls: dict[int, dict[str, Any]] = {}  # index → {id, name, arguments}
            usage_data: TokenUsage | None = None
            last_finish_reason: str | None = None

            async for chunk in stream:
                if chunk.usage:
                    usage_data = TokenUsage(
                        input_tokens=chunk.usage.prompt_tokens or 0,
                        output_tokens=chunk.usage.completion_tokens or 0,
                    )

                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta
                finish_reason = chunk.choices[0].finish_reason
                if finish_reason:
                    last_finish_reason = finish_reason

                if delta and delta.content:
                    accumulated_text += delta.content

                if delta and delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index
                        if idx not in tool_calls:
                            tool_calls[idx] = {"id": tc_delta.id or "", "name": tc_delta.function.name or "", "arguments": ""}
                        if tc_delta.function and tc_delta.function.arguments:
                            tool_calls[idx]["arguments"] += tc_delta.function.arguments
                        if tc_delta.id:
                            tool_calls[idx]["id"] = tc_delta.id
                        if tc_delta.function and tc_delta.function.name:
                            tool_calls[idx]["name"] = tc_delta.function.name

            # Emit assistant text
            if accumulated_text:
                msg = Message(
                    id=str(uuid.uuid4()),
                    role=MessageRole.ASSISTANT,
                    assistant_message=AssistantMessage(
                        content=accumulated_text,
                        is_final=not tool_calls,
                    ),
                )
                yield MessageEvent(message=msg)

            # Emit tool calls
            for tc in tool_calls.values():
                try:
                    params = json.loads(tc["arguments"]) if tc["arguments"] else {}
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

            # Emit usage — map OpenAI finish_reason to StopReason
            stop_mapping = {
                "stop": StopReason.END_TURN,
                "tool_calls": StopReason.TOOL_USE,
                "length": StopReason.MAX_TOKENS,
                "content_filter": StopReason.CONTENT_FILTERED,
            }
            stop = stop_mapping.get(last_finish_reason or "", StopReason.END_TURN)
            yield UsageEvent(
                usage=usage_data or TokenUsage(),
                stop_reason=stop,
            )

        except openai.APIError as e:
            yield ErrorEvent(error=e)

    def _build_request(self, request: GenerateRequest) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self._model.provider_model_id,
            "max_completion_tokens": request.max_tokens,
            "temperature": request.temperature,
        }

        # Messages
        messages = self._convert_messages(request.system_prompt, request.messages)
        kwargs["messages"] = messages

        # Tools
        if request.tools:
            kwargs["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.input_schema.to_dict(),
                    },
                }
                for t in request.tools
            ]

        return kwargs

    def _convert_messages(
        self, system_blocks: list, messages: list[Message]
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []

        # System prompt
        system_text = " ".join(b.content for b in system_blocks if b.type == SystemBlockType.TEXT and b.content)
        if system_text:
            result.append({"role": "system", "content": system_text})

        for msg in messages:
            if msg.user_message:
                result.append({"role": "user", "content": msg.user_message.content})
            elif msg.assistant_message:
                result.append({"role": "assistant", "content": msg.assistant_message.content})
            elif msg.tool_request:
                result.append({
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": msg.tool_request.tool_use_id,
                            "type": "function",
                            "function": {
                                "name": msg.tool_request.tool_name,
                                "arguments": json.dumps(msg.tool_request.parameters),
                            },
                        }
                    ],
                })
            elif msg.tool_result:
                result.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_result.tool_use_id,
                    "content": msg.tool_result.content,
                })
        return result
