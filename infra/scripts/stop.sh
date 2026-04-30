#!/usr/bin/env bash
# stop.sh — Stop the Sentiment Stream stack

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${SCRIPT_DIR}/../docker-compose.yml"

echo "🛑 Stopping Sentiment Stream stack..."
docker compose -f "${COMPOSE_FILE}" down

echo "✅ Stack stopped."
