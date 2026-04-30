#!/usr/bin/env bash
# start.sh — Start the full Sentiment Stream stack

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${SCRIPT_DIR}/../docker-compose.yml"

echo "🚀 Starting Sentiment Stream stack..."
docker compose -f "${COMPOSE_FILE}" up -d --build

echo ""
echo "⏳ Waiting for services to be healthy..."
sleep 5

# Healthcheck loop
for i in {1..30}; do
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null | grep -q "200"; then
        echo ""
        echo "✅ Stack is up and running!"
        echo "   Dashboard: http://localhost"
        echo "   API Docs:  http://localhost:8000/docs"
        echo "   Spark UI:  http://localhost:8080"
        exit 0
    fi
    echo -n "."
    sleep 2
done

echo ""
echo "⚠️  API healthcheck timed out. Check logs with: ./infra/scripts/logs.sh"
exit 1
