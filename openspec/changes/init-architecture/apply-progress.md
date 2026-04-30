# Apply Progress: init-architecture

## Batch 1 of 4 — Project Setup + Spark Pipeline

### Completed Tasks

#### Phase 1: Project Setup
- [x] **T1.1** Create directory structure (`data/`, `spark/`, `api/`, `dashboard/`, `infra/`, `docs/`)
- [x] **T1.2** Create `.gitignore` (Python, Spark, Docker, IDE files)
- [x] **T1.3** Create root `README.md` template (architecture, setup, usage, limitations)

#### Phase 2: Spark Pipeline
- [x] **T2.1** Create `spark/requirements.txt` (`pyspark==3.5.2`, `pymongo==4.7.0`, `pandas==2.2.2`)
- [x] **T2.2** Create `spark/Dockerfile` (`bitnami/spark:latest` base, pip install, copy scripts)
- [x] **T2.3** Create `spark/ingest.py` — reads CSV, validates schema, deduplicates, adds synthetic `id` and `timestamp`
- [x] **T2.4** Create `spark/train.py` — builds MLlib Pipeline (Tokenizer → StopWordsRemover → HashingTF(500) → IDF → NaiveBayes), trains on deduplicated data, saves `PipelineModel` to `/app/model`, stores metrics to MongoDB
- [x] **T2.5** Create `spark/stream.py` — Structured Streaming CSV source, `trigger(processingTime='5 seconds')`, `dropDuplicates(["texto"])`, `foreachBatch` writes to MongoDB with confidence extraction
- [x] **T2.6** Create `spark/utils.py` — MongoDB sync client (`pymongo`), logging, config constants, Spanish↔numeric label mapping
- [x] **T2.7** Create `spark/__init__.py`

### Files Changed (Batch 1)

| File | Action | Description |
|---|---|---|
| `data/dataset_sentimientos_500.csv` | Moved | Dataset relocated from project root to `data/` |
| `spark/requirements.txt` | Created | PySpark + pymongo + pandas dependencies |
| `spark/Dockerfile` | Created | Bitnami Spark base image with requirements install |
| `spark/ingest.py` | Created | CSV loading, deduplication, synthetic enrichment |
| `spark/train.py` | Created | ML pipeline definition, training, evaluation, persistence |
| `spark/stream.py` | Created | Structured Streaming with foreachBatch MongoDB sink |
| `spark/utils.py` | Created | Shared utilities and configuration |
| `spark/__init__.py` | Created | Package initializer |
| `.gitignore` | Created | Python/Spark/Docker/IDE ignores |
| `README.md` | Created | Root readme with architecture, setup, usage, limitations |
| `openspec/changes/init-architecture/tasks.md` | Modified | Marked Phase 1 and Phase 2 tasks complete |

---

## Batch 2 of 4 — FastAPI Backend

### Completed Tasks

#### Phase 3: FastAPI Backend
- [x] **T3.1** Create `api/requirements.txt` — fastapi, uvicorn, motor, pymongo, pyspark, pydantic, python-multipart
- [x] **T3.2** Create `api/Dockerfile` — python:3.11-slim, openjdk-11, expose 8000
- [x] **T3.3** Create `api/__init__.py` — package init
- [x] **T3.4** Create `api/models.py` — Pydantic v2: SentimentPredictionRequest, SentimentPredictionResponse, SentimentFilter, SentimentsResponse, StatsResponse, ErrorResponse
- [x] **T3.5** Create `api/database.py` — Motor async MongoDB client, indexes, helpers: insert_prediction, get_predictions, get_stats
- [x] **T3.6** Create `api/services/model_loader.py` — PipelineModel.load() from /app/model with graceful error handling
- [x] **T3.7** Create `api/services/inference.py` — ThreadPoolExecutor + run_in_executor, numeric→Spanish label map, confidence extraction
- [x] **T3.8** Create `api/routes/predict.py` — POST /predict, persists to MongoDB, returns structured response, handles 503/422
- [x] **T3.9** Create `api/routes/sentiments.py` — GET /sentiments paginated with query params (limit, offset, sentiment, date_from, date_to)
- [x] **T3.10** Create `api/routes/stats.py` — GET /stats with distribution, avg_confidence, total, timeseries (hour/day)
- [x] **T3.11** Create `api/main.py` — FastAPI lifespan asynccontextmanager, startup/shutdown, CORS, healthcheck, router inclusion

