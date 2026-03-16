---
description: Use when working on conversation history persistence, session management, message queries, token usage tracking, keyset pagination, full-text search, or observation masking in TaskMeAgents.
---

# History & Persistence Patterns — TaskMeAgents

## Session Upsert (Idempotent)
```python
stmt = insert(SessionModel).values(id=session_id, ...)
stmt = stmt.on_conflict_do_update(
    index_elements=["id"],
    set_={"status": status, "last_activity_at": datetime.now(timezone.utc)},
)
```
Counter fields use SQL expression: `SessionModel.message_count + delta`

## Token Usage JSONB Merge
```python
update_dict["token_usage"] = text(
    "sessions.token_usage || :usage_delta::jsonb"
).bindparams(usage_delta=json.dumps({...}))
```

## Message Write (Idempotent)
```python
stmt = insert(MessageModel).values(
    id=f"{session_id}-{sequence}",  # deterministic ID
    ...
).on_conflict_do_nothing(index_elements=["id"])
```

## Atomic Batch Persist
`persist_batch()` wraps session upsert + message writes in a single transaction:
```python
async with db.begin():
    # upsert session
    # write all messages
```

## Keyset Pagination
```python
query = select(SessionModel).where(
    SessionModel.user_id == user_id
).order_by(SessionModel.last_activity_at.desc(), SessionModel.id)
if cursor:  # ISO timestamp from previous page
    query = query.where(SessionModel.last_activity_at < cursor)
```

## Full-Text Search
```python
result = await db.execute(text("""
    SELECT m.* FROM messages m
    JOIN sessions s ON s.id = m.session_id
    WHERE s.user_id = :user_id
    AND m.content::text ILIKE :query
"""), {"user_id": user_id, "query": f"%{query}%"})
```

## Observation Masking
Applied before LLM calls to reduce context window usage:
- Threshold: only mask if `total_tokens > 75% of max_context_tokens`
- Recent window: keep last N turns unmasked (default: 3)
- Stale tool results → replaced with `"[Tool result omitted...]"`
- Returns NEW list (original unmodified — shallow copy)

```python
masked = apply_observation_masking(
    messages, current_turn=5,
    config=MaskingConfig(enabled=True, recent_window_turns=3),
    total_tokens=100000, max_context_tokens=128000,
)
```

## Key Files
- `src/taskmeagents/history/pg_store.py` — PostgresHistoryStore
- `src/taskmeagents/history/store.py` — HistoryStore ABC
- `src/taskmeagents/conversation/masking.py` — observation masking
- `src/taskmeagents/activities/persistence.py` — PersistMessages activity
