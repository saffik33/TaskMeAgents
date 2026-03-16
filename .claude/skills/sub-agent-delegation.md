---
description: Use when implementing sub-agent delegation, child workflows, parent-child workflow communication, the return_to_parent mechanism, agent tool queueing, or crash recovery in TaskMeAgents.
---

# Sub-Agent Delegation — TaskMeAgents

## How Delegation Works
1. Parent LLM calls agent tool (name = `_<sub_agent_id>`)
2. Stream handler detects agent tool → sends `ProcessAgentTool` update
3. Workflow creates child `CompanionWorkflow` with `delegation_depth + 1`
4. Initial message forwarded to child via `ForwardToChildWorkflow` activity
5. Child processes, eventually calls `return_to_parent_agent` tool
6. Parent receives result, continues conversation

## Tool Injection
```python
# Sub-agent tools get _ prefix (agent factory does this automatically)
Tool(name="_research-agent", description="Delegate research", tool_type=ToolType.AGENT)

# Sub-agents automatically get return_to_parent tool
Tool(name="return_to_parent_agent", input_schema={"result": str, "data": object})
```

## FIFO Queue
If LLM requests multiple agent tools simultaneously:
- First agent → starts immediately (active child)
- Subsequent agents → queued in `state.queued_agent_tools`
- When active child returns → next in queue starts
- Queue processed in order (FIFO)

## Depth Limit
`MAX_DELEGATION_DEPTH = 5`. At depth limit:
- Agent tool rejected with error ToolResultMessage
- Parent LLM receives: "Cannot delegate: maximum delegation depth (5) reached"

## Crash Recovery

### Synchronous (during active RPC)
```
Parent forwards message to child → child crashes → ForwardToChildWorkflow fails
→ Parent detects immediately → clears delegation state → synthesizes failure result
→ Calls parent LLM for recovery response → "The sub-agent encountered an error..."
```

### Asynchronous (between messages)
Next user message calls `forward_to_child_if_active()` → detects dead child
→ Same recovery path as synchronous

## Child Message Handling
- `clearIsFinalOnChildMessages()`: Forces `is_final=False` on ALL child assistant messages
- Only the root parent's final message has `is_final=True`
- Child token usage accumulated into parent's `CumulativeUsage`

## State Fields
```python
active_child_workflow_id: str    # ID of running child (empty if none)
active_agent_tool_use_id: str    # ToolUseID that spawned the active child
queued_agent_tools: list         # FIFO queue of pending delegations
```

## Key Files
- `src/taskmeagents/workflow/delegation.py` — all delegation logic
- `src/taskmeagents/workflow/companion_workflow.py` — `process_agent_tool` update
- `src/taskmeagents/services/agent_factory.py` — tool injection
- `src/taskmeagents/activities/delegation.py` — ForwardToChildWorkflow activity
