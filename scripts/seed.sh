#!/usr/bin/env bash
set -euo pipefail

API_KEY="${TASKME_API_KEY:-dev-test-key-123}"
SERVER="${TASKME_SERVER:-http://localhost:8000}"

echo "=== Seeding TaskMeAgents ==="
echo "Server: $SERVER"

# Check server health
echo "Checking server health..."
if ! curl -sf "$SERVER/health" > /dev/null 2>&1; then
    echo "ERROR: Server not reachable at $SERVER. Is it running?"
    exit 1
fi
echo "Server is healthy."

# Create test agent
echo "Creating test agent..."
RESPONSE=$(curl -sf -w "\n%{http_code}" -X POST "$SERVER/api/agents" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d @examples/sample-agent.json 2>&1) || true

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "201" ]; then
    echo "Agent 'test-assistant' created successfully!"
elif [ "$HTTP_CODE" = "409" ]; then
    echo "Agent 'test-assistant' already exists (skipping)."
else
    echo "Response ($HTTP_CODE): $BODY"
fi

echo ""
echo "=== Seed complete! ==="
echo ""
echo "Start chatting:"
echo "  taskme-cli chat interactive test-assistant --api-key $API_KEY --server $SERVER"
echo ""
echo "Or via curl:"
echo "  curl $SERVER/api/agents -H 'X-API-Key: $API_KEY'"
