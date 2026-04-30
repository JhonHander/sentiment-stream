# Sentiment-Stream — Technical Design Document

> **Change**: `init-architecture`  
> **Status**: Design  
> **Context7 References**: PySpark 3.5.x API, FastAPI v0.115+, Motor 3.x, Docker Compose v2, Jenkins Declarative Pipeline, Chart.js v3.9+

---

## 1. Component Design

### 1.1 Spark Service (`spark/`)

#### Internal Structure

```
spark/
├── __init__.py
├── config.py            # SparkSession factory, constants, env vars
├── pipeline.py           # ML pipeline definition: Tokenizer → StopWordsRemover → HashingTF → IDF → NaiveBayes
├── train.py             # Training script: load CSV → deduplicate → train → save PipelineModel + metrics
├── stream.py            # Structured Streaming: read CSV micro-batches → deduplicate → transform → foreachBatch write
├── sink.py              # MongoDB foreachBatch writer function
└── tests/
    ├── __init__.py
    ├── test_pipeline.py  # Unit: pipeline stages produce expected column names
    ├── test_train.py     # Unit: training produces saved model on disk
    └── test_stream.py    # Unit: foreachBatch function writes expected document shape
```

#### Module Details

**`config.py`**

```python
# Key constants (from spec)
SPARK_APP_NAME = "SentimentStream"
CSV_PATH = "/opt/spark/data/dataset_sentimientos_500.csv"
MODEL_PATH = "/opt/spark/model/pipeline_model"
MONGO_URI = "mongodb://mongodb:27017/sentiment_stream"
MONGO_COLLECTION = "predictions"
MONGO_METRICS_COLLECTION = "model_metrics"
NUM_FEATURES = 500
SMOOTHING = 1.0
MODEL_TYPE = "multinomial"
TRIGGER_INTERVAL = "5 seconds"
```

- `get_spark_session() -> SparkSession`: Factory function. Creates or retrieves a `SparkSession` with MongoDB connector config. Sets `spark.sql.streaming.schemaInference=true` for CSV streaming.

**`pipeline.py`**

```python
def build_pipeline() -> Pipeline:
    """Construct the ML pipeline with 5 stages."""
    tokenizer = Tokenizer(inputCol="texto", outputCol="palabras")
    remover = StopWordsRemover(inputCol="palabras", outputCol="filtrado")
    hashing_tf = HashingTF(
        inputCol="filtrado",
        outputCol="rawFeatures",
        numFeatures=NUM_FEATURES  # 500
    )
    idf = IDF(inputCol="rawFeatures", outputCol="features")
    nb = NaiveBayes(
        smoothing=SMOOTHING,        # 1.0
        modelType=MODEL_TYPE,       # "multinomial"
        labelCol="etiqueta",
        featuresCol="features"
    )
    return Pipeline(stages=[tokenizer, remover, hashing_tf, idf, nb])
```

- **Context7 (PySpark)**: `Tokenizer` splits text on whitespace, producing an array of strings in `outputCol`. `StopWordsRemover` filters default English stop words; supports `save()`/`load()` for persistence with `getStopWords()` preserved. `HashingTF.setNumFeatures(500)` maps term vectors to a fixed-size sparse vector; configuration preserved across save/load. `IDF` fits inverse document frequencies from the term frequencies. `NaiveBayes(smoothing=1.0, modelType="multinomial")` learns priors (`pi`) and conditional probabilities (`theta`); these are preserved on `save()`/`load()`.

**`train.py`**

```python
def train_model(spark: SparkSession) -> tuple[PipelineModel, dict]:
    """Train the pipeline and return (model, metrics_dict)."""
    # Load and deduplicate
    df = (spark.read.csv(CSV_PATH, header=True, inferSchema=True)
            .dropDuplicates(["texto"]))
    pipeline = build_pipeline()
    model = pipeline.fit(df)
    
    # Evaluate
    predictions = model.transform(df)
    evaluator = MulticlassClassificationEvaluator(
        labelCol="etiqueta", predictionCol="prediction"
    )
    metrics = {
        "accuracy": evaluator.evaluate(predictions, {evaluator.metricName: "accuracy"}),
        "f1_score": evaluator.evaluate(predictions, {evaluator.metricName: "f1"}),
        # Per-class precision/recall computed via BinaryClassificationEvaluator or manual
        "precision_per_class": {...},
        "recall_per_class": {...},
        "trained_at": datetime.utcnow().isoformat(),
        "model_version": f"v1_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    }
    
    # Persist model to shared volume
    model.save(MODEL_PATH)
    
    # Persist metrics to MongoDB
    write_metrics_to_mongo(metrics)
    
    return model, metrics
```

**`stream.py`**

```python
def start_streaming(spark: SparkSession, model: PipelineModel):
    """Start Structured Streaming with foreachBatch sink."""
    stream_df = (spark.readStream
        .format("csv")
        .option("header", True)
        .option("path", CSV_PATH)
        .option("maxFilesPerTrigger", 1)  # Process one file per trigger
        .load())
    
    # Deduplicate within micro-batch
    deduped = stream_df.dropDuplicates(["texto"])
    
    # Transform through loaded model
    predictions = model.transform(deduped)
    
    # Select output columns
    output = predictions.select(
        col("texto").alias("original_text"),
        col("prediction").alias("prediction"),
        # Map numeric prediction to label string
        col("probability").getItem(1).alias("confidence"),
        lit(model_version).alias("model_version")
    )
    
    # Write to MongoDB via foreachBatch
    query = (output.writeStream
        .foreachBatch(lambda df, batch_id: write_batch_to_mongo(df, batch_id))
        .trigger(processingTime=TRIGGER_INTERVAL)  # "5 seconds"
        .outputMode("append")
        .start())
    
    query.awaitTermination()
```

- **Context7 (PySpark)**: `DataStreamWriter.foreachBatch(func)` accepts a function `(DataFrame, int) -> None` where the `int` is the batch ID. `trigger(processingTime='5 seconds')` sets micro-batch interval. `dropDuplicates(["texto"])` performs deduplication within a micro-batch watermark.

**`sink.py`**

```python
def write_batch_to_mongo(batch_df: DataFrame, batch_id: int):
    """Write a micro-batch DataFrame to MongoDB predictions collection."""
    # Convert to list of dicts for pymongo insert
    records = [row.asDict() for row in batch_df.collect()]
    if records:
        # Map numeric prediction back to label string
        for r in records:
            r["timestamp"] = datetime.utcnow().isoformat()
            r["prediction"] = map_prediction_label(r["prediction"])
            r["confidence"] = float(r.get("confidence", 0.0))
        mongo_client[MONGO_COLLECTION].insert_many(records)
```

#### State Management

| State | Location | Lifecycle |
|-------|----------|-----------|
| `PipelineModel` | `/opt/spark/model/pipeline_model` (Docker volume `model_storage`) | Created by `train.py`, read by FastAPI via volume mount |
| Streaming query | In-memory Spark streaming query | Managed by `query.awaitTermination()`; checkpointed to `/opt/spark/checkpoints` |
| Training metrics | MongoDB `model_metrics` collection | Immutable once written; new training appends with new `model_version` |

#### Error Handling Strategy

