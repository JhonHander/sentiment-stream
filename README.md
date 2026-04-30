# Sentiment-Stream

> End-to-end sentiment analysis pipeline using PySpark MLlib, FastAPI, MongoDB, and Docker Compose.

## Architecture Overview

```text
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Browser       │────▶│  Dashboard      │────▶│  FastAPI        │
│  (Chart.js)     │◄────│  (nginx:80)     │◄────│  (Python 3.11)  │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                              ┌──────────────────────────┼──────────┐
                              │                          │          │
                              ▼                          ▼          ▼
                       ┌──────────────┐          ┌──────────────┐  ┌──────────────┐
                       │  MongoDB     │          │  PySpark     │  │  ProcessPool │
                       │  (Document   │          │  Pipeline    │  │  Executor    │
                       │   Store)     │          │  Model       │  │              │
                       └──────────────┘          └──────────────┘  └──────────────┘
                              ▲
                              │
                       ┌──────┴──────┐
                       │  Spark       │
                       │  (Training + │
                       │   Streaming) │
                       └──────────────┘
```

## Components

1. **Spark Pipeline** (`spark/`): Data ingestion, ML model training with PySpark MLlib, and Structured Streaming predictions.
2. **FastAPI Backend** (`api/`): REST API for on-demand predictions, sentiment queries, statistics, and model metrics.
3. **MongoDB** (`infra/`): Document store for predictions and model metrics.
4. **Dashboard** (`dashboard/`): Vanilla HTML/CSS/JS frontend with Chart.js visualizations.
5. **Infrastructure** (`infra/`): Docker Compose stack and Jenkins CI/CD pipeline.

## Prerequisites

- Docker Engine 24.0+
- Docker Compose v2.0+
- Python 3.11+ (for local development)
- (Optional) Jenkins 2.400+ for CI/CD

## Quick Start

```bash
# 1. Clone or navigate to the project directory
cd sentiment-stream

# 2. Build and start all services
docker compose -f infra/docker-compose.yml up -d

# 3. Wait for MongoDB to be healthy (~15s), then run training
docker compose -f infra/docker-compose.yml run --rm spark-master \
    python -m spark.train

# 4. Start streaming
docker compose -f infra/docker-compose.yml run --rm spark-master \
    python -m spark.stream

# 5. Open the dashboard at http://localhost
# 6. API docs are available at http://localhost:8000/docs
```

## API Summary

| Endpoint | Method | Description |
|---|---|---|
| `/predict` | POST | Predict sentiment for a given text |
| `/sentiments` | GET | Paginated list of predictions with filters |
| `/stats` | GET | Sentiment distribution, avg confidence, time series |
| `/model-metrics` | GET | Per-class precision, recall, and F1-score |
| `/health` | GET | Service health check |
| `/docs` | GET | Auto-generated OpenAPI (Swagger UI) |

### Example Requests

**Predict sentiment:**
```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"text": "I love this product"}'
```

**List latest predictions:**
```bash
curl "http://localhost:8000/sentiments?limit=10&offset=0"
```

**Get statistics:**
```bash
curl "http://localhost:8000/stats?period=hour"
```

**Get model metrics:**
```bash
curl "http://localhost:8000/model-metrics"
```

## Dashboard Features

- **Doughnut Chart**: Real-time sentiment distribution (positivo / negativo / neutral).
- **Horizontal Bar Chart**: Average confidence by sentiment class.
- **Line Chart**: Prediction volume over time.
- **Radar Chart**: Model performance metrics — precision, recall, and F1-score per class.
- **Predictions Table**: Paginated, searchable list of recent predictions.
- **Auto-refresh**: Polls the API every 10 seconds.
- **Offline banner**: Shown when the API is unreachable, with automatic retry.
- **Keyboard shortcuts**: `R` to refresh, `P` to toggle auto-refresh.

## Dataset Limitations

> This project is designed for **educational and demonstration purposes**.

- **Dataset quality**: The source CSV (`dataset_sentimientos_500.csv`) contains ~500 rows but ~94% are duplicates, leaving only ~30 unique records after deduplication.
- **Text length**: Average text length is approximately 28 characters, which limits the vocabulary and may reduce model accuracy.
- **Language mismatch**: Texts are in English while labels are in Spanish (`positivo`, `negativo`, `neutral`).
- **Stop words**: Default English stop words are used; this may not optimally filter all irrelevant tokens.
- **Model accuracy**: With only ~30 unique samples, the trained model is suitable for demonstration and educational purposes but should not be used for production sentiment analysis.

## Jenkins Pipeline

A declarative Jenkins pipeline is provided in `infra/Jenkinsfile`.

**Stages:**
1. **Checkout** — Pull latest code.
2. **Build** — Build Docker images.
3. **Test** — Run pytest suite inside containers.
4. **Lint** — Run `flake8` and `black --check`.
5. **Deploy** — Start services via `docker compose up -d`.

The pipeline uses `skipStagesAfterUnstable()` to prevent deployment if tests or linting fail.

**Setup:**
1. Install Jenkins with Docker Pipeline plugin.
2. Create a new Pipeline job pointing to your repository.
3. Set the pipeline script path to `infra/Jenkinsfile`.

## Development

```bash
# Install test dependencies
pip install -e ".[test,dev]"

# Run unit tests
pytest tests/test_api/ -v

# Run integration test
bash tests/integration/test_docker_compose.sh

# Lint
flake8 spark/ api/ tests/ --max-line-length=120 --exclude=__pycache__

# Format
black spark/ api/ tests/
```

## Troubleshooting

| Problem | Solution |
|---|---|
| `Modelo no disponible` (503) | Run training first: `docker compose run --rm spark-master python -m spark.train` |
| MongoDB connection refused | Wait for healthcheck: `docker compose ps` should show mongodb as `healthy` |
| Dashboard shows "Sin conexión" | Verify API is running: `curl http://localhost:8000/health` |
| PySpark out of memory | Increase Docker memory limit to at least 4 GB |
| Radar chart empty | Training metrics are missing; run `spark/train.py` to populate `model_metrics` |

## License

Educational project — Big Data / Data Engineering course.