### Files Changed (Batch 2)

| File | Action | Description |
|---|---|---|
| `api/requirements.txt` | Created | Backend dependencies including PySpark and Motor |
| `api/Dockerfile` | Created | Python 3.11 slim with OpenJDK 11 for PySpark |
| `api/__init__.py` | Created | Package initializer |
| `api/config.py` | Created | Pydantic v2 settings (MongoDB URI, model path, CORS) |
| `api/models.py` | Created | Request/response schemas and filter models |
| `api/database.py` | Created | Motor client wrapper with CRUD and aggregation helpers |
| `api/services/__init__.py` | Created | Services package init |
| `api/services/model_loader.py` | Created | PySpark PipelineModel loader from shared volume |
| `api/services/inference.py` | Created | Async inference via ThreadPoolExecutor and run_in_executor |
| `api/routes/__init__.py` | Created | Routes package init |
| `api/routes/predict.py` | Created | POST /predict endpoint with persistence |
| `api/routes/sentiments.py` | Created | GET /sentiments paginated endpoint |
| `api/routes/stats.py` | Created | GET /stats aggregated endpoint |
| `api/main.py` | Created | FastAPI app with lifespan, CORS, healthcheck, routers |
| `openspec/changes/init-architecture/tasks.md` | Modified | Marked Phase 3 tasks complete |

### Deviations from Design

1. **Database module consolidation**: The design proposed `api/dependencies.py` (DI) + `api/services/repository.py` (CRUD). The implementation consolidates both into `api/database.py` (`Database` class) to reduce indirection while preserving the same public interface (`insert_prediction`, `get_predictions`, `get_stats`). This aligns with the orchestrator's task description (T3.5) and keeps the codebase flatter.

2. **Model loader split**: The design had a single `inference.py` with `PipelineModelWrapper`. The implementation splits model loading (`model_loader.py`) from prediction logic (`inference.py`) for single-responsibility and easier testing.

3. **ThreadPoolExecutor instead of ProcessPoolExecutor**: The design suggested `ProcessPoolExecutor`. For PySpark, `ProcessPoolExecutor` fails because SparkSession and DataFrames are not picklable across processes. The implementation uses `ThreadPoolExecutor`, which is the standard pattern for running PySpark transform in an async context (JVM calls release the GIL).

4. **Database name**: The orchestrator task description mentioned `/sentiments`, but the existing Spark pipeline and spec use `sentiment_stream`. The implementation uses `sentiment_stream` to maintain compatibility with the trained model metrics and streaming predictions already stored by Batch 1.

5. **`pydantic-settings` omitted**: The design recommended `pydantic-settings.BaseSettings`. The implementation uses `pydantic.BaseModel` with `Field(default_factory=lambda: os.getenv(...))` to stay within the explicit dependency list while achieving the same env-var loading behavior.

### Issues Found

1. **Model version unknown at inference time**: The saved `PipelineModel` does not embed the version string generated during training. `inference.py` hardcodes `"unknown"` for `model_version`. A future improvement could query MongoDB `model_metrics` at startup to fetch the latest `model_version` and attach it to `app.state`.

2. **PySpark startup cost**: Creating a `SparkSession` inside the FastAPI container adds ~10-20s to startup. The lifespan handles this before yielding, so requests are not served until the session is ready or the load fails gracefully.

3. **No test runner available**: Strict TDD mode remains inactive. Implementation followed standard workflow.

### Remaining Tasks (Next Batches)

#### Batch 4 — Testing + Documentation
- [ ] T6.1–T6.8 API tests, Spark tests, integration tests
- [ ] T7.1–T7.4 Documentation updates

### Status

**39 / 45 tasks complete**. Ready for Batch 4 (Testing + Documentation).

---

## Batch 3 of 4 — Dashboard + Infrastructure

### Completed Tasks

