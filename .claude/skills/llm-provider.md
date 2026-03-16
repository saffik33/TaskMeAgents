---
description: Use when creating or modifying LLM provider integrations, streaming responses, tool use handling, thinking/reasoning modes, or the model registry in TaskMeAgents.
---

# LLM Provider Development — TaskMeAgents

## Provider ABC
```python
from taskmeagents.llm.provider import Provider, GenerateRequest, StreamEvent, MessageEvent, UsageEvent, ErrorEvent

class MyProvider(Provider):
    async def generate(self, request: GenerateRequest) -> AsyncIterator[StreamEvent]:
        # Stream LLM response
        yield MessageEvent(message=...)  # text or tool_use
        yield UsageEvent(usage=..., stop_reason=...)

    def get_model(self) -> Model:
        return self._model

    async def close(self) -> None:
        await self._client.close()
```

## Streaming Pattern
1. Accumulate text chunks into single `AssistantMessage`
2. Collect tool calls (parse JSON parameters)
3. Emit `MessageEvent` for each complete message
4. Emit `UsageEvent` at the end with token counts + stop reason
5. On error: yield `ErrorEvent`

## Tool Use Handling
```python
# Tool request message
msg = Message(
    id=str(uuid.uuid4()),
    role=MessageRole.ASSISTANT,
    tool_request=ToolRequestMessage(
        tool_use_id=tc["id"],
        tool_name=tc["name"],
        parameters=json.loads(tc["input"]),
    ),
)
yield MessageEvent(message=msg)
```

## Stop Reason Mapping
```python
class StopReason(str, Enum):
    END_TURN = "end_turn"
    MAX_TOKENS = "max_tokens"
    TOOL_USE = "tool_use"
    CONTENT_FILTERED = "content_filtered"
    ERROR = "error"
```

Map provider-specific values: Anthropic `"end_turn"` → `END_TURN`, OpenAI `"stop"` → `END_TURN`, `"length"` → `MAX_TOKENS`.

## Model Registry
Add new models to `src/taskmeagents/llm/models.py`:
```python
REGISTRY["my-model"] = Model(
    id="my-model",
    provider_model_id="actual-api-model-name",
    display_name="My Model",
    vendor=Vendor.OPENAI,
    provider_type=ProviderType.OPENAI,
    prices=Prices(input=2.50, output=10.0),
    capabilities=Capabilities(streaming=True, tool_use=True, vision=True),
    context_window=128000,
    max_output_tokens=16384,
)
```

## Key Files
- `src/taskmeagents/llm/provider.py` — ABC + StreamEvent types
- `src/taskmeagents/llm/models.py` — model registry + cost calculation
- `src/taskmeagents/llm/anthropic_provider.py` — Anthropic implementation
- `src/taskmeagents/llm/openai_provider.py` — OpenAI implementation
- `src/taskmeagents/llm/thinking.py` — ThinkingConfig
