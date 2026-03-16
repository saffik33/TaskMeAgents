---
description: Use when deploying TaskMeAgents, configuring Docker, setting up Railway services, managing environment variables, or troubleshooting infrastructure.
---

# Deployment & Railway — TaskMeAgents

## Local Development (3 services via Docker Compose)
```
docker compose up -d          # Start PostgreSQL + Temporal
alembic upgrade head          # Run migrations
python -m taskmeagents.main   # Start server
```

## Service Layout
| Service | Port | Image |
|---------|------|-------|
| PostgreSQL | **5433** (host) → 5432 (container) | postgres:16 |
| Temporal | 7233 (gRPC) + 8233 (UI) | temporalio/auto-setup:latest |
| TaskMeAgents | 8000 | Python 3.12-slim |

Port 5433 used to avoid conflict with local PostgreSQL on 5432.

## Docker Compose Key Settings
```yaml
postgres:
  POSTGRES_HOST_AUTH_METHOD: trust   # Allows passwordless TCP connections
temporal:
  DB: postgres12                      # NOT "postgresql" — Temporal-specific driver name
```

## Database Setup
- DB name: `TaskMeAgents` (case-sensitive)
- Schema: `taskme_agents` (created by init-db.sql + alembic)
- Init script: `docker/init-db.sql` runs on first PG startup

## Application Startup Order
```python
# In main.py lifespan:
1. init_db()              # PostgreSQL connectivity + create schema
2. init_history_store()   # PostgresHistoryStore singleton
3. init_mcp_registry()    # MCPRegistry singleton
4. init_agent_factory()   # AgentFactory singleton
5. connect_temporal()     # Temporal client
6. _seed_admin_key()      # Bootstrap API key (if ADMIN_API_KEY set)
7. run_worker()           # Background Temporal worker task
```

## Required Environment Variables
```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/TaskMeAgents
DATABASE_SCHEMA=taskme_agents
TEMPORAL_ADDRESS=localhost:7233
ANTHROPIC_API_KEY=...   (or OPENAI_API_KEY)
ADMIN_API_KEY=dev-test-key-123
```

## Railway Production Setup
- PostgreSQL: managed Railway service (2 databases: TaskMeAgents + temporal)
- Temporal: Docker service `temporalio/auto-setup`, internal networking
- TaskMeAgents: Docker service, persistent volume at `/data`
- CORS: set `CORS_ORIGINS=["https://taskme-app.com"]`

## Reset Everything (nuclear option)
```bash
docker compose down -v     # Remove containers + volumes
docker compose up -d       # Fresh start
alembic upgrade head       # Re-run migrations
```

## Key Files
- `docker-compose.yml` — service definitions
- `docker/init-db.sql` — DB + schema init
- `.env` / `.env.example` — environment config
- `Dockerfile` — production image
- `src/taskmeagents/main.py` — startup lifecycle
