# TaskMe Agents

AI agents infrastructure for [TaskMe](https://taskme-app.com/). Provides conversational AI with tool execution, sub-agent delegation, and MCP (Model Context Protocol) integration.

## Architecture

```
Client (taskme-app.com)
  |
  WebSocket /ws/chat
  |
FastAPI (port 8000)
  |
  +-- Temporal Workflow (CompanionWorkflow)
  |     +-- LLM Activity (Anthropic / OpenAI)
  |     +-- MCP Tool Execution
  |     +-- Sub-Agent Delegation (child workflows)
  |     +-- Message Persistence (PostgreSQL)
  |
  +-- REST API
        +-- Agent CRUD (/api/agents)
        +-- MCP Server CRUD (/api/mcp-servers)
        +-- Session History (/api/sessions)
        +-- Models (/api/models)
```

**Stack:** Python 3.12, FastAPI, Temporal, PostgreSQL, Anthropic SDK, OpenAI SDK, MCP

## Local Development

### Prerequisites

- Python 3.12+
- PostgreSQL 15+
- Temporal server ([dev server](https://docs.temporal.io/cli#start-dev-server))

### Setup

```bash
# Clone and install
cd TaskMeagents
pip install -e ".[dev]"

# Create database
createdb taskme

# Run migrations
alembic upgrade head

# Start Temporal dev server (separate terminal)
temporal server start-dev

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Run the server
python -m taskmeagents.main
```

### CLI

```bash
# Set API key
export TASKME_API_KEY=your_key

# Chat with an agent
taskme-cli chat interactive my-agent-id

# Send a single message
taskme-cli chat send my-agent-id "Hello"

# Manage agents
taskme-cli agent list
taskme-cli agent create agent-config.json
taskme-cli agent models
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | `postgresql+asyncpg://postgres:postgres@localhost:5432/taskme` | PostgreSQL connection |
| `TEMPORAL_ADDRESS` | Yes | `localhost:7233` | Temporal server address |
| `TEMPORAL_NAMESPACE` | No | `default` | Temporal namespace |
| `TEMPORAL_TASK_QUEUE` | No | `taskme-agents` | Temporal task queue |
| `ANTHROPIC_API_KEY` | Yes | | Anthropic API key |
| `OPENAI_API_KEY` | No | | OpenAI API key |
| `ATTACHMENT_BASE_PATH` | No | `/data/attachments` | File attachment storage |
| `MCP_IDLE_TIMEOUT_MINUTES` | No | `10` | MCP connection TTL |
| `ADMIN_API_KEY` | No | | Seed admin API key on first startup |
| `PORT` | No | `8000` | HTTP server port |
| `CORS_ORIGINS` | No | `["https://taskme-app.com"]` | Allowed CORS origins |

## Railway Deployment

Three Railway services required:

### 1. PostgreSQL (managed)

Create a PostgreSQL service in Railway. Create two databases:
- `taskme` — application data
- `temporal` — Temporal persistence

### 2. Temporal Server (Docker)

Deploy from Docker image `temporalio/auto-setup:latest`:

```
DB=postgresql
DB_PORT=5432
POSTGRES_SEEDS=<railway-pg-host>
DBNAME=temporal
POSTGRES_USER=<user>
POSTGRES_PWD=<password>
```

Expose port 7233 (internal) and 8233 (Temporal UI, public).

### 3. TaskMeAgents (this project)

Deploy from this repo. Set environment variables pointing to the Railway PostgreSQL and Temporal services. Mount a persistent volume at `/data`.

```
DATABASE_URL=postgresql+asyncpg://<user>:<pass>@<pg-host>:5432/taskme
TEMPORAL_ADDRESS=<temporal-service>.railway.internal:7233
ANTHROPIC_API_KEY=sk-ant-...
ADMIN_API_KEY=<your-bootstrap-key>
CORS_ORIGINS=["https://taskme-app.com"]
```

### Cleanup Schedule

After deployment, create a Temporal schedule for inactive conversation cleanup:

```bash
temporal schedule create \
  --address <temporal-host>:7233 \
  --schedule-id cleanup-inactive \
  --workflow-type CleanupInactiveConversationsWorkflow \
  --task-queue taskme-agents \
  --input '30' \
  --interval 10m
```

## API Reference

### WebSocket: Chat

```
WS /ws/chat?api_key=...&agent_id=...&session_id=...
```

Client sends JSON messages:
- `{"type": "user_message", "content": "..."}`
- `{"type": "client_tool_result", "tool_use_id": "...", "content": "...", "success": true}`
- `{"type": "server_tool_approval", "tool_use_id": "...", "approved": true}`
- `{"type": "end_conversation", "reason": "..."}`

Server sends JSON messages:
- `{"type": "session_established", "session_id": "..."}`
- `{"type": "assistant_message", "content": "...", "is_final": true}`
- `{"type": "tool_execution_request", "tool_name": "...", "parameters": {...}}`
- `{"type": "tool_approval_request", "tool_name": "...", "parameters": {...}}`
- `{"type": "tool_result", "tool_name": "...", "success": true, "content": "..."}`
- `{"type": "usage", "input_tokens": 100, "output_tokens": 50, "total_cost": 0.003}`
- `{"type": "error", "message": "...", "code": "INTERNAL"}`
- `{"type": "end", "reason": "completed"}`

### REST: Agents

```
GET    /api/agents                     — list agents
GET    /api/agents/{id}                — get agent
POST   /api/agents                     — create agent
PUT    /api/agents/{id}                — update agent
DELETE /api/agents/{id}                — delete agent
GET    /api/agents/{id}/versions       — version history
POST   /api/agents/{id}/rollback       — rollback to version
```

### REST: MCP Servers

```
GET    /api/mcp-servers                — list servers
POST   /api/mcp-servers                — create server
PUT    /api/mcp-servers/{id}           — update server
DELETE /api/mcp-servers/{id}           — delete server
POST   /api/mcp-servers/{id}/test      — test connection
```

### REST: Sessions & Models

```
GET    /api/sessions                   — list sessions
GET    /api/sessions/{id}/messages     — get messages
GET    /api/sessions/search?q=...      — search messages
GET    /api/models                     — list LLM models
GET    /health                         — health check
```

All REST endpoints require `X-API-Key` header (except `/health`).

## Agent Configuration Example

```json
{
  "agent_id": "my-assistant",
  "name": "My Assistant",
  "system_prompt": "You are a helpful assistant for TaskMe users.",
  "model": "claude-sonnet-4-6",
  "max_tokens": 4096,
  "temperature": 0.7,
  "client_tools": [],
  "mcp_server_ids": [],
  "sub_agents": [],
  "thinking": {"mode": "disabled"},
  "observation_masking": {"enabled": true, "recent_window_turns": 3}
}
```

## License

Proprietary — TaskMe
