# Proposal: Initial Architecture for Sentiment-Stream

## Intent

Build an end-to-end sentiment analysis pipeline that demonstrates Big Data engineering concepts: PySpark MLlib for training, FastAPI for serving, MongoDB for persistence, Docker for containerization, Jenkins for CI/CD, and a professional HTML/CSS/JS dashboard with Chart.js. The project must work with the provided dataset despite its documented quality limitations.

## Scope

### In Scope
- PySpark MLlib training pipeline (Tokenizer -> StopWordsRemover -> HashingTF -> IDF -> NaiveBayes)
- Spark Structured Streaming micro-batch ingestion from CSV
- FastAPI REST API with `/predict`, `/sentiments`, `/stats` endpoints
- MongoDB persistence with async Motor driver
- Vanilla JS + Chart.js dashboard with 5+ visualizations
- Docker Compose orchestration for all services
- Jenkins Declarative Pipeline for build/test/deploy
- Dataset deduplication and documented preprocessing

### Out of Scope
- Real-time WebSocket streaming (use polling)
- Model retraining automation
- Multi-language support beyond English
- Production-grade monitoring/observability
- Cloud deployment (local Docker only)

## Capabilities

### New Capabilities
- `data-ingestion`: Spark Structured Streaming micro-batch ingestion from CSV with deduplication
- `ml-pipeline`: PySpark MLlib feature extraction and NaiveBayes training with model persistence
- `prediction-api`: FastAPI async endpoints for inference, querying, and statistics
- `persistence`: MongoDB collections for predictions with indexing and schema validation
- `dashboard`: HTML/CSS/JS frontend with Chart.js visualizations and API polling
- `infrastructure`: Docker Compose services, networking, volumes, health checks
- `ci-cd`: Jenkins Declarative Pipeline with build, test, and deploy stages

### Modified Capabilities
- None (greenfield project)

## Approach

### Architecture Overview

```
+-------------+     +-----------------+     +-------------+
|  CSV File   |---->| Spark Streaming |---->|  MongoDB    |
| (Dataset)   |     | (Micro-batch)   |     | (Predicts)  |
+-------------+     +-----------------+     +------+------+
         |                    |                     |
         v                    v                     v
  +--------------+    +--------------+     +-------------+
  | ML Pipeline  |    |  FastAPI     |<----|   Motor     |
  | NaiveBayes   |    |  (REST API)  |     |  (async)    |
  +--------------+    +------+-------+     +-------------+
                             |
                             v
                    +-----------------+
                    | Dashboard       |
                    | (Chart.js)      |
                    +-----------------+
```

### Component Breakdown

**Data Ingestion (Spark Structured Streaming)**
- Use `spark.readStream.format("csv")` with micro-batch trigger (`processingTime='5 seconds'`)
- Deduplicate within each micro-batch using `dropDuplicates("texto")`
- Stream to MongoDB via foreachBatch sink
- *Context7 (PySpark)*: Structured Streaming supports `foreachBatch` for custom sinks; MLlib models support `save()` and `load()` for persistence

**Processing Pipeline (PySpark MLlib)**
1. `Tokenizer(inputCol="texto", outputCol="palabras")`
2. `StopWordsRemover(inputCol="palabras", outputCol="filtrado")`
3. `HashingTF(inputCol="filtrado", outputCol="rawFeatures", numFeatures=500)` -- reduced from 1000 due to short texts (avg 28 chars)
4. `IDF(inputCol="rawFeatures", outputCol="features")`
5. `NaiveBayes(smoothing=1.0, modelType="multinomial")`
- Save full PipelineModel to shared volume for FastAPI loading
- *Context7 (PySpark)*: `NaiveBayesModel.save(path)` and `NaiveBayesModel.load(path)` retain learned parameters; `HashingTF.save()` preserves numFeatures configuration

**Persistence Layer (MongoDB)**
- Database: `sentiment_stream`
- Collections:
  - `predictions`: `{ _id, texto, prediccion, confianza, timestamp, modelo_version }`
  - `model_metrics`: `{ _id, accuracy, f1_score, trained_at, model_version }`
- Indexes: `predictions.timestamp` (descending), `predictions.prediccion`, `predictions.confianza`
- Use Motor async driver for non-blocking I/O in FastAPI
- *Context7 (MongoDB)*: `create_index()` with Motor is awaitable; MongoDB has dynamic schema but collections hold homogeneous documents; indexes must be explicitly created except `_id`

**API Layer (FastAPI)**
- `lifespan` async context manager (supersedes startup/shutdown events as of v0.93.0) to load ML model once on startup
- `BackgroundTasks` for async logging and non-critical side effects
- Use `run_in_executor` for PySpark CPU-bound inference calls
- Endpoints:
  - `POST /predict` -- inference on new text, stores result in MongoDB
  - `GET /sentiments` -- paginated list with `sentiment`, `start_date`, `end_date`, `limit` filters
  - `GET /stats` -- class distribution, confidence averages, prediction counts by period
- *Context7 (FastAPI)*: `lifespan` is the recommended approach for startup/shutdown; `BackgroundTasks` integrates with dependency injection

**Dashboard (HTML/CSS/JS + Chart.js)**
- Static files served by FastAPI (`Mount("/", StaticFiles(...))`)
- Visualizations (all using Chart.js v3.9+):
  1. Doughnut chart -- sentiment class distribution
  2. Horizontal bar chart -- confidence by class
  3. Line chart -- prediction volume over time (using prediction timestamp)
  4. Radar chart -- model metrics comparison (accuracy, precision, recall, F1)
  5. Table -- recent predictions with pagination and filtering
