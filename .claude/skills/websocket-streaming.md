---
description: Use when working on WebSocket chat streaming, the two-phase message protocol, auto-approve recursion, message routing between Temporal workflow and WebSocket client, or the companion stream handler in TaskMeAgents.
---

# WebSocket Streaming Protocol — TaskMeAgents

## Two-Phase Streaming Architecture
Messages are streamed in strict order to ensure users see context before action prompts.

### Phase 1a — Context (streamed immediately)
- `assistant_message` — LLM text response
- `assistant_thinking` — reasoning content
- `tool_result` — completed tool execution results
- `usage` — token counts and cost

### Phase 1b — Actions (streamed after all context)
- `tool_execution_request` — client tools needing local execution
- `tool_approval_request` — server tools needing user approval

### Phase 2 — Deferred Tools (recursive execution)
- Agent tools → `ProcessAgentTool` workflow update → recurse
- Auto-approved server tools → `ProcessServerToolApproval` update → recurse
- Max recursion depth: `MAX_AUTO_APPROVE_DEPTH = 100`

## Message Classification
```python
for msg in messages:
    if msg.tool_request and msg.tool_request.tool_type == ToolType.AGENT:
        deferred_tools.append(msg)        # Phase 2
    elif msg.tool_request and msg.tool_request.auto_approve:
        deferred_tools.append(msg)        # Phase 2
    elif msg.tool_request:
        approval_requests.append(msg)     # Phase 1b
    else:
        _stream_message(ws, msg)          # Phase 1a (immediate)
```

## Server → Client Message Types (8)
| Type | When sent |
|------|-----------|
| `session_established` | First message after WS connect |
| `assistant_message` | LLM text response (with `is_final` flag) |
| `assistant_thinking` | Reasoning/thinking content |
| `tool_execution_request` | Client tool needs execution |
| `tool_approval_request` | Server tool needs user approval |
| `tool_result` | Tool execution completed |
| `usage` | Token counts + cost |
| `error` | Error occurred |
| `end` | Session ended |

## Client → Server Message Types (4)
| Type | When sent |
|------|-----------|
| `user_message` | User sends a message |
| `client_tool_result` | Client completed tool execution |
| `server_tool_approval` | User approves/rejects server tool |
| `end_conversation` | User ends session |

## Key Files
- `src/taskmeagents/services/companion.py` — `process_and_stream_messages()`
- `src/taskmeagents/api/websocket_chat.py` — WebSocket endpoint
- `src/taskmeagents/schemas/chat.py` — all WS message schemas