| Error | Strategy |
|-------|----------|
| CSV file not found | `train.py` exits with non-zero code; Docker restart policy `on-failure` |
| Training fails (OOM, schema mismatch) | Try/except logs error; no model saved; FastAPI healthcheck fails |
| Streaming query fails | `query.exception()` logs; Docker restart with `--restart unless-stopped` |
| MongoDB unreachable in foreachBatch | Batch write fails; Spark retries micro-batch (default maxRetries=3) |
| Model version mismatch | `model_version` stored in both model metadata and MongoDB; FastAPI validates on load |

---

### 1.2 FastAPI Service (`api/`)

#### Internal Structure

```
api/
├── __init__.py
├── main.py              # FastAPI app with lifespan, router mount
├── config.py            # Pydantic settings: MONGO_URI, MODEL_PATH, HOST, PORT
├── dependencies.py      # Dependency injection: db client, model, executor
├── models.py            # Pydantic request/response schemas
├── routes/
│   ├── __init__.py
│   ├── predict.py       # POST /predict
│   ├── sentiments.py    # GET /sentiments
│   └── stats.py         # GET /stats
├── services/
│   ├── __init__.py
│   ├── inference.py     # Model loading, prediction logic, run_in_executor
│   └── repository.py    # MongoDB CRUD operations via Motor
├── static/              # Mounted dashboard files (symlink or copy from dashboard/)
└── tests/
    ├── __init__.py
    ├── test_predict.py
    ├── test_sentiments.py
    ├── test_stats.py
    └── conftest.py       # Test fixtures: mock model, mock mongo
```

#### Module Details

