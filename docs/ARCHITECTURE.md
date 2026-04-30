# Sentiment-Stream — Architecture Document

> Detailed architecture, component design, data flows, and technology decisions.

---

## 1. Component Diagram

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                    │
│  ┌─────────────────┐                                                        │
│  │   Browser       │  Vanilla JS + Chart.js v4                              │
│  │   (Dashboard)   │  Polling every 10s via fetch()                         │
│  └────────┬────────┘                                                        │
└───────────┼─────────────────────────────────────────────────────────────────┘
            │ HTTP/JSON
            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API LAYER                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  FastAPI  (Python 3.11)                                                │ │
│  │  ├── Lifespan: MongoDB connect + index creation + model load           │ │
│  │  ├── CORS middleware                                                   │ │
│  │  └── Routes: /predict | /sentiments | /stats | /model-metrics | /health│ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│         │                                    │                              │
│         │ Motor (async)                      │ PipelineModel.load()         │
│         ▼                                    ▼                              │
└─────────────────────────────────────────────────────────────────────────────┘
            │                                         │
            ▼                                         ▼
┌──────────────────────┐                    ┌──────────────────────┐
│     MongoDB 7.0      │                    │  Shared Volume       │
│  ┌────────────────┐  │                    │  (model_storage)     │
│  │ predictions    │  │                    │                      │
│  │ model_metrics  │  │                    │  /opt/spark/model/   │
│  └────────────────┘  │                    │  pipeline_model/     │
└──────────┬───────────┘                    └──────────────────────┘
           │                                          ▲
           │ pymongo (sync)                           │
           ▼                                          │
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PROCESSING LAYER                                   │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  PySpark 3.5.2  (bitnami/spark)                                        │ │
│  │  ├── ingest.py   → CSV → DataFrame                                     │ │
│  │  ├── train.py    → Pipeline.fit() → PipelineModel.save() + metrics     │ │
│  │  └── stream.py   → readStream → dropDuplicates → transform → MongoDB   │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Data Flows

### 2.1 Training Flow

```
dataset_sentimientos_500.csv
        │
        ▼ spark.read.csv(header=True, inferSchema=True)
        ▼ .dropDuplicates(["texto"])
┌─────────────────┐
│ Deduplicated DF │  (~30 unique rows)
└────────┬────────┘
         │
         ▼ pipeline.fit(df)
    Tokenizer → StopWordsRemover → HashingTF(500) → IDF → NaiveBayes
         │
         ├──────────────► PipelineModel.save("/opt/spark/model/")
         │
         ▼ model.transform(df) → evaluator
    ┌─────────────────┐
    │  Metrics Dict   │──► MongoDB.model_metrics
    │  (acc, prec,    │    {precision, recall, f1, trained_at, model_version}
    │   rec, f1)      │
    └─────────────────┘
```

### 2.2 Streaming Flow

```
dataset_sentimientos_500.csv
        │
        ▼ spark.readStream.format("csv")
        ▼ .option("maxFilesPerTrigger", 1)
        ▼ .trigger(processingTime="5 seconds")
┌─────────────────┐
│ Streaming DF    │
└────────┬────────┘
         │ dropDuplicates(["texto"])
         ▼
┌─────────────────┐
│ Deduplicated    │
│ Streaming DF    │
└────────┬────────┘
         │ model.transform(deduped)
         ▼
┌─────────────────┐
│ Predictions DF  │  [original_text, prediction, confidence, model_version]
└────────┬────────┘
         │ .writeStream.foreachBatch(write_to_mongo)
         ▼
┌─────────────────┐
│ MongoDB         │  predictions collection
│                 │  {original_text, prediction, confidence, timestamp, model_version}
└─────────────────┘
```

### 2.3 API Request Flow

```
Client → POST /predict {"text": "..."}
    │
    ▼ FastAPI router
    ├─► Pydantic validation (SentimentPredictionRequest)
    ├─► Check app.state.model_loader (503 if None)
    ├─► ThreadPoolExecutor + run_in_executor → PySpark transform
    ├─► Background task: insert_prediction → MongoDB
    └─► JSON response {prediction, confidence, timestamp}

Client → GET /sentiments?limit=10&offset=0
    │
    ▼ FastAPI router
    ├─► Parse query params (limit, offset, sentiment, date_from, date_to)
    ├─► MongoDB find → sort(timestamp, -1) → skip → limit
    └─► JSON response {items, total, limit, offset}

Client → GET /stats?period=hour
    │
    ▼ FastAPI router
    ├─► MongoDB aggregate: distribution, avg_confidence, total
    ├─► MongoDB aggregate: timeseries via $dateTrunc
    └─► JSON response {distribution, avg_confidence, total, timeseries}

Client → GET /model-metrics
    │
    ▼ FastAPI router
    ├─► MongoDB find_one on model_metrics (latest by trained_at)
    ├─► 404 if collection is empty
    └─► JSON response {metrics, model_version, trained_at}
```

---

## 3. Technology Stack

