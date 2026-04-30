# Sentiment-Stream Specification

## 1. Functional Requirements

### Requirement: FR1 — Data Ingestion

The system MUST use PySpark Structured Streaming 3.5.6 to read the CSV dataset in micro-batches triggered every 5 seconds via `DataStreamWriter.trigger(processingTime='5 seconds')`. Each micro-batch MUST deduplicate records using `dropDuplicates("texto")` before prediction.

#### Scenario: Ingestion and Deduplication

- GIVEN the raw CSV `dataset_sentimientos_500.csv` is present
- WHEN Spark Structured Streaming triggers a micro-batch
- THEN duplicate texts are removed and only unique records proceed to prediction
- AND predictions are written to MongoDB via `foreachBatch`

### Requirement: FR2 — Processing Pipeline

The system MUST train a PySpark MLlib pipeline consisting of: `Tokenizer` → `StopWordsRemover` → `HashingTF(numFeatures=500)` → `IDF` → `NaiveBayes(smoothing=1.0, modelType="multinomial")`. The trained `PipelineModel` MUST be persisted to a shared Docker volume using `PipelineModel.save()` (PySpark 3.5.6 API).

#### Scenario: Model Training and Persistence

- GIVEN the deduplicated dataset (~30 unique samples)
- WHEN the training job executes
- THEN the full PipelineModel is saved to the shared volume
- AND training metrics are stored in the `model_metrics` collection

### Requirement: FR3 — Prediction Persistence

The system MUST store every prediction in MongoDB with the exact fields: `original_text` (string), `prediction` (string: positivo|negativo|neutral), `confidence` (double), `timestamp` (ISO8601), and `model_version` (string).

#### Scenario: Streaming Prediction Storage

- GIVEN a deduplicated text is processed by the saved PipelineModel
- WHEN the prediction is generated
- THEN a document containing all five required fields is inserted into MongoDB

### Requirement: FR4 — API Endpoints

The system MUST expose three FastAPI endpoints:

- `GET /sentiments` — paginated list with query params `limit`, `offset`, `sentiment`, `date_from`, `date_to`
- `GET /stats` — sentiment distribution, average confidence, total count, and time-series aggregation
- `POST /predict` — accepts JSON `{"text": "string"}`, returns `{"prediction": "...", "confidence": float, "timestamp": "..."}`, and persists the result to MongoDB

#### Scenario: On-Demand Prediction

- GIVEN the FastAPI service is running with the model loaded via `lifespan` (FastAPI v0.115+)
- WHEN a client sends `POST /predict` with valid JSON
- THEN the response contains `prediction`, `confidence`, and `timestamp`
- AND the record is persisted to MongoDB via Motor async driver

#### Scenario: Paginated Query

- GIVEN 50 predictions exist in MongoDB
- WHEN `GET /sentiments?limit=10&offset=0&sentiment=neutral` is called
- THEN exactly 10 neutral predictions are returned with pagination metadata

### Requirement: FR5 — Dashboard

The system MUST serve a vanilla HTML/CSS/JS dashboard using Chart.js with five minimum visualizations: (1) doughnut chart for sentiment distribution, (2) horizontal bar chart for average confidence by sentiment, (3) line chart for prediction volume over time, (4) radar chart for model metrics (accuracy, precision, recall by class), and (5) a paginated, searchable table of latest predictions. The dashboard MUST auto-refresh every 10 seconds via `fetch()` polling.

#### Scenario: Dashboard Load and Refresh

- GIVEN the dashboard is loaded in a browser
- WHEN the page renders and 10 seconds elapse
- THEN all five Chart.js visualizations display current data
- AND the predictions table updates without a full page reload

## 2. Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR1 | All services MUST be containerized; `docker compose up` MUST start the entire stack. |
| NFR2 | MongoDB MUST expose a `healthcheck` (test: `echo 'db.runCommand({ping:1})' | mongosh ...`); FastAPI service MUST use `depends_on` with `condition: service_healthy` to ensure startup order. |
| NFR3 | FastAPI MUST load the ML model inside an `asynccontextmanager` `lifespan` (FastAPI v0.115+) and MUST handle concurrent requests without blocking the event loop. |
| NFR4 | Jenkins MUST use Declarative Pipeline syntax with stages: Checkout → Build → Test → Lint → Deploy, and MUST use `skipStagesAfterUnstable()` to gate deployment. |
| NFR5 | Dashboard MUST be responsive (mobile-ready) and visually professional. |