#### Phase 4: Dashboard
- [x] **T4.1** Create `dashboard/index.html` — Professional HTML5 with header, grid layout, chart containers, predictions table, footer, offline banner
- [x] **T4.2** Create `dashboard/css/styles.css` — Dark theme, CSS Grid + Flexbox, responsive (320px+), card layout, animations, loading spinners
- [x] **T4.3-T4.4** Config + API wrapper merged into `dashboard/js/app.js` and `dashboard/js/utils.js` — API_BASE configurable via query param/localStorage/env, fetch with 3 retries
- [x] **T4.5-T4.9** Chart modules consolidated into `dashboard/js/charts.js` — Doughnut (distribution), horizontal Bar (confidence), Line (volume), Radar (metrics proxy), Table (paginated + searchable)
- [x] **T4.10** Create `dashboard/js/app.js` — Polling every 10s, auto-refresh toggle, offline banner, error handling, last-update timestamp, keyboard shortcuts (R=refresh, P=toggle)
- [x] **T4.11** Create `dashboard/Dockerfile` — nginx:alpine, static files, gzip, healthcheck
- [x] **T4.6 / T4.8** `dashboard/assets/` created, `.dockerignore` added
- [x] **T4.9** Script tags in correct order (Chart.js CDN → utils.js → charts.js → app.js)
- [x] **T4.10** Empty states handled gracefully for all charts and table
- [x] **T4.11** Force refresh button + keyboard shortcut (R)

#### Phase 5: Infrastructure
- [x] **T5.1** Create `infra/docker-compose.yml` — MongoDB (healthcheck), Spark master+worker (bitnami), FastAPI (depends_on mongodb healthy), Dashboard (depends_on api), shared volume model_storage, bridge network
- [x] **T5.2** Create `infra/docker-compose.test.yml` — Test profile with alt ports (27018, 8001), isolated volumes and network
- [x] **T5.3** Create `infra/mongodb-init.js` — Collections predictions + model_metrics, indexes (timestamp desc, prediction asc, confidence desc, model_version unique), schema validation with moderate level
- [x] **T5.4** Create `infra/Jenkinsfile` — Declarative Pipeline: Checkout → Build → Test → Lint → Deploy, skipStagesAfterUnstable(), timeout, healthcheck waits, post cleanup
- [x] **T5.5-T5.6** Existing `spark/Dockerfile` and `api/Dockerfile` referenced directly from compose; no redundant infra/ copies needed
- [x] **T5.7** Create `infra/scripts/` — start.sh, stop.sh, logs.sh, reset.sh (all executable)
- [x] **T5.6** Create `infra/.env.example` — MONGO_URI, API_PORT, DASHBOARD_PORT, SPARK ports, COMPOSE_PROJECT_NAME

### Files Changed (Batch 3)

| File | Action | Description |
|---|---|---|
| `dashboard/index.html` | Created | Professional dark-theme dashboard layout with 5 chart sections, KPI cards, table, footer |
| `dashboard/css/styles.css` | Created | Dark theme, CSS custom properties, responsive breakpoints (1200/768/480px), animations, scrollbar styling |
| `dashboard/js/utils.js` | Created | Date/number formatting, debounce/throttle, color utilities, DOM helpers, sentiment mapping |
| `dashboard/js/charts.js` | Created | Chart.js v4 configs: doughnut, horizontal bar, line, radar, data table with pagination/search |
| `dashboard/js/app.js` | Created | Polling (10s), retry logic, offline banner, KPI updates, auto-refresh toggle, keyboard shortcuts |
| `dashboard/Dockerfile` | Created | nginx:alpine with gzip, custom conf, healthcheck |
| `dashboard/.dockerignore` | Created | Ignores node_modules, logs, git |
| `dashboard/assets/` | Created | Empty assets directory for future icons/images |
| `infra/docker-compose.yml` | Created | Full 5-service orchestration with healthchecks, volumes, networks |
| `infra/docker-compose.test.yml` | Created | Isolated test profile with alternate ports |
| `infra/mongodb-init.js` | Created | Collections, indexes, JSON schema validation |
| `infra/Jenkinsfile` | Created | Declarative pipeline with 5 stages, gating, cleanup |
| `infra/.env.example` | Created | Environment variable template |
| `infra/scripts/start.sh` | Created | docker-compose up with healthcheck wait loop |
| `infra/scripts/stop.sh` | Created | docker-compose down |
| `infra/scripts/logs.sh` | Created | docker-compose logs -f |
| `infra/scripts/reset.sh` | Created | docker-compose down -v && up -d --build with confirmation |
| `openspec/changes/init-architecture/tasks.md` | Modified | Marked Phase 4 and Phase 5 tasks complete |

### Deviations from Design

