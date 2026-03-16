---
description: Use when creating, configuring, or modifying AI agents, sub-agent delegation, agent tools, the agent factory, or the return_to_parent mechanism in TaskMeAgents.
---

# Agent Configuration — TaskMeAgents

## Agent Schema (PostgreSQL)
```sql
CREATE TABLE taskme_agents.agents (
    agent_id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(255),
    system_prompt TEXT,
    model VARCHAR(255),          -- must exist in llm/models.py REGISTRY
    max_tokens INTEGER,
    temperature REAL,
    client_tools JSONB,          -- tool definitions for client-side execution
    mcp_server_ids TEXT[],       -- MCP server IDs for server-side tools
    sub_agents TEXT[],           -- sub-agent IDs for delegation
    thinking JSONB,              -- {"mode": "disabled|manual|adaptive"}
    observation_masking JSONB,   -- {"enabled": true, "recent_window_turns": 3}
    tool JSONB,                  -- this agent's contract as a sub-agent
    version INTEGER
);
```

## Sub-Agent Delegation
- Sub-agent tools are prefixed with `_`: tool name = `_<sub_agent_id>`
- When a sub-agent is created, `return_to_parent_agent` tool is auto-injected
- Max delegation depth: 5 levels
- FIFO queue: if multiple agent tools requested, they execute sequentially

## Agent Factory
```python
from taskmeagents.services.agent_factory import get_agent_factory

factory = get_agent_factory()
agent = await factory.get_agent("agent-id")          # cached
agent = await factory.get_agent("agent-id", is_sub_agent=True)  # different cache key
factory.invalidate("agent-id")                        # clear on config update
```

## AgentInstance
```python
@dataclass
class AgentInstance:
    config: dict          # raw agent config from DB
    provider: Provider    # LLM provider (Anthropic/OpenAI)
    all_tools: list[Tool] # client + server + agent tools combined
    server_name_to_id: dict[str, str]  # MCP server name → ID mapping
```

## Creating an Agent (API)
```bash
curl -X POST http://localhost:8000/api/agents \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-test-key-123" \
  -d '{
    "agent_id": "my-agent",
    "name": "My Agent",
    "system_prompt": "You are helpful.",
    "model": "gpt-5.2",
    "max_tokens": 4096,
    "temperature": 0.7,
    "sub_agents": ["research-agent"],
    "mcp_server_ids": ["uuid-of-mcp-server"]
  }'
```

## Agent Update Flow
1. PUT `/api/agents/{id}` updates config
2. Old version archived to `agent_versions` table
3. `factory.invalidate(agent_id)` clears cache
4. Next request re-creates agent with new config

## Key Files
- `src/taskmeagents/models/agent.py` — Agent + AgentVersion ORM
- `src/taskmeagents/services/agent_factory.py` — AgentFactory singleton
- `src/taskmeagents/api/agents.py` — CRUD endpoints
- `src/taskmeagents/schemas/agent.py` — Pydantic schemas
- `examples/sample-agent.json` — example config
