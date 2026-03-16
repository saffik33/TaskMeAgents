---
description: Use when creating or modifying Temporal workflow code, update handlers, child workflows, delegation logic, or workflow state management in TaskMeAgents.
---

# Temporal Workflow Development — TaskMeAgents

## CRITICAL: Determinism Rules
Temporal replays workflows from event history. Any non-deterministic call breaks replay.

### NEVER use in workflow code:
```python
# WRONG — non-deterministic
uuid.uuid4()
datetime.now()
datetime.now(timezone.utc)
random.random()
__import__("module")
```

### ALWAYS use instead:
```python
# CORRECT — Temporal deterministic APIs
workflow.uuid4()           # deterministic UUID
workflow.now()             # deterministic timestamp
workflow.random()          # deterministic random
```

## Import Pattern
ALL non-stdlib imports MUST be inside `workflow.unsafe.imports_passed_through()`:

```python
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from taskmeagents.activities.types import ActivityInput, ActivityResult, PersistInput
    from taskmeagents.conversation.types import Message, MessageRole, UserMessage
    from taskmeagents.workflow.constants import ACTIVITY_PROCESS_USER_MESSAGE
    from taskmeagents.workflow.state import ConversationState
```

Imports inside function bodies (lazy imports) are acceptable for breaking circular dependencies.

## Update Handler Pattern
Every `@workflow.update` handler MUST wait for state initialization:

```python
@workflow.update
async def process_user_message(self, content: str, ...) -> list[Message]:
    await self._wait_for_state()  # MUST be first line
    try:
        # ... handler logic
    except Exception as err:
        fatal_msgs, terminate = _handle_fatal_error(self._state.agent_id, err)
        if terminate:
            self._should_terminate = True
            return fatal_msgs
        raise
```

## Activity Execution
Always pass `result_type` for proper deserialization:

```python
result: ActivityResult = await _execute_activity(
    ACTIVITY_PROCESS_USER_MESSAGE, input_, result_type=ActivityResult
)
```

## State Management
- `pending_tool_ids`: Maps tool_use_id → Message (deferred until tool_result arrives)
- `pending_writes`: Captured and cleared by `_build_activity_input()` before each activity
- `should_terminate`: Set AFTER `PersistMessages` completes (never before)
- `_process_activity_result()`: Routes tool requests to pending_tool_ids, persists separately

## Key Files
- `src/taskmeagents/workflow/companion_workflow.py` — main workflow
- `src/taskmeagents/workflow/delegation.py` — sub-agent delegation
- `src/taskmeagents/workflow/state.py` — ConversationState dataclass
- `src/taskmeagents/workflow/constants.py` — activity/update names, timeouts