## 3. Data Requirements

| Collection | Fields | Indexes |
|---|---|---|
| `predictions` | `original_text` (string), `prediction` (string), `confidence` (double), `timestamp` (datetime), `model_version` (string) | `timestamp` (descending), `prediction` (ascending), `confidence` (descending) |
| `model_metrics` | `accuracy` (double), `precision` (object per class), `recall` (object per class), `f1_score` (double), `trained_at` (datetime), `model_version` (string) | `model_version` (unique) |

## 4. API Specification

| Endpoint | Method | Query / Body | Response 200/201 | Error Codes |
|---|---|---|---|---|
| `/sentiments` | GET | `?limit=20&offset=0&sentiment=positivo&date_from=2026-01-01&date_to=2026-12-31` | `{ "items": [...], "total": 0, "limit": 20, "offset": 0 }` | 422 (validation), 500 |
| `/stats` | GET | `?period=day` (optional aggregation bucket) | `{ "distribution": {"positivo": 10, ...}, "avg_confidence": 0.82, "total": 30, "timeseries": [...] }` | 500 |
| `/predict` | POST | `{ "text": "string" }` | `{ "prediction": "positivo", "confidence": 0.92, "timestamp": "2026-04-30T12:00:00Z" }` | 422 (validation), 500 |

**Common Error Response** (`422`, `500`):
```json
{ "detail": "Human-readable error message" }
```

## 5. Scenarios

### Scenario: End-to-End Ingestion

- GIVEN the raw CSV contains 500 rows (94% duplicates)
- WHEN Spark Structured Streaming runs for 60 seconds
- THEN MongoDB `predictions` collection contains at most 30 deduplicated documents

### Scenario: Real-Time Prediction via API

- GIVEN the trained model is loaded in FastAPI lifespan
- WHEN a client POSTs `"I love this product"` to `/predict`
- THEN the response returns `prediction: "positivo"` with `confidence > 0.0`
- AND a corresponding document exists in MongoDB within 1 second

### Scenario: Filtered API Query

- GIVEN 50 predictions with mixed sentiments exist in MongoDB
- WHEN `GET /sentiments?sentiment=negativo&limit=5` is requested
- THEN exactly 5 documents with `prediction: "negativo"` are returned
- AND the response includes `total` count for the filter

### Scenario: Dashboard Visualization

- GIVEN the dashboard is open in a browser
- WHEN the page loads and completes the first `fetch()` to `/stats`
- THEN Chart.js renders all five required visualizations without console errors
- AND after 10 seconds the charts update with refreshed data

### Scenario: CI/CD Pipeline Success

- GIVEN a commit is pushed to the repository
- WHEN the Jenkins Declarative Pipeline executes
- THEN all stages (Checkout, Build, Test, Lint, Deploy) complete successfully
- AND the application is running via `docker compose up` on the Jenkins agent

## 6. Success Criteria / Acceptance Criteria

| Requirement | Acceptance Criteria |
|---|---|
| FR1 | Micro-batch triggers every 5s ±1s; deduplication removes ≥90% duplicates. |
| FR2 | Pipeline trains and `PipelineModel.save()` writes to shared volume; model loads successfully in FastAPI. |
| FR3 | 100% of inserted prediction documents contain all five required fields with valid types. |
| FR4 | `/predict` p95 latency <500ms; `/sentiments` and `/stats` return valid JSON; OpenAPI docs auto-generated at `/docs`. |
| FR5 | All 5 visualizations render; auto-refresh fires every 10s ±1s; responsive on viewport ≥320px. |
| NFR1 | `docker compose up -d` exits 0 and all services reach healthy state within 60s. |
| NFR2 | FastAPI container restarts ≤1 time before MongoDB healthcheck passes. |
| NFR3 | FastAPI handles 10 concurrent `/predict` requests without 500 errors. |
| NFR4 | Jenkins pipeline completes all 5 stages with green status; deployment step runs only if Test+Lint pass. |
| NFR5 | Dashboard passes manual visual inspection on desktop and mobile viewport. |
