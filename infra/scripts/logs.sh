#!/usr/bin/env bash
# logs.sh — Tail logs for all services

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${SCRIPT_DIR}/../docker-compose.yml"

echo "📜 Tailing logs (Ctrl+C to exit)..."
docker compose -f "${COMPOSE_FILE}" logs -f --tail=100
