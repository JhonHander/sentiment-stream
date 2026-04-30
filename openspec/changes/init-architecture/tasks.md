# Tasks: init-architecture

## Phase 1: Project Setup

- [x] **T1.1** Create dirs: `data/`, `spark/`, `api/`, `dashboard/`, `infra/`, `docs/`. D:— AC: dirs exist.
- [x] **T1.2** Create `.gitignore`. D:T1.1 AC: ignores Python/Spark/Node artifacts.
- [x] **T1.3** Create `README.md` template. D:T1.1 AC: has sections.

## Phase 2: Spark Pipeline

- [x] **T2.1** Create `spark/requirements.txt`. D:T1.1 AC: lists pyspark, pymongo.
- [x] **T2.2** Create `spark/Dockerfile`. D:T2.1 AC: image builds.
- [x] **T2.3** Create `spark/ingest.py` (read CSV, dedupe, synthetic id/timestamp). D:T2.1 AC: returns cleaned DataFrame.
- [x] **T2.4** Create `spark/train.py` (build Pipeline, train, save model+metrics). D:T2.2,T2.3 AC: model on volume; metrics in DB.
- [x] **T2.5** Create `spark/stream.py` (Structured Streaming, 5s trigger, dedup, foreachBatch). D:T2.3,T2.4 AC: micro-batches write to MongoDB.
- [x] **T2.6** Create `spark/utils.py` (MongoDB connection, logging, config, label mapping). D:T2.3 AC: shared utilities.
- [x] **T2.7** Create `spark/__init__.py`. D:T2.3 AC: package init.

## Phase 3: FastAPI Backend

- [x] **T3.1** Create `api/requirements.txt`. D:T1.1 AC: lists fastapi, motor, pydantic-settings.
- [x] **T3.2** Create `api/Dockerfile`. D:T3.1 AC: image builds.
- [x] **T3.3** Create `api/config.py` (Pydantic Settings). D:T3.1 AC: loads env vars.
- [x] **T3.4** Create `api/models.py` (PredictRequest, PredictResponse, SentimentsResponse, StatsResponse). D:T3.1 AC: validates.
- [x] **T3.5** Create `api/dependencies.py` (Motor client, model injection). D:T3.3 AC: `get_db()` works.
- [x] **T3.6** Create `api/services/inference.py` (PipelineModelWrapper, `run_in_executor`). D:T3.3 AC: returns prediction dict.
- [x] **T3.7** Create `api/services/repository.py` (persist, query, stats). D:T3.5 AC: returns correct shapes.
- [x] **T3.8** Create `api/main.py` (FastAPI lifespan, routers, CORS). D:T3.4,T3.5,T3.6,T3.7 AC: starts; `/docs` works.
- [x] **T3.9** Create `api/routes/predict.py` (`POST /predict`). D:T3.6,T3.7,T3.8 AC: returns prediction; persists.
- [x] **T3.10** Create `api/routes/sentiments.py` (`GET /sentiments` paginated). D:T3.7,T3.8 AC: returns paginated JSON.
- [x] **T3.11** Create `api/routes/stats.py` (`GET /stats`). D:T3.7,T3.8 AC: returns distribution, avg confidence, timeseries.

## Phase 4: Dashboard

- [x] **T4.1** Create `dashboard/index.html` (Chart.js containers, table). D:T1.1 AC: valid HTML.
- [x] **T4.2** Create `dashboard/css/styles.css` (responsive dark theme). D:T4.1 AC: works at 320px+.
- [x] **T4.3** Create `dashboard/js/config.js` (API base, colors, interval). D:T4.1 AC: exports config.
- [x] **T4.4** Create `dashboard/js/api.js` (fetch wrapper with retry). D:T4.3 AC: retries 3x.
- [x] **T4.5** Create `dashboard/js/charts/doughnut.js`. D:T4.3 AC: updates with data.
- [x] **T4.6** Create `dashboard/js/charts/bar.js`. D:T4.3 AC: updates with data.
- [x] **T4.7** Create `dashboard/js/charts/line.js`. D:T4.3 AC: updates with data.
- [x] **T4.8** Create `dashboard/js/charts/radar.js`. D:T4.3 AC: updates with data.
- [x] **T4.9** Create `dashboard/js/charts/table.js`. D:T4.3 AC: renders rows.
- [x] **T4.10** Create `dashboard/js/app.js` (init, 10s polling, offline banner). D:T4.4,T4.5-4.9 AC: all charts render; refreshes.
- [x] **T4.11** Create `dashboard/Dockerfile` (nginx). D:T4.2,T4.10 AC: serves static files.

## Phase 5: Infrastructure

- [x] **T5.1** Create `infra/docker-compose.yml` (MongoDB, Spark, API, Dashboard). D:T2.2,T3.2,T4.11 AC: `up` exits 0; healthy.
- [x] **T5.2** Create `infra/docker-compose.test.yml`. D:T5.1 AC: test profile runs.
- [x] **T5.3** Create `infra/mongodb-init.js` (indexes). D:T5.1 AC: indexes created.
- [x] **T5.4** Create `infra/Jenkinsfile` (Checkout→Build→Test→Lint→Deploy). D:T5.1 AC: valid declarative syntax.
- [x] **T5.5** Create `infra/spark/Dockerfile`. D:T2.2 AC: builds via compose.
- [x] **T5.6** Create `infra/api/Dockerfile`. D:T3.2 AC: builds via compose.
- [x] **T5.7** Create `infra/dashboard/Dockerfile`. D:T4.11 AC: builds via compose.

## Phase 6: Testing

- [x] **T6.1** Create `tests/conftest.py` (fixtures). D:T3.8 AC: injectable.
- [x] **T6.2** Create `tests/test_api/test_predict.py`. D:T3.9,T6.1 AC: covers 200/422/503.
- [x] **T6.3** Create `tests/test_api/test_sentiments.py`. D:T3.10,T6.1 AC: paginated data.
- [x] **T6.4** Create `tests/test_api/test_stats.py`. D:T3.11,T6.1 AC: stats JSON + model-metrics.
- [x] **T6.5** Create `tests/test_api/test_health.py`. D:T3.8 AC: health endpoint.
- [x] **T6.6** Create `tests/integration/test_docker_compose.sh`. D:T5.1 AC: end-to-end bash script.
- [x] **T6.7** Create `pyproject.toml` with pytest configuration. D:T6.1 AC: test runner config.
- [x] **T6.8** Create `tests/__init__.py`. D:T6.1 AC: package init.

## Phase 7: Documentation

- [x] **T7.1** Update `README.md`. D:T5.1 AC: architecture, setup, limitations.
- [x] **T7.2** Create `docs/ARCHITECTURE.md`. D:T7.1 AC: components and data flow.
- [x] **T7.3** Create `docs/API.md`. D:T3.11 AC: endpoints with examples.
- [x] **T7.4** Create `docs/DEPLOYMENT.md`. D:T5.4 AC: Docker and Jenkins steps.
