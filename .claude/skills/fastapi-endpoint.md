---
description: Use when creating or modifying FastAPI REST endpoints, WebSocket handlers, API routes, request/response schemas, or authentication middleware in TaskMeAgents.
---

# FastAPI Endpoint Development — TaskMeAgents

## REST Endpoint Pattern
```python
from fastapi import APIRouter, Depends, HTTPException
from taskmeagents.auth.middleware import AuthUser, get_current_user
from taskmeagents.database import get_db

router = APIRouter(prefix="/api/my-resource", tags=["my-resource"])

@router.get("", response_model=list[MyResponse])
async def list_items(
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(get_current_user),  # REQUIRED for auth
):
    ...
```

## WebSocket Pattern
```python
@router.websocket("/ws/my-endpoint")
async def my_websocket(ws: WebSocket, api_key: str, ...):
    # 1. Validate BEFORE accept
    async with async_session_factory() as db:
        key_record = await validate_api_key(db, api_key)
    if not key_record:
        await ws.close(code=4001, reason="Invalid API key")
        return

    # 2. Accept AFTER validation
    await ws.accept()

    # 3. Message loop
    while True:
        raw = await ws.receive_json()
        ...
```

## Route Ordering
Specific paths MUST come before parameterized catch-alls:
```python
@router.get("/search")           # FIRST — specific
@router.get("/{resource_id}")    # SECOND — catch-all
```

## Schemas
Define in `src/taskmeagents/schemas/`:
```python
from pydantic import BaseModel

class MyCreate(BaseModel):
    name: str
    ...

class MyResponse(BaseModel):
    id: str
    name: str
    created_at: datetime
```

## Router Registration
Add to `src/taskmeagents/main.py`:
```python
from taskmeagents.api.my_resource import router as my_router
app.include_router(my_router)
```

## Key Files
- `src/taskmeagents/api/` — all routers
- `src/taskmeagents/schemas/` — Pydantic models
- `src/taskmeagents/auth/middleware.py` — `get_current_user` dependency
- `src/taskmeagents/main.py` — app creation, router registration, CORS

## WebSocket Message Types Reference

### Server → Client (9 types)
| Type | Fields | When |
|------|--------|------|
| `session_established` | session_id | First message after connect |
| `assistant_message` | content, is_final, message_id, agent_id | LLM response |
| `assistant_thinking` | content | Reasoning content |
| `tool_execution_request` | tool_name, tool_use_id, parameters, tool_type | Client tool needed |
| `tool_approval_request` | tool_name, tool_use_id, parameters, description | Server tool needs approval |
| `tool_result` | tool_name, tool_use_id, success, content, data, was_auto_approved | Tool completed |
| `usage` | input_tokens, output_tokens, cache_*, total_*, request_cost | Token counts |
| `error` | message, code | Error occurred |
| `end` | reason | Session ended |

### Client → Server (4 types)
| Type | Fields | When |
|------|--------|------|
| `user_message` | content, message_id | User sends message |
| `client_tool_result` | tool_use_id, tool_name, success, content, result_data | Tool completed |
| `server_tool_approval` | tool_use_id, tool_name, approved, rejection_reason | Approve/reject tool |
| `end_conversation` | reason | End session |
