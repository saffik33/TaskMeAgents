---
description: Use when creating or modifying Temporal activity code, LLM call activities, persistence activities, or MCP tool execution activities in TaskMeAgents.
---

# Temporal Activity Development — TaskMeAgents

## Activity Definition
```python
from temporalio import activity

@activity.defn(name="MyActivityName")
async def my_activity(input_: ActivityInput) -> ActivityResult:
    # Activity logic here
    ...
```

## Design Principle: Activities are READ-ONLY
- Activities NEVER write to PostgreSQL directly
- `PersistMessages` is the ONLY activity that writes to DB
- LLM activities: load history → merge pending → call LLM → return delta

## Standard Activity Pattern
```python
@activity.defn(name="ProcessUserMessage")
async def process_user_message(input_: ActivityInput) -> ActivityResult:
    agent = await _get_agent(input_.agent_id, input_.is_sub_agent)
    history = await _load_and_merge_history(input_)
    return await _generate_and_aggregate(agent, history, input_.context)
```

## Activity Types
```python
@dataclass
class ActivityInput:
    workflow_id: str
    agent_id: str
    is_sub_agent: bool
    user_id: str
    current_turn: int
    context: ContextUpdate | None
    mcp_headers: dict[str, str]
    pending_writes: list[Message]    # merged in-memory, NOT written

@dataclass
class ActivityResult:
    messages: list[Message]          # NOT yet persisted
    should_terminate: bool = False
    was_blocked: bool = False

@dataclass
class PersistInput:
    workflow_id: str
    agent_id: str
    user_id: str
    current_turn: int
    messages: list[Message]
    session_status: str = "running"
```

## Registration
New activities MUST be registered in `src/taskmeagents/temporal_/worker.py`:
```python
worker = Worker(
    client,
    task_queue=settings.temporal_task_queue,
    activities=[
        ...,
        my_new_activity,  # Add here
    ],
)
```

## Singletons (available in activities)
```python
from taskmeagents.services.agent_factory import get_agent_factory, get_history_store
factory = get_agent_factory()   # cached agent instances
store = get_history_store()     # PostgreSQL history store
```

## Key Files
- `src/taskmeagents/activities/types.py` — ActivityInput, ActivityResult, PersistInput
- `src/taskmeagents/activities/conversation.py` — LLM activities
- `src/taskmeagents/activities/persistence.py` — PersistMessages
- `src/taskmeagents/activities/mcp_tools.py` — ExecuteServerTool
- `src/taskmeagents/temporal_/worker.py` — activity registration

## Error Handling in Activities
```python
# LLM provider failures — propagate to workflow
async for event in agent.provider.generate(request):
    if isinstance(event, ErrorEvent):
        logger.error("llm.error", error=str(event.error))
        raise event.error  # → workflow catches in _handle_fatal_error

# Empty LLM response (no messages, no error)
# Returns ActivityResult(messages=[]) → no assistant message streamed
# Always log a warning for debugging

# Non-retryable errors (bad input, serialization)
from temporalio.exceptions import ApplicationError
raise ApplicationError("message", non_retryable=True)
```
