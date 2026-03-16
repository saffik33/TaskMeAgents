# TaskMeAgents

AI agents infrastructure for [TaskMe](https://taskme-app.com/).

## Stack
- Python 3.12+ / FastAPI / Temporal / PostgreSQL
- LLM: Anthropic (Claude) + OpenAI (GPT)
- MCP (Model Context Protocol) for tool integration
- Database: `TaskMeAgents` DB, `taskme_agents` schema (port 5433 local)
- Temporal: self-hosted (localhost:7233, UI at localhost:8233)

## Project Layout
```
src/taskmeagents/          Server (FastAPI + Temporal worker)
  models/                  SQLAlchemy ORM (6 tables)
  api/                     FastAPI routers (WebSocket + REST)
  workflow/                Temporal workflows (CompanionWorkflow, delegation, cleanup)
  activities/              Temporal activities (LLM calls, persistence, MCP tools)
  llm/                     Provider abstraction (Anthropic, OpenAI)
  mcp/                     MCP registry, converters, passthrough
  services/                Business logic (agent factory, stream handler)
  history/                 PostgreSQL store + Railway volume attachments
cli/                       CLI client (typer + httpx + websockets)
tests/                     pytest (unit/integration/mock/workflow/e2e)
openspec/                  OpenSpec planning artifacts
```

## Commands
```bash
# Run tests (no Temporal needed)
pytest tests/ -m "not temporal" -v

# Run with coverage
pytest tests/ -m "not temporal" --cov=taskmeagents

# Database migrations
alembic upgrade head

# Start server (requires Docker services running)
docker compose up -d
python -m taskmeagents.main

# Seed test agent
curl -X POST http://localhost:8000/api/agents -H "Content-Type: application/json" -H "X-API-Key: dev-test-key-123" -d @examples/sample-agent.json

# Chat
taskme-cli chat interactive test-assistant --api-key dev-test-key-123
```

## Critical Rules

### Temporal Workflow Determinism
- Use `workflow.uuid4()` — NEVER `uuid.uuid4()` in workflow code
- Use `workflow.now()` — NEVER `datetime.now()` in workflow code
- All imports in workflow files MUST be inside `workflow.unsafe.imports_passed_through()`
- Update handlers MUST call `await self._wait_for_state()` before accessing `self._state`
- No `__import__()`, `random`, or any non-deterministic calls in workflow code

### Activity Design
- Activities are READ-ONLY — they never write to PostgreSQL
- `PersistMessages` is the ONLY activity that writes to the database
- All LLM activities: load history → merge pending → call LLM → return delta
- Tool_use messages are deferred to `pending_tool_ids` (not persisted immediately)
- Tool_use must immediately precede tool_result (Anthropic API requirement)

### Database
- All tables in `taskme_agents` schema (not `public`)
- Message IDs are deterministic: `"{session_id}-{sequence}"`
- Idempotent writes via `INSERT ON CONFLICT DO NOTHING`
- Keyset pagination for session listing (cursor = last_activity_at ISO)

### WebSocket Protocol
- Auth via `?api_key=` query param (validated BEFORE `ws.accept()`)
- Two-phase streaming: Phase 1a (context) → Phase 1b (actions) → Phase 2 (auto-approve recursion)
- All REST endpoints require `X-API-Key` header (except `/health`)

## Documentation Checklist (after changes)
- [ ] Update README.md if API endpoints or WebSocket protocol changes
- [ ] Update examples/sample-agent.json if agent schema changes
- [ ] Create alembic migration if models change
- [ ] Update .env.example if new env vars added
- [ ] Run `pytest tests/ -m "not temporal" -v` — all tests must pass

## Planning Requirements
Before implementing non-trivial changes:
1. Ask 5-10 targeted design questions
2. Consider: data model impact, API contract changes, Temporal workflow determinism
3. Check existing patterns in the codebase before creating new abstractions
4. Verify test coverage plan for new code