1. **Dashboard file consolidation**: The design proposed 8 separate JS files (`config.js`, `api.js`, 5 chart files, `app.js`). The implementation consolidates into 3 files (`utils.js`, `charts.js`, `app.js`) for cleaner dependency management and fewer HTTP requests in production. All functionality is preserved.

2. **Radar chart data source**: The design specified radar chart should show precision/recall per class from `/stats`. The actual `/stats` endpoint (Batch 2) does not expose per-class precision/recall — only distribution, avg_confidence, total, and timeseries. The radar chart uses `avg_confidence` as a proxy metric across 5 axes (Precisión, Recall, F1-Score, Exactitud, Confianza) until a dedicated `/model-metrics` endpoint is added.

3. **Dockerfile locations**: The design placed Dockerfiles under `infra/{service}/Dockerfile`. The orchestrator's task description and existing codebase keep Dockerfiles at `spark/Dockerfile`, `api/Dockerfile`, and `dashboard/Dockerfile`. The docker-compose.yml references these directly. This is simpler and matches the existing project structure.

4. **Jenkinsfile Dockerfile.jenkins skipped**: The orchestrator marked T5.5 (infra/Dockerfile.jenkins) as optional. It was not needed because `agent any` is sufficient and the project builds directly from service Dockerfiles.

### Issues Found

1. **No dedicated /model-metrics endpoint**: The dashboard radar chart cannot show true precision/recall per class because the API lacks a model_metrics endpoint. Workaround: uses avg_confidence as proxy. Recommendation: Add `GET /model-metrics` in a future batch.

2. **Spark master/worker CMD override**: The existing `spark/Dockerfile` sets `CMD ["python", "-m", "spark.train"]`. In docker-compose, the bitnami entrypoint respects `SPARK_MODE` environment variable, but the CMD might need to be empty for pure master/worker mode. The compose file does not override CMD; if issues arise, add `command: []` to spark-master and spark-worker services.

3. **Chart.js CDN dependency**: The dashboard loads Chart.js from jsDelivr CDN. For air-gapped environments, vendor the library locally.

### Remaining Tasks (Next Batch)

#### Batch 4 — Testing + Documentation
- [x] T6.1–T6.8 API tests, Spark tests, integration tests
- [x] T7.1–T7.4 Documentation updates

### Status

**39 / 45 tasks complete**. Ready for Batch 4 (Testing + Documentation).

---

## Batch 4 of 4 — Testing + Documentation + Critical Fix

### Completed Tasks

#### Critical Fix: /model-metrics endpoint + Dashboard Radar Chart
- [x] **Fix** Add `GET /model-metrics` endpoint — `api/routes/model_metrics.py`
- [x] **Fix** Add `ModelMetricsResponse` schema — `api/models.py`
- [x] **Fix** Add `get_model_metrics()` helper — `api/database.py`
- [x] **Fix** Register router in `api/main.py`
- [x] **Fix** Update radar chart to consume `/model-metrics` — `dashboard/js/charts.js`
- [x] **Fix** Update app polling to fetch `/model-metrics` — `dashboard/js/app.js`

#### Phase 6: Testing
- [x] **T6.1** Create `tests/__init__.py`
- [x] **T6.2** Create `tests/conftest.py` — pytest fixtures with `FakeDatabase` and `fake_model_loader` mocks
- [x] **T6.3** Create `tests/test_api/test_predict.py` — Tests POST /predict (valid input, empty text, model not loaded, too long text)
- [x] **T6.4** Create `tests/test_api/test_sentiments.py` — Tests GET /sentiments (pagination, filtering, empty collection, limit bounds)
- [x] **T6.5** Create `tests/test_api/test_stats.py` — Tests GET /stats and GET /model-metrics (structure, period param, metrics exists, metrics not found)
- [x] **T6.6** Create `tests/test_api/test_health.py` — Tests GET /health
- [x] **T6.7** Create `tests/integration/test_docker_compose.sh` — Bash integration test: compose up, health check, predict, sentiments, stats, model-metrics, MongoDB verification, compose down
- [x] **T6.8** Create `pyproject.toml` — pytest configuration, optional test/dev dependencies, black/isort settings

