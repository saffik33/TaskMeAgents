---
description: Use when working on file attachments, uploads, binary storage, attachment rehydration, or the Railway persistent volume storage in TaskMeAgents.
---

# Attachment Storage — TaskMeAgents

## Storage Location
Railway persistent volume at `ATTACHMENT_BASE_PATH` (default: `/data/attachments`).
Local dev: `./data/attachments` (set in `.env`).

## Directory Structure
```
{attachment_base_path}/{user_id}/{session_id}/{message_id}/{filename}
```

## Upload & Strip Pattern
Before sending through Temporal (which has payload size limits):
```python
await upload_and_strip(user_id, session_id, message_id, attachments)
# For each attachment:
#   1. Sanitize filename (os.path.basename → prevent traversal)
#   2. Write binary data to volume
#   3. Set att.uri = file path
#   4. Set att.data = None (strip binary)
```

## Rehydrate Pattern
When reading back for LLM or client delivery:
```python
await rehydrate(user_id, session_id, message_id, attachments)
# For each attachment where data is None:
#   Read binary from volume, populate att.data
```

## Security: Path Traversal Prevention
```python
def _sanitize_filename(filename: str) -> str:
    safe = os.path.basename(filename)  # strips ../  and directory components
    if not safe or safe.startswith("."):
        raise ValueError(f"Invalid filename: {filename}")
    return safe
```

## Attachment Data Flow
```
User uploads → WebSocket receives → upload_and_strip() → binary on volume, att.data=None
  → Temporal activity (no binary payload) → persist message metadata to DB
  → Later: rehydrate() reads binary back when needed
```

## Key Files
- `src/taskmeagents/history/attachments.py` — upload_and_strip, rehydrate, _sanitize_filename
- `src/taskmeagents/conversation/types.py` — Attachment dataclass
