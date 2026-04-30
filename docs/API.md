# Sentiment-Stream — API Documentation

> Complete reference for all REST endpoints exposed by the FastAPI backend.

**Base URL:** `http://localhost:8000`  
**OpenAPI (Swagger UI):** `http://localhost:8000/docs`  
**OpenAPI (ReDoc):** `http://localhost:8000/redoc`

---

## Common Response Codes

| Code | Meaning | Description |
|---|---|---|
| `200` | OK | Request succeeded |
| `201` | Created | Resource created successfully |
| `422` | Unprocessable Entity | Validation error (Pydantic) |
| `500` | Internal Server Error | Unexpected server error |
| `503` | Service Unavailable | Model not loaded or dependency unavailable |

**Error Response Body:**
```json
{
  "detail": "Human-readable error message"
}
```

---

## Endpoints

### 1. POST /predict

Predict the sentiment of a given text and persist the result to MongoDB.

**Request:**
```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"text": "I love this product"}'
```

**Body Schema:**
```json
{
  "text": "string (min_length=1, max_length=1000)"
}
```

**Success Response (200):**
```json
{
  "prediction": "positivo",
  "confidence": 0.92,
  "timestamp": "2026-04-30T12:00:00Z"
}
```

**Error Responses:**
- `422` — Text empty or exceeds 1000 characters
- `503` — Model not loaded (run training first)

---

### 2. GET /sentiments

Retrieve paginated predictions with optional filtering.

**Request:**
```bash
curl "http://localhost:8000/sentiments?limit=10&offset=0&sentiment=positivo"
```

**Query Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `limit` | integer | `50` | Page size (1–1000) |
| `offset` | integer | `0` | Items to skip |
| `sentiment` | string | — | Filter by `"positivo"`, `"negativo"`, or `"neutral"` |
| `date_from` | ISO8601 datetime | — | Minimum timestamp (inclusive) |
| `date_to` | ISO8601 datetime | — | Maximum timestamp (inclusive) |

**Success Response (200):**
```json
{
  "items": [
    {
      "original_text": "I love this product",
      "prediction": "positivo",
      "confidence": 0.92,
      "timestamp": "2026-04-30T12:00:00Z",
      "model_version": "v1_20260430_120000"
    }
  ],
  "total": 42,
  "limit": 10,
  "offset": 0
}
```

**Error Responses:**
- `422` — Invalid query parameter (e.g., `limit=0`)
- `500` — MongoDB query failure

---

### 3. GET /stats

Retrieve aggregated statistics: sentiment distribution, average confidence, total count, and time-series buckets.

**Request:**
```bash
curl "http://localhost:8000/stats?period=hour"
```

**Query Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `period` | string | `"day"` | Time bucket: `"hour"` or `"day"` |

**Success Response (200):**
```json
{
  "distribution": {
    "positivo": 15,
    "negativo": 8,
    "neutral": 2
  },
  "avg_confidence": 0.82,
  "total": 25,
  "timeseries": [
    {
      "timestamp": "2026-04-30T12:00:00",
      "count": 5
    },
    {
      "timestamp": "2026-04-30T13:00:00",
      "count": 3
    }
  ]
}
```

**Error Responses:**
- `422` — Invalid `period` value
- `500` — Aggregation pipeline failure

---

### 4. GET /model-metrics

Retrieve the latest model evaluation metrics: per-class precision, recall, and F1-score.

**Request:**
```bash
curl "http://localhost:8000/model-metrics"
```

**Success Response (200):**
```json
{
  "metrics": {
    "positivo": {
      "precision": 0.90,
      "recall": 0.88,
      "f1": 0.82
    },
    "negativo": {
      "precision": 0.80,
      "recall": 0.78,
      "f1": 0.82
    },
    "neutral": {
      "precision": 0.70,
      "recall": 0.68,
      "f1": 0.82
    }
  },
  "model_version": "v1_20260430_120000",
  "trained_at": "2026-04-30T12:00:00Z"
}
```

**Error Responses:**
- `404` — No metrics found (training has not been executed yet)

---

### 5. GET /health

Simple health check for load balancers and orchestrators.

**Request:**
```bash
curl "http://localhost:8000/health"
```

**Success Response (200):**
```json
{
  "status": "ok"
}
```

---

## Data Types

### SentimentPredictionRequest

| Field | Type | Constraints | Description |
|---|---|---|---|
| `text` | string | min_length=1, max_length=1000 | Text to classify |

### SentimentPredictionResponse

| Field | Type | Description |
|---|---|---|
| `prediction` | string | `"positivo"`, `"negativo"`, or `"neutral"` |
| `confidence` | float | Probability of the predicted class (0.0–1.0) |
| `timestamp` | datetime | ISO8601 UTC timestamp |

### SentimentsResponse

| Field | Type | Description |
|---|---|---|
| `items` | list[dict] | Array of prediction documents |
| `total` | integer | Total matching documents |
| `limit` | integer | Requested page size |
| `offset` | integer | Requested skip value |

### StatsResponse

| Field | Type | Description |
|---|---|---|
| `distribution` | dict[string, int] | Count per sentiment class |
| `avg_confidence` | float | Mean confidence across all predictions |
| `total` | integer | Total number of predictions |
| `timeseries` | list[dict] | `{timestamp, count}` buckets |

### ModelMetricsResponse

| Field | Type | Description |
|---|---|---|
| `metrics` | dict[string, dict] | Per-class `{precision, recall, f1}` |
| `model_version` | string | Version string from training |
| `trained_at` | datetime | ISO8601 UTC timestamp of training |

---

## Example Script

```bash
#!/usr/bin/env bash
# Quick API smoke test

BASE="http://localhost:8000"

echo "Health:"
curl -s "$BASE/health" | jq .

echo -e "\nPredict:"
curl -s -X POST "$BASE/predict" \
  -H "Content-Type: application/json" \
  -d '{"text":"Amazing service"}' | jq .

echo -e "\nSentiments:"
curl -s "$BASE/sentiments?limit=3" | jq .

echo -e "\nStats:"
curl -s "$BASE/stats?period=hour" | jq .

echo -e "\nModel Metrics:"
curl -s "$BASE/model-metrics" | jq .
```