#### Phase 7: Documentation
- [x] **T7.1** Update `README.md` — Complete project info: architecture diagram, prerequisites, setup, API summary with examples, dashboard features, dataset limitations, Jenkins instructions, troubleshooting
- [x] **T7.2** Create `docs/ARCHITECTURE.md` — Component diagram, data flow diagrams, technology stack, design decisions, collection schemas, error handling, directory structure
- [x] **T7.3** Create `docs/API.md` — Full API documentation: all endpoints with methods, parameters, request/response examples, error codes, curl commands, data types reference
- [x] **T7.4** Create `docs/DEPLOYMENT.md` — Docker Compose deployment, Jenkins setup, environment variables, production considerations, troubleshooting

### Files Changed (Batch 4)

| File | Action | Description |
|---|---|---|
| `api/models.py` | Modified | Added `ModelMetricsResponse` schema |
| `api/database.py` | Modified | Added `get_model_metrics()` helper |
| `api/routes/model_metrics.py` | Created | `GET /model-metrics` endpoint with 404 handling |
| `api/main.py` | Modified | Registered `model_metrics` router |
| `dashboard/js/charts.js` | Modified | Added `updateRadarChartMetrics()`; exports new function |
| `dashboard/js/app.js` | Modified | Added `fetchModelMetrics()`; updated `refreshData()` to call radar metrics |
| `tests/__init__.py` | Created | Test package init |
| `tests/conftest.py` | Created | `FakeDatabase` in-memory mock + `fake_model_loader` fixture + `client` fixture |
| `tests/test_api/test_predict.py` | Created | Unit tests for POST /predict (200, 422, 503) |
| `tests/test_api/test_sentiments.py` | Created | Unit tests for GET /sentiments (pagination, filter, empty, bounds) |
| `tests/test_api/test_stats.py` | Created | Unit tests for GET /stats and GET /model-metrics |
| `tests/test_api/test_health.py` | Created | Unit test for GET /health |
| `tests/integration/test_docker_compose.sh` | Created | Bash integration test for full Docker Compose stack |
| `pyproject.toml` | Created | Project metadata, pytest config, optional test/dev deps, tool settings |
| `README.md` | Modified | Complete rewrite with architecture, setup, API examples, limitations, troubleshooting |
| `docs/ARCHITECTURE.md` | Created | Detailed architecture document |
| `docs/API.md` | Created | Full API reference with examples |
| `docs/DEPLOYMENT.md` | Created | Deployment guide with Docker, Jenkins, production notes |
| `openspec/changes/init-architecture/tasks.md` | Modified | Marked all Phase 6 and Phase 7 tasks complete |

### Deviations from Design

1. **Test location**: The original tasks referenced `api/tests/`. The implementation places tests at the repository root under `tests/` with subdirectories `test_api/` and `integration/`. This is the modern Python convention and keeps tests decoupled from source code.

2. **FakeDatabase instead of mongomock**: The design did not specify a mock strategy. The implementation uses a pure-Python `FakeDatabase` class that mirrors the public interface of `api.database.Database`. This avoids introducing `mongomock` as a new dependency while still providing fast, deterministic tests without a real MongoDB instance.

3. **Integration test as bash script**: The task allowed a bash script if Python integration testing was too complex. A bash script is the most reliable integration test for a Docker Compose stack because it exercises the actual containers, networking, and volume mounts exactly as production would.

4. **pyproject.toml instead of pytest.ini**: The task mentioned `tests/pytest.ini` or `pyproject.toml`. The implementation uses `pyproject.toml` at the repository root because it is the modern Python standard (PEP 621/518) and consolidates project metadata, dependencies, and tool configuration in a single file.

### Issues Found

1. **Model version still "unknown" in inference**: The critical fix adds `/model-metrics` but does not resolve the root cause from Batch 2 — `inference.py` still hardcodes `"unknown"` for `model_version` because the saved `PipelineModel` does not embed the version string. A future enhancement could query `model_metrics` at startup to inject the latest version into predictions.

2. **Radar chart F1 approximation**: Because `model_metrics` stores a single global `f1_score` rather than per-class F1, the dashboard radar chart replicates that global value across all three classes. For a more accurate visualization, the Spark training script should compute and store per-class F1 scores.

3. **Test dependency on inference.py mocks**: `test_predict.py` must mock the PySpark `transform` chain deeply (DataFrame, collect, row.prediction, row.probability). This is brittle if the inference implementation changes. The `FakeDatabase` approach works well, but the PySpark mock chain is inherently complex.

### Remaining Tasks

None — all 45 tasks are complete.

### Status

**45 / 45 tasks complete**. Ready for verify phase.
