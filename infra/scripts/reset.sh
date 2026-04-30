#!/usr/bin/env bash
# reset.sh — Full reset: stop, remove volumes, and restart

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${SCRIPT_DIR}/../docker-compose.yml"

echo "⚠️  This will REMOVE all data volumes and restart the stack."
read -r -p "Are you sure? [y/N] " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

echo "🧹 Stopping and removing volumes..."
docker compose -f "${COMPOSE_FILE}" down -v

echo "🚀 Restarting stack..."
docker compose -f "${COMPOSE_FILE}" up -d --build

echo "✅ Reset complete."
