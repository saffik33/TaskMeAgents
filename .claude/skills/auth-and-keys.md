---
description: Use when working on authentication, API key management, key generation, key validation, authorization middleware, or security patterns in TaskMeAgents.
---

# Authentication & API Key Management — TaskMeAgents

## Key Format
```
tma_<32-byte-urlsafe-random>
```
Example: `tma_Ab3dEf5gHi7jKlMnOpQrStUvWxYz012345678`

## Key Lifecycle
1. **Generate**: `generate_api_key()` → `tma_` + `secrets.token_urlsafe(32)`
2. **Hash**: `hash_api_key(key)` → SHA-256 hex digest (64 chars)
3. **Store**: Only the hash is stored in `api_keys` table (never the raw key)
4. **Validate**: Hash the incoming key, query DB for matching active hash
5. **Track**: Update `last_used_at = func.now()` on each successful validation

## REST Auth (Header)
```python
# Client sends:
X-API-Key: tma_your_key_here

# FastAPI dependency:
from taskmeagents.auth.middleware import get_current_user, AuthUser
async def my_endpoint(user: AuthUser = Depends(get_current_user)):
    print(user.user_id, user.key_name)
```

## WebSocket Auth (Query Param)
```python
# Client connects:
ws://localhost:8000/ws/chat?api_key=tma_key&agent_id=...

# Handler validates BEFORE accept:
key_record = await validate_api_key(db, api_key)
if not key_record:
    await ws.close(code=4001, reason="Invalid API key")
    return
await ws.accept()  # ONLY after validation
```

## Bootstrap (First API Key)
Set `ADMIN_API_KEY` in `.env` → server seeds it on startup via `_seed_admin_key()`:
```python
key_hash = hashlib.sha256(settings.admin_api_key.encode()).hexdigest()
# Inserts if not exists with user_id="admin", name="admin"
```

## Database Schema
```sql
CREATE TABLE taskme_agents.api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key_hash VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    last_used_at TIMESTAMPTZ
);
CREATE INDEX idx_api_keys_hash ON api_keys(key_hash) WHERE is_active = true;
```

## Key Files
- `src/taskmeagents/auth/api_key.py` — generate, hash, validate, create
- `src/taskmeagents/auth/middleware.py` — FastAPI `get_current_user` dependency
- `src/taskmeagents/models/api_key.py` — ORM model
- `src/taskmeagents/main.py` — `_seed_admin_key()` bootstrap