**`main.py`** — Lifespan Pattern

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from api.dependencies import get_model, get_db
from api.routes import predict, sentiments, stats
from api.services.inference import PipelineModelWrapper

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load ML model and MongoDB connection on startup; cleanup on shutdown."""
    # --- STARTUP ---
    # Load PipelineModel from shared volume
    model_wrapper = PipelineModelWrapper.load_from_volume()
    app.state.model = model_wrapper
    
    # Initialize Motor client
    db = await get_db()
    app.state.db = db
    
    # Create indexes
    await db.predictions.create_index([("timestamp", -1)])
    await db.predictions.create_index([("prediction", 1)])
    await db.predictions.create_index([("confidence", -1)])
    await db.model_metrics.create_index([("model_version", 1)], unique=True)
    
    yield  # App is running, serving requests
    
    # --- SHUTDOWN ---
    app.state.db.client.close()

app = FastAPI(
    title="Sentiment Stream API",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(predict.router, prefix="/predict", tags=["prediction"])
app.include_router(sentiments.router, prefix="/sentiments", tags=["sentiments"])
app.include_router(stats.router, prefix="/stats", tags=["statistics"])
```

- **Context7 (FastAPI)**: The `lifespan` parameter accepts an `@asynccontextmanager` function. Code before `yield` runs at startup; code after `yield` runs at shutdown. This is the recommended approach since v0.93.0, replacing the deprecated `on_startup`/`on_shutdown` events. Model loading happens in the startup phase, ensuring it's ready before any request arrives.

**`config.py`** — Pydantic Settings

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    MONGO_URI: str = "mongodb://mongodb:27017"
    MONGO_DB: str = "sentiment_stream"
    MODEL_PATH: str = "/opt/spark/model/pipeline_model"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8080"]
    
    class Config:
        env_file = ".env"

settings = Settings()
```

**`dependencies.py`** — Injection

```python
from motor.motor_asyncio import AsyncIOMotorClient
from api.services.inference import PipelineModelWrapper
from api.config import settings

async def get_db():
    """Return Motor database instance."""
    client = AsyncIOMotorClient(settings.MONGO_URI)
    return client[settings.MONGO_DB]

def get_model(app) -> PipelineModelWrapper:
    """Return loaded model from app state."""
    return app.state.model
```

**`models.py`** — Pydantic Schemas

```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class PredictRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000, description="Text to classify")

class PredictResponse(BaseModel):
    prediction: str
    confidence: float
    timestamp: str
    
class SentimentsResponse(BaseModel):
    items: list[dict]
    total: int
    limit: int
    offset: int

class StatsResponse(BaseModel):
    distribution: dict[str, int]
    avg_confidence: float
    total: int
    timeseries: list[dict]

class ErrorResponse(BaseModel):
    detail: str
```

**`routes/predict.py`**

```python
from fastapi import APIRouter, BackgroundTasks, HTTPException
from api.models import PredictRequest, PredictResponse
from api.services.inference import predict_sentiment
from api.services.repository import persist_prediction
import asyncio

router = APIRouter()

@router.post("/", response_model=PredictResponse)
async def predict_endpoint(request: PredictRequest, background_tasks: BackgroundTasks):
    """Predict sentiment for given text and persist result."""
    # CPU-bound inference — must not block event loop
    result = await predict_sentiment(request.text)
    
    if result is None:
        raise HTTPException(status_code=503, detail="Model not available")
    
    # Persist to MongoDB as background task (fire-and-forget)
    background_tasks.add_task(persist_prediction, result)
    
    return PredictResponse(
        prediction=result["prediction"],
        confidence=result["confidence"],
        timestamp=result["timestamp"]
    )
```

- **Context7 (FastAPI)**: `BackgroundTasks` runs after the response is sent. It integrates with FastAPI's dependency injection. For CPU-bound work like ML inference, `run_in_executor` is required to prevent event loop blocking.

**`services/inference.py`**

```python
import asyncio
from concurrent.futures import ProcessPoolExecutor
from pyspark.ml import PipelineModel
from api.config import settings

class PipelineModelWrapper:
    """Wraps a loaded PySpark PipelineModel for thread-safe inference."""
    
    def __init__(self, model: PipelineModel, spark):
        self.model = model
        self.spark = spark
        self.model_version = self._extract_version()
    
    @classmethod
    def load_from_volume(cls) -> "PipelineModelWrapper":
        """Load PipelineModel from shared Docker volume."""
        from pyspark.sql import SparkSession
        spark = SparkSession.builder.appName("InferenceServer").getOrCreate()
        model = PipelineModel.load(settings.MODEL_PATH)
        return cls(model=model, spark=spark)
    
    def _extract_version(self) -> str:
        """Extract model version from metadata or default to timestamp."""
        return getattr(self.model, '_metadata', {}).get('version', 'unknown')

_executor = ProcessPoolExecutor(max_workers=2)

async def predict_sentiment(text: str) -> dict | None:
    """Run prediction in executor to avoid blocking the event loop."""
    wrapper = _get_model_wrapper()  # from app state
    if wrapper is None:
        return None
    
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(_executor, _sync_predict, wrapper, text)
    return result

def _sync_predict(wrapper: PipelineModelWrapper, text: str) -> dict:
    """Synchronous prediction — runs in ProcessPoolExecutor."""
    from datetime import datetime
    df = wrapper.spark.createDataFrame([(text,)], ["texto"])
    prediction_df = wrapper.model.transform(df)
    row = prediction_df.collect()[0]
    
    return {
        "original_text": text,
        "prediction": row.prediction,
        "confidence": float(row.probability.max()),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "model_version": wrapper.model_version
    }
```

**`services/repository.py`**

```python
from motor.motor_asyncio import AsyncIOMotorDatabase
from api.config import settings
from datetime import datetime

async def persist_prediction(result: dict, db: AsyncIOMotorDatabase):
    """Insert prediction document into MongoDB."""
    await db.predictions.insert_one({
        "original_text": result["original_text"],
        "prediction": result["prediction"],
        "confidence": result["confidence"],
        "timestamp": datetime.fromisoformat(result["timestamp"].replace("Z", "+00:00")),
        "model_version": result["model_version"]
    })

async def get_sentiments(
    db: AsyncIOMotorDatabase,
    limit: int = 20,
    offset: int = 0,
    sentiment: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None
) -> dict:
    """Get paginated predictions with optional filters."""
    query = {}
    if sentiment:
        query["prediction"] = sentiment
    if date_from or date_to:
        query["timestamp"] = {}
        if date_from:
            query["timestamp"]["$gte"] = datetime.fromisoformat(date_from)
        if date_to:
            query["timestamp"]["$lte"] = datetime.fromisoformat(date_to)
    
    total = await db.predictions.count_documents(query)
    cursor = db.predictions.find(query, {"_id": 0}).sort("timestamp", -1).skip(offset).limit(limit)
    items = await cursor.to_list(length=limit)
    
    return {"items": items, "total": total, "limit": limit, "offset": offset}

async def get_stats(db: AsyncIOMotorDatabase, period: str = "day") -> dict:
    """Aggregate prediction statistics."""
    # Distribution
    distribution_cursor = db.predictions.aggregate([
        {"$group": {"_id": "$prediction", "count": {"$sum": 1}}}
    ])
    distribution = {item["_id"]: item["count"] async for item in distribution_cursor}
    
    # Average confidence
    avg_result = await db.predictions.aggregate([
        {"$group": {"_id": None, "avg_confidence": {"$avg": "$confidence"}, "total": {"$sum": 1}}}
    ]).to_list(length=1)
    avg_confidence = avg_result[0]["avg_confidence"] if avg_result else 0.0
    total = avg_result[0]["total"] if avg_result else 0
    
    # Time series
    timeseries_cursor = db.predictions.aggregate([
        {"$group": {
            "_id": {"$dateTrunc": {"date": "$timestamp", "unit": period}},
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}}
    ])
    timeseries = [{"timestamp": item["_id"].isoformat(), "count": item["count"]} 
                  async for item in timeseries_cursor]
    
    return {
        "distribution": distribution,
        "avg_confidence": avg_confidence,
        "total": total,
        "timeseries": timeseries
    }
```

- **Context7 (Motor)**: `AsyncIOMotorClient` creates a single connection pool per process. `await db.collection.create_index()` is awaitable and creates indexes asynchronously. `find()` returns an `AsyncIOMotorCursor` usable with `async for` or `.to_list(length=N)`. `aggregate()` returns a `MotorCommandCursor` usable with `async for` or `.to_list()`. Single `Motor` client per app lifecycle prevents connection pool exhaustion.

#### State Management

| State | Location | Lifecycle |
|-------|----------|-----------|
| `PipelineModel` | `app.state.model` | Loaded in `lifespan` startup, released on shutdown |
| Motor client | `app.state.db` | Created in `lifespan` startup, closed on shutdown |
| Prediction records | MongoDB `predictions` collection | Persistent across restarts |
| Model version | In-memory `app.state.model.model_version` | Set at load time; refreshed on restart |

#### Error Handling Strategy

| Error | Strategy | HTTP Code |
|-------|----------|-----------|
| Model not loaded | Return 503 Service Unavailable | 503 |
| Invalid input (empty text, >1000 chars) | Pydantic validation error | 422 |
| MongoDB unreachable | Retry 3 times with exponential backoff in lifespan; return 500 if persists | 500 |
| Prediction timeout (>10s) | `run_in_executor` timeout; return 504 | 504 |
| Background task failure | Logged but does not affect response | 200 |

---

### 1.3 MongoDB Service

#### Internal Structure

No application code — MongoDB is configured via Docker Compose and initialized via FastAPI's lifespan.

#### Collection Schemas

**`predictions` collection**

```javascript
{
  "_id": ObjectId,
  "original_text": String,      // Required
  "prediction": String,         // "positivo" | "negativo" | "neutral"
  "confidence": Double,         // 0.0 - 1.0
  "timestamp": ISODate,         // UTC timestamp
  "model_version": String       // e.g., "v1_20260430_120000"
}
```

**Indexes**:
- `{ "timestamp": -1 }` — descending for latest-first queries
- `{ "prediction": 1 }` — ascending for sentiment filter
- `{ "confidence": -1 }` — descending for high-confidence queries

**`model_metrics` collection**

```javascript
{
  "_id": ObjectId,
  "accuracy": Double,
  "precision": Object,          // { "positivo": 0.8, "negativo": 0.75, "neutral": 0.7 }
  "recall": Object,             // { "positivo": 0.78, "negativo": 0.72, "neutral": 0.65 }
  "f1_score": Double,
  "trained_at": ISODate,
  "model_version": String       // Unique
}
```

**Indexes**:
- `{ "model_version": 1 }` — unique, for version lookups

#### State Management

| State | Location | Lifecycle |
|-------|----------|-----------|
| Data files | Docker volume `mongo_data` | Persists across container restarts |
| Indexes | MongoDB engine | Created by FastAPI lifespan on startup; idempotent |
| Collections | MongoDB engine | Created implicitly on first insert |

---

### 1.4 Dashboard (`dashboard/`)

#### Internal Structure

```
dashboard/
├── index.html            # Layout: header, grid of charts, prediction table
├── css/
│   └── styles.css        # Responsive grid, card layout, dark theme
├── js/
│   ├── app.js            # Main entry: init charts, start polling
│   ├── api.js            # fetch wrapper with error handling and retry
│   ├── charts/
│   │   ├── doughnut.js   # Sentiment distribution doughnut
│   │   ├── bar.js        # Average confidence horizontal bar
│   │   ├── line.js       # Prediction volume over time
│   │   ├── radar.js      # Model metrics radar
│   │   └── table.js      # Paginated predictions table
│   └── config.js         # API base URL, refresh interval, chart colors
└── assets/               # Any icons or images (optional)
```

#### Module Details

**`js/app.js`**

```javascript
import { API_BASE, REFRESH_INTERVAL } from './config.js';
import { initDoughnutChart, updateDoughnutChart } from './charts/doughnut.js';
import { initBarChart, updateBarChart } from './charts/bar.js';
import { initLineChart, updateLineChart } from './charts/line.js';
import { initRadarChart, updateRadarChart } from './charts/radar.js';
import { initTable, updateTable } from './charts/table.js';
import { fetchStats, fetchSentiments } from './api.js';

let charts = {};

document.addEventListener('DOMContentLoaded', async () => {
  charts.doughnut = initDoughnutChart();
  charts.bar = initBarChart();
  charts.line = initLineChart();
  charts.radar = initRadarChart();
  initTable();
  
  await refreshData();
  setInterval(refreshData, REFRESH_INTERVAL);  // 10000ms
});

async function refreshData() {
  try {
    const [stats, sentiments] = await Promise.all([
      fetchStats(),
      fetchSentiments({ limit: 10, offset: 0 })
    ]);
    updateDoughnutChart(charts.doughnut, stats.distribution);
    updateBarChart(charts.bar, stats);
    updateLineChart(charts.line, stats.timeseries);
    updateRadarChart(charts.radar, stats);
    updateTable(sentiments.items);
  } catch (error) {
    console.error('Refresh failed:', error);
    // Display offline indicator
    showOfflineBanner();
  }
}
```

**`js/api.js`**

```javascript
import { API_BASE } from './config.js';

const RETRY_ATTEMPTS = 3;
const RETRY_DELAY_MS = 1000;

async function fetchWithRetry(url, options = {}, retries = RETRY_ATTEMPTS) {
  try {
    const response = await fetch(url, options);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  } catch (error) {
    if (retries > 0) {
      await new Promise(resolve => setTimeout(resolve, RETRY_DELAY_MS));
      return fetchWithRetry(url, options, retries - 1);
    }
    throw error;
  }
}

export async function fetchStats() {
  return fetchWithRetry(`${API_BASE}/stats`);
}

export async function fetchSentiments(params = {}) {
  const query = new URLSearchParams(params).toString();
  return fetchWithRetry(`${API_BASE}/sentiments?${query}`);
}
```

- **Context7 (Chart.js)**: Chart types `doughnut`, `bar` (horizontal with `indexAxis: 'y'`), `line`, `radar` are all natively supported. Each requires a `config` object with `type`, `data`, and `options`. Responsive mode is enabled with `responsive: true`. Charts are created via `new Chart(ctx, config)` and updated via `chart.data = newData; chart.update()`.

**Chart configurations** (example for doughnut):

```javascript
import { Chart } from 'chart.js/auto';
import { COLORS } from '../config.js';

export function initDoughnutChart() {
  const ctx = document.getElementById('doughnutChart').getContext('2d');
  return new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Positivo', 'Negativo', 'Neutral'],
      datasets: [{
        data: [0, 0, 0],
        backgroundColor: [COLORS.positivo, COLORS.negativo, COLORS.neutral],
        borderWidth: 2
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { position: 'top' },
        title: { display: true, text: 'Sentiment Distribution' }
      },
      cutout: '60%'
    }
  });
}

export function updateDoughnutChart(chart, distribution) {
  chart.data.datasets[0].data = [
    distribution.positivo || 0,
    distribution.negativo || 0,
    distribution.neutral || 0
  ];
  chart.update();
}
```

#### State Management

| State | Location | Lifecycle |
|-------|----------|-----------|
| Chart instances | In-memory JS variables | Created on `DOMContentLoaded`, updated on poll |
| Cached data | In-memory JS variables | Refreshed every 10s via `setInterval` |
| Offline state | DOM banner element | Shown when fetch fails, hidden on success |

#### Error Handling Strategy

| Error | Strategy |
|-------|----------|
| API unreachable | 3 retries with 1s backoff; show offline banner |
| Malformed response | `try/catch` with console error; keep last good data |
| Chart.js render error | Graceful degradation — hide broken chart, show others |
| Empty dataset | Show "No data yet" placeholder in charts and table |

---

### 1.5 Jenkins Pipeline (`infra/`)

#### Internal Structure

```
infra/
├── Jenkinsfile              # Declarative Pipeline
├── docker-compose.yml       # Production Docker Compose
├── docker-compose.test.yml  # Test profile override
├── .env.example             # Environment template
├── spark/
│   └── Dockerfile           # PySpark training + streaming image
├── api/
│   └── Dockerfile            # FastAPI + PySpark inference image
└── dashboard/
    └── Dockerfile            # Nginx to serve static files (optional, or use FastAPI static mount)
```

#### `Jenkinsfile` Details

```groovy
pipeline {
    agent any
    
    options {
        skipStagesAfterUnstable()  // Gate: don't deploy if tests/lint fail
        timeout(time: 30, unit: 'MINUTES')
    }
    
    environment {
        COMPOSE_PROJECT_NAME = "sentiment-stream-${BUILD_NUMBER}"
        MODEL_VERSION = "v1_${BUILD_NUMBER}"
    }
    
    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }
        
        stage('Build') {
            steps {
                sh 'docker compose build'
            }
        }
        
        stage('Test') {
            steps {
                sh 'docker compose -f docker-compose.test.yml run --rm api pytest api/tests/ -v --tb=short'
                sh 'docker compose -f docker-compose.test.yml run --rm spark pytest spark/tests/ -v --tb=short'
            }
        }
        
        stage('Lint') {
            steps {
                sh 'docker compose run --rm api flake8 api/ --max-line-length=120 --exclude=__pycache__'
                sh 'docker compose run --rm api black --check api/'
            }
        }
        
        stage('Deploy') {
            steps {
                sh 'docker compose up -d'
                // Wait for services to be healthy
                sh '''
                    timeout 60 bash -c 'until curl -s http://localhost:8000/docs > /dev/null; do sleep 2; done'
                '''
            }
        }
    }
    
    post {
        always {
            sh 'docker compose logs --tail=50'
        }
        failure {
            echo 'Pipeline failed! Check logs above.'
        }
        success {
            echo 'Pipeline succeeded! All services healthy.'
        }
    }
}
```

- **Context7 (Jenkins)**: Declarative Pipeline syntax uses `pipeline {}` top-level block. `skipStagesAfterUnstable()` prevents subsequent stages from running if a previous stage is marked UNSTABLE. `agent { dockerfile true }` can be used instead of `agent any` to build from a Dockerfile per stage. `checkout scm` pulls from configured SCM.

---

## 2. Data Flow Diagrams

### 2.1 Training Flow

```
┌─────────────────┐
│  dataset_        │
│  sentimientos_   │
│  500.csv         │
│  (data/ dir)     │
└────────┬────────┘
         │ spark.read.csv(header=True, inferSchema=True)
         │ .dropDuplicates(["texto"])
         ▼
┌─────────────────┐
│  Deduplicated   │
│  DataFrame      │
│  (~30 rows)     │
└────────┬────────┘
         │ pipeline.fit(df)
         │ Pipeline: Tokenizer → StopWordsRemover → HashingTF(500) → IDF → NaiveBayes
         ▼
┌─────────────────┐     ┌──────────────────────┐
│  PipelineModel  │────▸│  /opt/spark/model/    │
│  (trained)      │     │  pipeline_model/      │
│                 │     │  (Docker volume)       │
└────────┬────────┘     └──────────────────────┘
         │ model.transform(df) → evaluation
         ▼
┌─────────────────┐     ┌──────────────────────┐
│  Metrics Dict   │────▸│  MongoDB              │
│  (accuracy, F1,  │     │  model_metrics        │
│   precision,     │     │  collection            │
│   recall)        │     └──────────────────────┘
└─────────────────┘
```

### 2.2 Streaming Flow

```
┌─────────────────┐
│  dataset_        │     spark.readStream
│  sentimientos_   │     .format("csv")
│  500.csv         │     .option("maxFilesPerTrigger", 1)
│  (data/ dir)     │     .trigger(processingTime="5 seconds")
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Streaming      │
│  DataFrame      │──┬── Schema: [texto, etiqueta]
│  (micro-batch)  │  │
└────────┬────────┘  │
         │            │ dropDuplicates(["texto"])
         ▼            │
┌─────────────────┐  │
│  Deduplicated    │◄─┘
│  Streaming DF   │
└────────┬────────┘
         │ model.transform(deduped_df)
         │ (loaded PipelineModel from shared volume)
         ▼
┌─────────────────┐
│  Predictions    │
│  Streaming DF   │── Columns: [original_text, prediction, confidence, model_version]
│                 │
└────────┬────────┘
         │ .writeStream
         │ .foreachBatch(write_batch_to_mongo)
         │ .outputMode("append")
         ▼
┌─────────────────┐
│  MongoDB        │
│  predictions    │── Document: {original_text, prediction, confidence, timestamp, model_version}
│  collection     │
└─────────────────┘
```

### 2.3 API Flow

```
┌────────┐      POST /predict        ┌──────────────┐
│ Client │──────────────────────────>│  FastAPI      │
│        │      {"text": "..."}      │  (lifespan)   │
│        │                            │               │
│        │      GET /sentiments      │  1. Validate input (Pydantic)
│        │      GET /stats            │  2. For /predict:
│        │                            │     run_in_executor(model.transform)
│        │                            │  3. Background task: persist to MongoDB
│        │                            │  4. Return JSON response
│        │◄──────────────────────────│               │
└────────┘      JSON response        └──────┬───────┘
                                            │
                              ┌──────────────┼──────────────┐
                              │              │              │
                              ▼              ▼              ▼
                    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
                    │  Model Volume │  │  MongoDB      │  │  ProcessPool  │
                    │  (PipelineMo- │  │  (Motor async│  │  Executor     │
                    │   del.load()) │  │   driver)    │  │  (CPU-bound)  │
                    └──────────────┘  └──────────────┘  └──────────────┘
```

### 2.4 Dashboard Flow

```
┌─────────────┐     fetch() every 10s      ┌──────────────┐
│  Browser    │──────────────────────────>│  FastAPI      │
│  (JS/HTML/  │  GET /stats               │  /stats       │
│   CSS/      │  GET /sentiments?limit=10 │  /sentiments   │
│   Chart.js) │                            │               │
│             │◄──────────────────────────│               │
│             │      JSON response         └──────┬───────┘
│             │                                     │
│  ┌──────────┴──────────┐                         │
│  │  Chart.js Instances  │                         ▼
│  │  ┌─────────────────┐│                ┌──────────────┐
│  │  │ Doughnut (dist) ││                │  MongoDB      │
│  │  ├─────────────────┤│                │  predictions   │
│  │  │ Bar (conf avg)  ││                │  model_metrics │
│  │  ├─────────────────┤│                └──────────────┘
│  │  │ Line (volume)   ││
│  │  ├─────────────────┤│
│  │  │ Radar (metrics) ││
│  │  ├─────────────────┤│
│  │  │ Table (recent)  ││
│  │  └─────────────────┘│
│  └─────────────────────┘
│
│  Offline Banner (shown on fetch failure)
└─────────────┘
```

---

## 3. Interface Specifications

### 3.1 Spark → Model Volume

| Aspect | Specification |
|--------|--------------|
| **Format** | PySpark `PipelineModel.save()` directory format (metadata + stages parquet) |
| **Path** | `/opt/spark/model/pipeline_model` (inside container, mapped to Docker volume `model_storage`) |
| **Versioning** | Immutable per build; version stored in `model_metrics.model_version`; FastAPI loads latest |
| **Loading** | `PipelineModel.load("/opt/spark/model/pipeline_model")` — Context7: `load()` restores all stage params including `numFeatures`, `smoothing`, `modelType` |
| **Overwrite** | Training script deletes old model before saving: `rm -rf` then `model.save()` |
| **Atomicity** | Model write is not atomic; FastAPI loads model at startup only, not during streaming |

### 3.2 FastAPI → MongoDB

| Aspect | Specification |
|--------|--------------|
| **Driver** | Motor 3.x (`motor.motor_asyncio.AsyncIOMotorClient`) |
| **Connection** | `AsyncIOMotorClient("mongodb://mongodb:27017")` — single client per process |
| **Database** | `sentiment_stream` |
| **Collections** | `predictions`, `model_metrics` |
| **Write Pattern** | `await db.predictions.insert_one({...})` for single; `insert_many()` for batch |
| **Read Patterns** | `find(query).sort().skip().limit()` for paginated; `aggregate()` for stats |
| **Indexes** | Created in lifespan via `await db.predictions.create_index([("timestamp", -1)])` |
| **Schema Validation** | Application-level (Pydantic); MongoDB uses flexible schema |

**Query Patterns**

```python
# GET /sentiments — paginated filter
await db.predictions.find(
    {"prediction": sentiment, "timestamp": {"$gte": date_from, "$lte": date_to}}
).sort("timestamp", -1).skip(offset).limit(limit).to_list(length=limit)

# GET /stats — aggregation
await db.predictions.aggregate([
    {"$group": {"_id": "$prediction", "count": {"$sum": 1}}},
    # ... time-series aggregation
])

# POST /predict — insert one
await db.predictions.insert_one({
    "original_text": text,
    "prediction": label,
    "confidence": prob,
    "timestamp": datetime.utcnow(),
    "model_version": version
})
```

- **Context7 (Motor)**: `AsyncIOMotorClient` creates a connection pool (default 100 connections). `insert_one()` and `insert_many()` are awaitable. `find()` returns an `AsyncIOMotorCursor` that supports `.sort()`, `.skip()`, `.limit()` chaining. `.to_list(length=N)` materializes results. `aggregate()` returns a `MotorCommandCursor`.

### 3.3 FastAPI → Model Volume

| Aspect | Specification |
|--------|--------------|
| **Mount Path** | `/opt/spark/model/pipeline_model` (same Docker volume as Spark service) |
| **Loading Mechanism** | `PipelineModelWrapper.load_from_volume()` called in `lifespan` startup |
| **Cache Strategy** | Loaded once at startup; cached in `app.state.model`; NOT hot-reloaded |
| **Fallback** | If model load fails, FastAPI starts but `/predict` returns 503; `/stats` and `/sentiments` still work |
| **Version Check** | `model_version` stored in `model_metrics` MongoDB collection; validated on startup |

### 3.4 Dashboard → FastAPI

| Endpoint | Method | Request | Response | Poll Interval |
|----------|--------|---------|----------|---------------|
| `/stats` | GET | `?period=day` | `{ distribution, avg_confidence, total, timeseries }` | 10s |
| `/sentiments` | GET | `?limit=10&offset=0` | `{ items, total, limit, offset }` | 10s |
| `/predict` | POST | `{"text": "..."}` | `{ prediction, confidence, timestamp }` | On-demand |

| Aspect | Specification |
|--------|--------------|
| **Polling** | `setInterval(refreshData, 10000)` — not WebSocket |
| **Error Handling** | 3 retries with 1s delay; show offline banner on persistent failure |
| **CORS** | `CORSMiddleware` allowing `http://localhost:*` origins |
| **Content Type** | `application/json` for all endpoints |
| **Static Files** | Dashboard served by FastAPI via `StaticFiles(directory="dashboard")` |

### 3.5 Docker Compose

```yaml
version: "3.8"

services:
  mongodb:
    image: mongo:7.0
    container_name: sentiment-mongodb
    ports:
      - "27017:27017"
    volumes:
      - mongo_data:/data/db
    healthcheck:
      test: ["CMD", "mongosh", "--eval", "db.runCommand({ping:1})"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s
    networks:
      - sentiment-net

  spark:
    build:
      context: .
      dockerfile: infra/spark/Dockerfile
    container_name: sentiment-spark
    volumes:
      - model_storage:/opt/spark/model
      - ./data:/opt/spark/data:ro
      - spark_checkpoints:/opt/spark/checkpoints
    depends_on:
      - mongodb
    environment:
      - MONGO_URI=mongodb://mongodb:27017/sentiment_stream
      - SPARK_MASTER=local[*]
    networks:
      - sentiment-net

  api:
    build:
      context: .
      dockerfile: infra/api/Dockerfile
    container_name: sentiment-api
    ports:
      - "8000:8000"
    volumes:
      - model_storage:/opt/spark/model:ro
    depends_on:
      mongodb:
        condition: service_healthy
    environment:
      - MONGO_URI=mongodb://mongodb:27017
      - MODEL_PATH=/opt/spark/model/pipeline_model
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/docs"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 30s
    networks:
      - sentiment-net

  dashboard:
    build:
      context: .
      dockerfile: infra/dashboard/Dockerfile
    container_name: sentiment-dashboard
    ports:
      - "3000:80"
    depends_on:
      - api
    networks:
      - sentiment-net

volumes:
  mongo_data:
    driver: local
  model_storage:
    driver: local
  spark_checkpoints:
    driver: local

networks:
  sentiment-net:
    driver: bridge
```

- **Context7 (Docker Compose)**: Named volumes (`model_storage`, `mongo_data`) persist data across container restarts and are shared between services by referencing the same volume name. `depends_on` with `condition: service_healthy` waits for the healthcheck to pass before starting the dependent service. `healthcheck` with `test`, `interval`, `timeout`, `retries`, and `start_period` controls container readiness. Bridge networks provide DNS-based service discovery (containers reference each other by service name).

---

## 4. Technology Decisions with Justifications

### 4.1 HashingTF with 500 features (not 1000)

**Decision**: Use `HashingTF(numFeatures=500)` instead of the default 262144 or a larger value.

**Justification**: 
- The dataset contains ~30 unique records after deduplication, with an average text length of ~28 characters.
- With such short texts, the vocabulary size is extremely small (likely <100 unique terms after stop word removal).
- Using 500 features vs. 1000 makes no accuracy difference when vocabulary is <100, but 500 reduces memory footprint and speeds up IDF computation.
- Hashing collisions are negligible at 500 features for a vocabulary of <100 terms (the birthday paradox collision probability is ~10% at 100 terms with 500 features, which is acceptable for an educational project with acknowledged accuracy limitations).
- **Trade-off**: Slightly higher collision probability vs. significantly lower memory/compute. For ~30 samples, the trade-off clearly favors 500.

### 4.2 Motor instead of pymongo

**Decision**: Use Motor (async MongoDB driver) instead of PyMongo (sync driver).

**Justification**:
- FastAPI is an async framework; synchronous database calls block the event loop, degrading concurrent request handling.
- Motor wraps PyMongo and provides awaitable equivalents: `await db.collection.insert_one()`, `await db.collection.find().to_list()`, `await db.collection.aggregate()`.
- **Context7 (Motor)**: `AsyncIOMotorClient` creates a single connection pool per process (default 100 connections). All operations (`insert_one`, `find`, `aggregate`, `create_index`) are fully awaitable and non-blocking.
- PyMongo would require `run_in_executor` for every database call, adding unnecessary complexity.
- **Trade-off**: Slightly higher per-call overhead vs. full async concurrency. For a dashboard polling every 10s and multiple concurrent `/predict` calls, async wins.

### 4.3 Spark Structured Streaming over batch

**Decision**: Use `spark.readStream` with micro-batch triggers instead of `spark.read` batch processing.

**Justification**:
- The assignment explicitly requires demonstrating streaming concepts (Structured Streaming).
- Structured Streaming provides fault tolerance via checkpointing — if the streaming query fails, it can resume from the last checkpoint.
- `foreachBatch` (Context7: PySpark) provides a way to write micro-batch results to arbitrary sinks (MongoDB), which DataStreamWriter does not support natively.
- `trigger(processingTime='5 seconds')` simulates real-time ingestion, processing data in micro-batches.
- `dropDuplicates("texto")` in streaming mode is optimized for streaming — it maintains state across micro-batches using watermarking.
- **Trade-off**: Slightly more complex than batch, but demonstrates streaming competency required by the assignment. Batch could be a fallback if streaming proves problematic.

### 4.4 Lifespan over startup event

**Decision**: Use `asynccontextmanager` lifespan (FastAPI v0.93+) instead of `on_startup`/`on_shutdown` events.

**Justification**:
- **Context7 (FastAPI)**: The `lifespan` parameter is the official recommended approach since v0.93.0. The `on_startup` and `on_shutdown` events are deprecated in newer versions.
- Lifespan provides guaranteed startup-to-shutdown lifecycle: code before `yield` runs before the app accepts requests; code after `yield` runs on shutdown.
- This ensures the ML model is fully loaded and MongoDB indexes are created BEFORE any HTTP request arrives.
- With startup events, there's a race condition: the app may accept requests before the model is loaded.
- **Trade-off**: Slightly more complex syntax (async context manager) vs. simple event handlers. The reliability guarantee is worth it.

### 4.5 Shared volume over S3/MinIO for model artifact

**Decision**: Use a Docker named volume (`model_storage`) for sharing the PipelineModel between Spark and FastAPI containers.

**Justification**:
- The project runs entirely locally via Docker Compose — no cloud infrastructure is available or required.
- A shared volume is the simplest mechanism for file-based handoff between sibling containers on the same host.
- S3/MinIO would require additional infrastructure (a MinIO container, SDK configuration, bucket policies) for no benefit in a single-host deployment.
- The `PipelineModel.save()` and `PipelineModel.load()` APIs (Context7: PySpark) work natively with local filesystem paths. Adding S3 would require `s3a://` URI support and Hadoop AWS JARs.
- **Trade-off**: Volume is limited to single-host deployment. If we needed multi-node Spark, we'd need S3/HDFS. For this educational project, single-host is sufficient.

### 4.6 Jenkins Declarative over Scripted Pipeline

**Decision**: Use Declarative Pipeline syntax with `skipStagesAfterUnstable()`.

**Justification**:
- **Context7 (Jenkins)**: Declarative Pipeline provides a structured, opinionated syntax with `pipeline {}`, `stages {}`, and `steps {}` blocks that are easier to read and maintain.
- `skipStagesAfterUnstable()` (Context7: Jenkins) automatically gates deployment — if the Test stage produces unstable results, Deploy is skipped.
- Declarative syntax is more auditable and enforceable in an educational context — students can visually identify each stage.
- `agent { dockerfile true }` allows building from the repo's Dockerfile, keeping CI/CD consistent with Docker Compose deployment.
- Scripted Pipeline offers more flexibility but is harder to debug and less appropriate for a straightforward Build/Test/Lint/Deploy workflow.
- **Trade-off**: Less flexibility vs. more structure and safety. For a 5-stage pipeline, structure wins.

---

## 5. Error Handling & Resilience

### 5.1 Spark Streaming Failure Recovery

| Scenario | Strategy |
|----------|----------|
| Streaming query crash | Docker `restart: unless-stopped` restarts the container; Structured Streaming resumes from last checkpoint via `checkpointLocation` |
| Micro-batch write failure | `foreachBatch` errors are logged; Spark retries the micro-batch up to 3 times (configurable via `maxOffsetsPerTrigger`) |
| CSV file unavailable | `readStream` with `maxFilesPerTrigger=1` silently waits for new data; no crash |
| Model file missing for streaming | Pre-check in `stream.py`: if model path doesn't exist, log error and exit with non-zero code; Docker restart handles recovery |
| Checkpoint corruption | Remove checkpoint directory and restart (acceptable for educational project) |

**Checkpoint Configuration**:
```python
query = (output.writeStream
    .foreachBatch(write_batch_to_mongo)
    .trigger(processingTime="5 seconds")
    .option("checkpointLocation", "/opt/spark/checkpoints")
    .outputMode("append")
    .start())
```

### 5.2 FastAPI Model Loading Failure

| Scenario | Strategy |
|----------|----------|
| Model file not found at startup | Log error; set `app.state.model = None`; `/predict` returns 503; `/stats` and `/sentiments` continue working |
| Model loading timeout (>60s) | Hardcoded 60s timeout in lifespan; return 503 |
| SparkSession creation fails | Catch `Py4JError` or `SparkException`; log and set model to None |
| Model version mismatch | Compare `model_metadata` version with MongoDB `model_metrics`; log warning if mismatch |

**Fallback Chain**:
```
1. Load PipelineModel from /opt/spark/model/pipeline_model
2. If fails → try loading from /opt/spark/model/pipeline_model_backup (if exists)
3. If fails → start API without model; /predict returns 503; /stats and /sentiments still work
```

### 5.3 MongoDB Connection Retry

| Scenario | Strategy |
|----------|----------|
| First connection in lifespan | Retry 3 times with 2s exponential backoff |
| Connection loss during runtime | Motor auto-reconnects (built into PyMongo/Motor) |
| Write failure in background task | Log error; data lost for that single prediction (acceptable for educational project) |
| Read failure in /stats or /sentiments | Return 500 with detail message |

**Lifespan Retry Logic**:
```python
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def connect_with_retry(uri: str, retries: int = 3, delay: float = 2.0):
    for attempt in range(retries):
        try:
            client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
            await client.server_info()  # Verify connection
            return client
        except Exception as e:
            if attempt < retries - 1:
                await asyncio.sleep(delay * (2 ** attempt))
            else:
                raise
```

### 5.4 Dashboard Offline Handling

| Scenario | Strategy |
|----------|----------|
| API unreachable | `fetchWithRetry` with 3 retries and 1s exponential backoff |
| Persistent failure | Show offline banner: `⚠ Connection lost. Retrying...` |
| Empty data from API | Show "No data yet" in charts and "Waiting for predictions..." in table |
| Malformed JSON | `try/catch` around `response.json()`; keep last good data |

**Offline Banner Implementation**:
```javascript
function showOfflineBanner() {
  document.getElementById('offline-banner').style.display = 'block';
}

function hideOfflineBanner() {
  document.getElementById('offline-banner').style.display = 'none';
}
```

---

## 6. Security Considerations

### 6.1 MongoDB Authentication

| Aspect | Decision |
|--------|----------|
| Auth mode | No authentication (development only) |
| Justification | Local Docker network only; no external access; educational project |
| Network isolation | `sentiment-net` bridge network; only published ports are 3000 (dashboard) and 8000 (API); MongoDB port 27017 is published for local development only |
| Production recommendation | Enable `--auth` with `MONGO_INITDB_ROOT_USERNAME`/`MONGO_INITDB_ROOT_PASSWORD` env vars; use connection string `mongodb://user:pass@mongodb:27017` |

**Docker Compose Security**:
```yaml
mongodb:
  # DO NOT expose 27017 in production
  # ports:
  #   - "27017:27017"  # Only for local development
  networks:
    - sentiment-net
  # No external access — only internal API and Spark services can connect
```

### 6.2 API Validation & Sanitization

| Aspect | Implementation |
|--------|---------------|
| Input validation | Pydantic `PredictRequest` model with `min_length=1`, `max_length=1000` |
| Text sanitization | Strip whitespace; reject null bytes; HTML-encode output |
| Rate limiting | NOT implemented (educational project); recommended: `slowapi` with per-IP limits |
| Response headers | `X-Content-Type-Options: nosniff`; `Content-Type: application/json` |
| CORS | Allow `http://localhost:*` origins only (dev); `https://domain.com` in production |

**Validation Example**:
```python
from pydantic import BaseModel, Field, validator
import re

class PredictRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000)
    
    @validator('text')
    def sanitize_text(cls, v):
        v = v.strip()
        if '\x00' in v:
            raise ValueError('Null bytes not allowed')
        return v
```

### 6.3 CORS Configuration

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

---

## 7. Testing Strategy

### 7.1 Unit Tests

#### Spark Unit Tests (`spark/tests/`)

| Test | What It Verifies |
|------|------------------|
| `test_pipeline_stages` | Pipeline stages produce expected column names after each transformation |
| `test_tokenizer` | `Tokenizer` splits text into word arrays |
| `test_stopwords_remover` | `StopWordsRemover` removes English stop words |
| `test_hashing_tf` | `HashingTF` produces correct vector size (500 features) |
| `test_naive_bayes` | NaiveBayes produces predictions with valid labels |
| `test_model_save_load` | `PipelineModel.save()` and `load()` roundtrip correctly |
| `test_train_and_evaluate` | Training produces metrics dict with all required keys |

#### FastAPI Unit Tests (`api/tests/`)

| Test | What It Verifies |
|------|------------------|
| `test_predict_valid_text` | `/predict` returns valid prediction for normal input |
| `test_predict_empty_text` | `/predict` returns 422 for empty text |
| `test_predict_long_text` | `/predict` returns 422 for text >1000 chars |
| `test_predict_model_not_loaded` | `/predict` returns 503 when model is None |
| `test_sentiments_pagination` | `/sentiments` respects limit, offset, and sentiment filters |
| `test_stats_distribution` | `/stats` returns correct distribution keys |
| `test_stats_timeseries` | `/stats` returns timeseries with correct structure |

**Test Fixtures (`conftest.py`)**:
```python
import pytest
from httpx import AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient
from api.main import app

@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.fixture
async def mock_db():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["sentiment_stream_test"]
    yield db
    await db.drop_collection("predictions")
    await db.drop_collection("model_metrics")
    client.close()
```

#### Dashboard Unit Tests

| Test | What It Verifies |
|------|------------------|
| `test_api_fetch_retry` | `fetchWithRetry` retries 3 times before throwing |
| `test_api_fetch_success` | `fetchWithRetry` returns data on first successful response |
| `test_config_values` | `API_BASE` and `REFRESH_INTERVAL` are correct |

### 7.2 Integration Tests

| Test | What It Verifies | How |
|------|-------------------|-----|
| Spark → MongoDB | Streaming writes predictions to MongoDB | Run streaming for 15s; query MongoDB for documents |
| FastAPI → MongoDB | API writes and reads predictions | Start API; POST `/predict`; GET `/sentiments`; verify data in MongoDB |
| Spark model → FastAPI | Shared volume model handoff | Train model; load in FastAPI; `/predict` returns valid result |
| Dashboard → API | Dashboard fetches and renders data | Start dashboard; verify `fetch()` calls return valid data |

**Docker Compose Test Profile** (`docker-compose.test.yml`):
```yaml
services:
  api:
    environment:
      - MONGO_URI=mongodb://mongodb:27017
      - TESTING=true
    command: pytest api/tests/ -v --tb=short
```

### 7.3 End-to-End Tests

| Test | What It Verifies | How |
|------|-------------------|-----|
| Full pipeline | CSV → Spark processing → MongoDB predictions | `docker compose up`; wait 30s; query MongoDB for >=1 prediction |
| API prediction | Client → POST /predict → MongoDB → response | `curl -X POST /predict -d '{"text":"test"}'`; verify response and MongoDB document |
| Dashboard refresh | Browser → fetch → charts update | Manual verification: open dashboard, wait 10s, verify chart data changes |

**Jenkins E2E Test Stage**:
```groovy
stage('E2E Test') {
    steps {
        sh '''
            docker compose up -d
            sleep 30
            # Wait for API health
            timeout 60 bash -c 'until curl -sf http://localhost:8000/docs > /dev/null; do sleep 2; done'
            # Test API
            curl -sf http://localhost:8000/stats
            curl -sf -X POST http://localhost:8000/predict -H "Content-Type: application/json" -d '{"text":"test"}'
            # Test dashboard
            curl -sf http://localhost:3000/
        '''
    }
}
```

---

## 8. File Structure

```
sentiment-stream/
│
├── data/
│   ├── dataset_sentimientos_500.csv    # RAW CSV — never modified
│   └── processed/                        # Deduplicated dataset (generated by Spark)
│       └── deduplicated.csv
│
├── spark/
│   ├── __init__.py
│   ├── config.py                         # Constants, env vars, SparkSession factory
│   ├── pipeline.py                       # build_pipeline(): Tokenizer → NB
│   ├── train.py                          # train_model(): load CSV → train → save model + metrics
│   ├── stream.py                         # start_streaming(): Structured Streaming entry point
│   ├── sink.py                           # write_batch_to_mongo(): foreachBatch function
│   └── tests/
│       ├── __init__.py
│       ├── test_pipeline.py              # Unit: pipeline stages and column names
│       ├── test_train.py                # Unit: training produces saved model
│       └── test_stream.py               # Unit: foreachBatch writes correct docs
│
├── api/
│   ├── __init__.py
│   ├── main.py                           # FastAPI app with lifespan, CORS, router mount
│   ├── config.py                         # Pydantic Settings (MONGO_URI, MODEL_PATH, etc.)
│   ├── dependencies.py                   # Dependency injection (db, model)
│   ├── models.py                         # Pydantic request/response schemas
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── predict.py                   # POST /predict endpoint
│   │   ├── sentiments.py                # GET /sentiments endpoint
│   │   └── stats.py                     # GET /stats endpoint
│   ├── services/
│   │   ├── __init__.py
│   │   ├── inference.py                 # PipelineModelWrapper, run_in_executor predict
│   │   └── repository.py               # Motor MongoDB operations (CRUD + aggregation)
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py                  # Fixtures: mock model, mock db, test client
│       ├── test_predict.py             # Unit: /predict endpoint
│       ├── test_sentiments.py          # Unit: /sentiments endpoint
│       └── test_stats.py               # Unit: /stats endpoint
│
├── dashboard/
│   ├── index.html                        # Layout: header, grid, table
│   ├── css/
│   │   └── styles.css                   # Responsive grid, cards, dark theme, offline banner
│   ├── js/
│   │   ├── app.js                       # Main entry: init charts, start polling
│   │   ├── api.js                       # fetchWithRetry, API functions
│   │   ├── config.js                    # API_BASE_URL, REFRESH_INTERVAL, COLORS
│   │   └── charts/
│   │       ├── doughnut.js             # Sentiment distribution
│   │       ├── bar.js                  # Average confidence by sentiment
│   │       ├── line.js                 # Prediction volume over time
│   │       ├── radar.js                # Model metrics (accuracy, precision, recall, F1)
│   │       └── table.js                # Paginated predictions table
│   └── assets/                          # Icons, logos (optional)
│
├── infra/
│   ├── Jenkinsfile                       # Declarative Pipeline: Checkout → Build → Test → Lint → Deploy
│   ├── docker-compose.yml               # Production stack
│   ├── docker-compose.test.yml          # Test override profile
│   ├── .env.example                     # Environment variable template
│   ├── spark/
│   │   └── Dockerfile                   # PySpark 3.5.6 + MongoDB connector
│   ├── api/
│   │   └── Dockerfile                   # Python 3.11 + FastAPI + PySpark (inference)
│   └── dashboard/
│       └── Dockerfile                   # Nginx alpine (or Caddy) for static files
│
├── openspec/
│   └── changes/
│       └── init-architecture/
│           ├── proposal.md
│           ├── spec.md
│           ├── design.md                 # ← This file
│           └── tasks.md                  # (to be created)
│
├── .gitignore
├── .env                                 # Environment variables (gitignored)
├── README.md
└── requirements.txt                      # Python dependencies (pyspark, fastapi, motor, etc.)
```

---

## Appendix A: Context7 API References

| Technology | Version | Key APIs Referenced |
|-----------|---------|-------------------|
| PySpark MLlib | 3.5.x | `Tokenizer`, `StopWordsRemover`, `HashingTF(numFeatures)`, `IDF`, `NaiveBayes(smoothing, modelType)`, `PipelineModel.save()/load()`, `Pipeline(stages=[])`, `MulticlassClassificationEvaluator` |
| PySpark Streaming | 3.5.x | `spark.readStream.format("csv")`, `DataStreamWriter.foreachBatch()`, `trigger(processingTime)`, `dropDuplicates()`, `outputMode("append")` |
| FastAPI | v0.115+ | `lifespan` async context manager (replaces startup/shutdown events), `BackgroundTasks`, `run_in_executor` |
| Motor | 3.x | `AsyncIOMotorClient`, `await collection.insert_one()`, `await collection.find().to_list()`, `await collection.create_index()`, `await collection.aggregate()` |
| Docker Compose | v2+ | Named volumes, `depends_on.condition: service_healthy`, `healthcheck`, bridge networks |
| Jenkins | 2.400+ | Declarative Pipeline: `pipeline {}`, `stages {}`, `skipStagesAfterUnstable()`, `agent { dockerfile true }` |
| Chart.js | v3.9+ | `new Chart(ctx, config)`, chart types: `doughnut`, `bar` (horizontal), `line`, `radar`, `responsive: true`, `chart.update()` |

## Appendix B: Environment Variables

| Variable | Default | Service | Description |
|----------|---------|---------|-------------|
| `MONGO_URI` | `mongodb://mongodb:27017` | api, spark | MongoDB connection string |
| `MONGO_DB` | `sentiment_stream` | api, spark | Database name |
| `MODEL_PATH` | `/opt/spark/model/pipeline_model` | api, spark | Model artifact path (shared volume) |
| `SPARK_MASTER` | `local[*]` | spark | Spark master URL |
| `CSV_PATH` | `/opt/spark/data/dataset_sentimientos_500.csv` | spark | CSV dataset path |
| `NUM_FEATURES` | `500` | spark | HashingTF feature count |
| `TRIGGER_INTERVAL` | `5 seconds` | spark | Streaming micro-batch interval |
| `HOST` | `0.0.0.0` | api | FastAPI host |
| `PORT` | `8000` | api | FastAPI port |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:8080` | api | Allowed CORS origins |
| `REFRESH_INTERVAL` | `10000` | dashboard | Dashboard polling interval (ms) |
| `API_BASE_URL` | `http://api:8000` | dashboard | API endpoint for dashboard fetch |