| Layer | Technology | Version | Purpose |
|---|---|---|---|
| Data Processing | PySpark | 3.5.2 | Structured Streaming, MLlib Pipeline |
| ML Algorithm | NaiveBayes (multinomial) | MLlib 3.5.2 | Text classification |
| Feature Engineering | HashingTF + IDF | MLlib 3.5.2 | Term frequency → TF-IDF vectors |
| API Framework | FastAPI | >=0.115.0 | Async REST API with OpenAPI docs |
| Validation | Pydantic v2 | >=2.0.0 | Request/response schemas |
| Async DB Driver | Motor | >=3.5.0 | Async MongoDB client |
| Database | MongoDB | 7.0 | Document store for predictions + metrics |
| Frontend | Chart.js | v4 (CDN) | Interactive visualizations |
| Web Server (Dashboard) | nginx | alpine | Static file serving |
| ASGI Server | Uvicorn | >=0.30.0 | Python async HTTP server |
| Container Runtime | Docker | 24.0+ | Service isolation |
| Orchestration | Docker Compose | v2.0+ | Multi-service local deployment |
| CI/CD | Jenkins | 2.400+ | Declarative pipeline |
| Testing | pytest | >=8.0.0 | Unit and integration tests |

---

## 4. Design Decisions

### 4.1 HashingTF with 500 features

The dataset contains ~30 unique records with very short texts (~28 chars average). A vocabulary of <100 terms makes `numFeatures=500` more than sufficient while keeping memory and compute overhead minimal. Collision probability is acceptable for an educational project.

### 4.2 Motor instead of PyMongo

FastAPI is inherently async. Using Motor prevents blocking the event loop on every database call, which is critical when the dashboard polls every 10 seconds and multiple clients may call `/predict` concurrently.

### 4.3 ThreadPoolExecutor for PySpark inference

PySpark DataFrames and the underlying JVM are not picklable, so `ProcessPoolExecutor` fails. `ThreadPoolExecutor` is the standard pattern: JVM calls release the GIL, allowing true concurrency within the same process.

### 4.4 Lifespan over startup events

`asynccontextmanager` lifespan guarantees that MongoDB indexes and the ML model are fully initialized BEFORE the first HTTP request arrives. This eliminates race conditions that existed with the deprecated `on_startup`/`on_shutdown` events.

### 4.5 Shared Docker volume for model artifacts

A named volume (`model_storage`) is the simplest mechanism for file-based handoff between Spark and FastAPI containers in a single-host deployment. S3/MinIO would add unnecessary complexity for this scope.

### 4.6 Consolidated dashboard JS

The design originally proposed 8 separate JS files. The implementation consolidates into 3 (`utils.js`, `charts.js`, `app.js`) to reduce HTTP requests and simplify dependency management, without losing any functionality.

---

## 5. Collection Schemas

### 5.1 `predictions`

```javascript
{
  "_id": ObjectId,
  "original_text": String,
  "prediction": String,      // "positivo" | "negativo" | "neutral"
  "confidence": Double,      // 0.0 - 1.0
  "timestamp": ISODate,
  "model_version": String
}
```

**Indexes:**
- `{ "timestamp": -1 }` — latest-first queries
- `{ "prediction": 1 }` — sentiment filtering
- `{ "confidence": -1 }` — high-confidence queries

### 5.2 `model_metrics`

```javascript
{
  "_id": ObjectId,
  "accuracy": Double,
  "precision": Object,       // { "positivo": 0.85, "negativo": 0.80, "neutral": 0.75 }
  "recall": Object,          // { "positivo": 0.82, "negativo": 0.78, "neutral": 0.72 }
  "f1_score": Double,
  "trained_at": ISODate,
  "model_version": String    // Unique
}
```

**Indexes:**
- `{ "model_version": 1 }` — unique, version lookups

---

## 6. Error Handling & Resilience

| Component | Failure Mode | Strategy |
|---|---|---|
| Spark Streaming | Query crash | Docker `restart: unless-stopped`; checkpoint resume |
| Spark Training | OOM / schema mismatch | Log error; no model saved; API returns 503 |
| FastAPI | Model not found at startup | Start without model; `/predict` returns 503; other endpoints work |
| FastAPI | MongoDB unreachable | Lifespan retry 3× with exponential backoff; return 500 if persists |
| Dashboard | API unreachable | 3 retries with 1s backoff; offline banner |
| Dashboard | Empty dataset | Show "No data yet" placeholder |

---

## 7. Directory Structure

```
sentiment-stream/
├── api/                    # FastAPI backend
│   ├── routes/             # HTTP route definitions
│   ├── services/           # Model loader + inference logic
│   ├── database.py         # Motor client + CRUD helpers
│   ├── models.py           # Pydantic schemas
│   ├── config.py           # Environment-based settings
│   └── main.py             # App factory with lifespan
├── dashboard/              # Static frontend
│   ├── js/                 # app.js, charts.js, utils.js
│   ├── css/                # styles.css
│   └── index.html
├── spark/                  # PySpark pipeline
│   ├── ingest.py
│   ├── train.py
│   ├── stream.py
│   └── utils.py
├── infra/                  # Infrastructure
│   ├── docker-compose.yml
│   ├── docker-compose.test.yml
│   ├── Jenkinsfile
│   └── mongodb-init.js
├── tests/                  # Test suite
│   ├── conftest.py         # Fixtures (fake DB, fake model)
│   ├── test_api/           # Unit tests per endpoint
│   └── integration/        # Docker Compose integration test
├── docs/                   # Documentation
│   ├── ARCHITECTURE.md
│   ├── API.md
│   └── DEPLOYMENT.md
└── data/                   # CSV dataset
    └── dataset_sentimientos_500.csv
```
