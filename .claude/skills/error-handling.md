---
description: Use when implementing error handling, exception recovery, error codes, fatal error patterns, or debugging error flows in TaskMeAgents.
---

# Error Handling Patterns — TaskMeAgents

## Workflow Error Pattern (Fatal vs Recoverable)
Every workflow update handler uses this pattern:
```python
@workflow.update
async def process_user_message(self, ...) -> list[Message]:
    await self._wait_for_state()
    try:
        # ... handler logic
    except Exception as err:
        # ALL exceptions → generic user message (never leak internals)
        fatal_msgs, terminate = _handle_fatal_error(self._state.agent_id, err)
        if terminate:
            self._should_terminate = True
            return fatal_msgs
        raise  # re-raise if not handled
```

`_handle_fatal_error` logs the real error and returns:
> "I'm sorry, but I encountered an internal error. Please try starting a new conversation."

## WebSocket Error Codes
| Code | Meaning | When |
|------|---------|------|
| 4001 | Invalid API key | Auth validation failed before accept |
| Generic `WsError` | Internal error | Any processing error during session |

```python
# Auth error (before accept)
await ws.close(code=4001, reason="Invalid API key")

# Processing error (after accept)
await ws.send_json(WsError(message="An internal error occurred.", code="INTERNAL").model_dump())
```

## Activity Error Handling
Activities retry automatically (3 attempts, 500ms → 750ms → 1125ms backoff).
Non-retryable errors should use:
```python
from temporalio.exceptions import ApplicationError
raise ApplicationError("message", non_retryable=True)
```

## LLM Provider Errors
```python
async for event in provider.generate(request):
    if isinstance(event, ErrorEvent):
        logger.error("llm.error", error=str(event.error))
        raise event.error  # Propagates to activity → workflow → user
```

## Empty LLM Response
If LLM returns no messages and no error → `ActivityResult(messages=[])` → workflow gets empty list → no assistant message streamed → client sees nothing. Always check for empty results.

## Key Principle
**Never expose internal errors to users.** Log the full error, return a generic message.

## Key Files
- `src/taskmeagents/workflow/companion_workflow.py` — `_handle_fatal_error()`
- `src/taskmeagents/api/websocket_chat.py` — WebSocket error handling
- `src/taskmeagents/workflow/constants.py` — retry policy
