Investigate an issue in the TaskMeAgents system.

**Input**: $ARGUMENTS — description of the issue or symptom.

## Investigation Workflow

### Step 1: Health Check
```bash
curl -sf http://localhost:8000/health
docker compose ps
```

### Step 2: Check Temporal Workflows
```python
# List running workflows
python -c "
import asyncio
from temporalio.client import Client
async def check():
    client = await Client.connect('localhost:7233')
    async for wf in client.list_workflows('ExecutionStatus=\"Running\"'):
        print(f'{wf.id} ({wf.workflow_type})')
asyncio.run(check())
"
```
Temporal UI: http://localhost:8233

### Step 3: Check Workflow History (if workflow ID known)
```python
python -c "
import asyncio
from temporalio.client import Client
async def check():
    client = await Client.connect('localhost:7233')
    handle = client.get_workflow_handle('<WORKFLOW_ID>')
    async for event in handle.fetch_history_events():
        etype = event.WhichOneof('attributes')
        attrs = getattr(event, etype)
        extra = ''
        if 'failed' in etype and hasattr(attrs, 'failure') and attrs.failure:
            extra = f' — {attrs.failure.message[:200]}'
        print(f'{etype}{extra}')
asyncio.run(check())
"
```

### Step 4: Check Database
```bash
docker exec taskmeagents-postgres-1 psql -U postgres -d TaskMeAgents -c "
SET search_path TO taskme_agents;
SELECT id, status, agent_id, turn_count, last_activity_at FROM sessions ORDER BY last_activity_at DESC LIMIT 5;
"
```

### Step 5: Check Server Logs
Look at the terminal running `python -m taskmeagents.main` for errors.

## Common Issues

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| "internal error" in chat | Workflow task failed | Check Temporal history for error message |
| WebSocket hangs | Worker not running | Restart server, check for sandbox errors |
| 401 on API | Invalid API key | Check ADMIN_API_KEY in .env |
| Activity fails with "not initialized" | Factory/store not init'd | Restart server (don't run worker separately) |
| "side_effect" error | Wrong Temporal API | Use `workflow.uuid4()` not `workflow.side_effect()` |

## Service Endpoints
- FastAPI: http://localhost:8000 (API docs at /docs)
- Temporal UI: http://localhost:8233
- PostgreSQL: localhost:5433 (DB: TaskMeAgents, schema: taskme_agents)
