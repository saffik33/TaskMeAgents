---
description: Use when working on scheduled Temporal workflows, cleanup jobs, inactive conversation termination, Temporal schedules, or cron-like background tasks in TaskMeAgents.
---

# Scheduled Workflows — TaskMeAgents

## Cleanup Workflow
`CleanupInactiveConversationsWorkflow` terminates stale conversations.

### How It Works
1. Activity queries Temporal visibility: `WorkflowType="CompanionWorkflow" AND ExecutionStatus="Running" AND LastActivityTime < threshold`
2. For each stale workflow: send `EndConversation` update (graceful shutdown)
3. If update fails: fall back to `CancelWorkflow` (forced termination)
4. Activity heartbeats progress before each operation

### Workflow Definition
```python
@workflow.defn
class CleanupInactiveConversationsWorkflow:
    @workflow.run
    async def run(self, inactivity_threshold_minutes: int = 30) -> CleanupResult:
        result = await workflow.execute_activity(
            cleanup_activity,
            args=[inactivity_threshold_minutes],
            start_to_close_timeout=timedelta(minutes=15),
            heartbeat_timeout=timedelta(minutes=2),
        )
        return result
```

### Create Temporal Schedule
```bash
temporal schedule create \
  --schedule-id cleanup-inactive \
  --workflow-type CleanupInactiveConversationsWorkflow \
  --task-queue taskme-agents \
  --input '30' \
  --interval 10m
```

### LastActivityTime Search Attribute
Updated at the start of each workflow update handler. Used by cleanup queries to find stale workflows. Set via:
```python
# In Go version: workflow.UpsertTypedSearchAttributes()
# In Python: not yet implemented (Temporal Python SDK limitation)
# Cleanup currently relies on workflow.now() timestamps in visibility
```

### Registration
Both workflow and activity registered in `temporal_/worker.py`:
```python
workflows=[CompanionWorkflow, CleanupInactiveConversationsWorkflow]
activities=[..., cleanup_inactive_conversations_activity]
```

## Key Files
- `src/taskmeagents/workflow/cleanup.py` — workflow + activity
- `src/taskmeagents/temporal_/worker.py` — registration