- Auto-refresh every 10 seconds via `fetch()` polling
- *Context7 (Chart.js)*: Supports bar, doughnut, pie, radar, line types; responsive with `plugins.legend`, `plugins.title`, and `scales` configuration

**Infrastructure (Docker Compose)**
- Services: `mongodb`, `spark-master`, `spark-worker`, `api`, `dashboard`
- `api` depends on `mongodb` with healthcheck
- Shared volume `model_storage` for Spark -> FastAPI model handoff
- Bridge network `sentiment-net` for service discovery
- *Context7 (Docker Compose)*: `depends_on` controls startup order; `healthcheck` validates readiness; `volumes` persist data across restarts

**CI/CD (Jenkins)**
- Declarative Pipeline with stages:
  1. `Checkout` -- pull from SCM
  2. `Build` -- build Docker images (api, spark, dashboard)
  3. `Test` -- run pytest for API, Spark unit tests
  4. `Lint` -- flake8, black check
  5. `Deploy` -- `docker compose up -d` on Jenkins agent
- *Context7 (Jenkins)*: Declarative Pipeline supports `agent { dockerfile true }` and per-stage Docker agents; `skipStagesAfterUnstable()` prevents deploying broken builds

### Data Flow

1. **Training Phase**: Spark reads deduplicated CSV -> builds Pipeline (Tokenizer -> StopWordsRemover -> HashingTF -> IDF -> NaiveBayes) -> trains model -> saves PipelineModel to `model_storage` volume -> stores metrics to MongoDB
2. **Streaming Phase**: Spark Structured Streaming reads CSV in micro-batches -> deduplicates -> passes through saved PipelineModel -> writes predictions to MongoDB via foreachBatch
3. **Inference Phase**: Client sends text to `POST /predict` -> FastAPI loads PipelineModel from volume (via lifespan) -> transforms text -> returns prediction -> stores in MongoDB
4. **Dashboard Phase**: Browser loads static files -> JavaScript polls `GET /stats` and `GET /sentiments` -> Chart.js renders visualizations -> table displays paginated predictions

### Technology Decisions

| Technology | Decision | Justification |
|------------|----------|---------------|
| PySpark Structured Streaming | Micro-batch with `foreachBatch` | Context7: Native Spark streaming with fault tolerance; `foreachBatch` allows custom MongoDB writes per micro-batch |
| FastAPI `lifespan` | Load model on startup | Context7: Recommended since v0.93.0; replaces startup/shutdown events; ensures model is ready before first request |
| Motor (async MongoDB) | Non-blocking DB I/O | Context7: `await db.collection.create_index()` provides async index creation; avoids blocking FastAPI event loop |
| Chart.js v3.9+ | 5 chart types | Context7: Simple, flexible, supports bar, doughnut, line, radar with responsive plugins and custom styling |
| Docker Compose | `depends_on` + healthchecks | Context7: Multi-container orchestration with service dependencies; healthchecks ensure MongoDB is ready before API starts |
| Jenkins Declarative | Build/Test/Deploy stages | Context7: `agent { dockerfile true }` builds from repo Dockerfile; `skipStagesAfterUnstable()` gates deployment |
| NaiveBayes | Multinomial with smoothing=1.0 | Standard for text classification with TF-IDF; handles sparse feature vectors well; computationally efficient |

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `spark/` | New | Training pipeline, streaming ingestion, model persistence |
| `api/` | New | FastAPI app, routes, Pydantic models, MongoDB connection |
| `dashboard/` | New | HTML, CSS, JS, Chart.js visualizations |
| `infra/` | New | Docker Compose, Dockerfiles, Jenkinsfile |
| `data/processed/` | New | Deduplicated dataset |
| `openspec/` | New | Proposal, specs, design, tasks |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| 94% duplicate data causes overfitting | High | Deduplicate to ~30 unique samples; acknowledge educational limitation in docs; focus on pipeline correctness over accuracy |
| Very short texts limit feature extraction | High | Reduce HashingTF to 500 features; use stop word removal; accept lower accuracy |
| PySpark blocking FastAPI event loop | Medium | Use `run_in_executor` for all Spark inference; separate training and serving containers |
| MongoDB connection failures on startup | Low | Docker Compose `depends_on` with healthcheck; FastAPI retry logic in lifespan |
| Jenkins agent lacks Docker | Medium | Document prerequisite; use `agent { dockerfile true }` to build inside container |

## Rollback Plan

1. All Docker images tagged with Git commit SHA
2. `docker compose down` stops all services immediately
3. MongoDB data persisted in named volume; can restore from backup if needed
4. PipelineModel saved with version suffix; FastAPI can load previous version by changing env var
5. Jenkins `skipStagesAfterUnstable()` prevents broken deployments from reaching production

## Dependencies

- Docker Engine 24.0+
- Docker Compose v2+
- Jenkins 2.400+ with Docker Pipeline plugin
- Python 3.11+ (for local development)
- Git repository for SCM integration

## Success Criteria

- [ ] FastAPI responds correctly to `/predict`, `/sentiments`, `/stats` with <500ms latency
- [ ] Dashboard displays 5+ Chart.js visualizations and auto-refreshes every 10s
- [ ] Spark Structured Streaming processes CSV in micro-batches and stores predictions to MongoDB
- [ ] Docker Compose starts all services with `docker compose up -d` and passes health checks
- [ ] Jenkins pipeline completes Build, Test, Lint, Deploy stages successfully
- [ ] Dataset limitations are documented in README and inline comments
- [ ] Model persists to shared volume and loads correctly in FastAPI on startup
