#!/usr/bin/env bash
set -euo pipefail

echo "=== TaskMeAgents Setup ==="

# Install dependencies
echo "Installing dependencies..."
pip install -e ".[dev]" --quiet

# Wait for PostgreSQL
echo "Waiting for PostgreSQL..."
for i in $(seq 1 30); do
    if pg_isready -h localhost -p 5432 -U postgres >/dev/null 2>&1; then
        echo "PostgreSQL is ready."
        break
    fi
    if [ $i -eq 30 ]; then
        echo "ERROR: PostgreSQL not ready after 30s. Is 'docker compose up' running?"
        exit 1
    fi
    sleep 1
done

# Create schema (in case init-db.sql didn't run)
echo "Ensuring database and schema exist..."
PGPASSWORD=postgres psql -h localhost -U postgres -c 'SELECT 1' -d TaskMeAgents >/dev/null 2>&1 || \
    PGPASSWORD=postgres psql -h localhost -U postgres -c 'CREATE DATABASE "TaskMeAgents"' 2>/dev/null || true
PGPASSWORD=postgres psql -h localhost -U postgres -d TaskMeAgents -c 'CREATE SCHEMA IF NOT EXISTS taskme_agents' 2>/dev/null || true

# Run migrations
echo "Running database migrations..."
alembic upgrade head

echo ""
echo "=== Setup complete! ==="
echo ""
echo "Next steps:"
echo "  1. Edit .env and set your ANTHROPIC_API_KEY"
echo "  2. Start the server:  python -m taskmeagents.main"
echo "  3. Seed test agent:   ./scripts/seed.sh"
echo "  4. Chat:              taskme-cli chat interactive test-assistant --api-key dev-test-key-123"
