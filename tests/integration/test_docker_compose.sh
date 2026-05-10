#!/usr/bin/env bash
# =============================================================================
# test_docker_compose.sh — Integration test for the Sentiment Stream stack
# =============================================================================
# This script orchestrates the test profile defined in
# infra/docker-compose.test.yml, waits for services to be healthy, exercises
# the API, and cleans up afterwards.
#
# Usage:
#   bash tests/integration/test_docker_compose.sh
# =============================================================================

set -euo pipefail

COMPOSE_FILE="infra/docker-compose.test.yml"
API_URL="http://localhost:8001"
MONGO_CONTAINER="sentiment-mongodb-test"

# Colors for readability
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

info() { echo -e "${GREEN}[INFO]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

cleanup() {
    info "Cleaning up test stack..."
    docker compose -f "$COMPOSE_FILE" down -v --remove-orphans || true
}

trap cleanup EXIT

# ---------------------------------------------------------------------------
# Step 1: Start services
# ---------------------------------------------------------------------------
info "Starting test stack with $COMPOSE_FILE"
docker compose -f "$COMPOSE_FILE" up -d

# ---------------------------------------------------------------------------
# Step 2: Wait for API to be ready
# ---------------------------------------------------------------------------
info "Waiting for API to become healthy (max 60s)..."
for i in {1..30}; do
    if curl -sf "$API_URL/health" >/dev/null 2>&1; then
        info "API is healthy"
        break
    fi
    if [ "$i" -eq 30 ]; then
        error "API did not become healthy in time"
        docker compose -f "$COMPOSE_FILE" logs api-test --tail=50
        exit 1
    fi
    sleep 2
done

# ---------------------------------------------------------------------------
# Step 3: Health endpoint
# ---------------------------------------------------------------------------
info "Testing GET /health"
HEALTH=$(curl -sf "$API_URL/health")
if echo "$HEALTH" | grep -q '"status":"ok"'; then
    info "  ✓ Health check passed"
else
    error "  ✗ Health check failed: $HEALTH"
    exit 1
fi

# ---------------------------------------------------------------------------
# Step 4: POST /predict
# ---------------------------------------------------------------------------
info "Testing POST /predict"
PREDICT_RESP=$(curl -s -X POST "$API_URL/predict" \
    -H "Content-Type: application/json" \
    -d '{"text":"This is an integration test"}') || true

if echo "$PREDICT_RESP" | grep -q '"prediction"'; then
    info "  ✓ Prediction received"
    PREDICTION_OK=true
elif echo "$PREDICT_RESP" | grep -q "503\|no disponible\|not available"; then
    warn "  ⚠ Predict returned 503 (model not trained) — acceptable for first run"
    PREDICTION_OK=false
else
    error "  ✗ Prediction failed: $PREDICT_RESP"
    exit 1
fi

# ---------------------------------------------------------------------------
# Step 5: GET /sentiments
# ---------------------------------------------------------------------------
info "Testing GET /sentiments"
SENTIMENTS_RESP=$(curl -sf "$API_URL/sentiments?limit=5")

if echo "$SENTIMENTS_RESP" | grep -q '"items"'; then
    info "  ✓ Sentiments list received"
else
    error "  ✗ Sentiments list failed: $SENTIMENTS_RESP"
    exit 1
fi

# ---------------------------------------------------------------------------
# Step 6: GET /stats
# ---------------------------------------------------------------------------
info "Testing GET /stats"
STATS_RESP=$(curl -sf "$API_URL/stats")

if echo "$STATS_RESP" | grep -q '"total"'; then
    info "  ✓ Stats received"
else
    error "  ✗ Stats failed: $STATS_RESP"
    exit 1
fi

# ---------------------------------------------------------------------------
# Step 7: GET /model-metrics
# ---------------------------------------------------------------------------
info "Testing GET /model-metrics"
METRICS_RESP=$(curl -sf "$API_URL/model-metrics" || true)

if [ -n "$METRICS_RESP" ] && echo "$METRICS_RESP" | grep -q '"metrics"'; then
    info "  ✓ Model metrics received"
else
    warn "  ⚠ Model metrics not found (training may not have run yet) — acceptable for first run"
fi

# ---------------------------------------------------------------------------
# Step 8: Verify data in MongoDB
# ---------------------------------------------------------------------------
info "Verifying predictions in MongoDB"
MONGO_COUNT=$(docker exec "$MONGO_CONTAINER" mongosh --quiet --eval \
    "db.getSiblingDB('sentiment_stream_test').predictions.countDocuments({})") || true

if [ "$MONGO_COUNT" -ge 1 ]; then
    info "  ✓ Found $MONGO_COUNT prediction(s) in MongoDB"
elif [ "${PREDICTION_OK:-false}" = "true" ]; then
    error "  ✗ No predictions found in MongoDB (predict succeeded but data missing)"
    exit 1
else
    warn "  ⚠ No predictions in MongoDB — model was not trained, skipping"
fi

info "All integration tests passed!"
