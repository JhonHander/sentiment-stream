# Sentiment-Stream — Deployment Guide

> Step-by-step instructions for deploying the Sentiment Stream stack with Docker Compose and Jenkins.

---

## 1. Docker Compose Deployment

### 1.1 Prerequisites

- Docker Engine 24.0+ (with Docker Compose v2.0+)
- 4 GB RAM available to Docker (PySpark requires significant memory)
- Ports `80`, `8000`, `8080`, `8081`, `27017` free on the host

### 1.2 Environment Variables

Create a `.env` file in the project root (or export variables manually):

```bash
# MongoDB
MONGO_URI=mongodb://mongodb:27017
MONGO_DB=sentiment_stream

# API
API_PORT=8000
MODEL_PATH=/app/model

# Dashboard
DASHBOARD_PORT=80

# Spark
SPARK_MASTER_PORT=8080
SPARK_WORKER_PORT=8081
SPARK_MASTER_URL=spark://spark-master:7077

# Compose
COMPOSE_PROJECT_NAME=sentiment-stream
```

> **Note:** The repository includes `infra/.env.example` as a template.

### 1.3 Production Startup

```bash
# 1. Navigate to project root
cd sentiment-stream

# 2. Build images (first time or after code changes)
docker compose -f infra/docker-compose.yml build

# 3. Start all services in detached mode
docker compose -f infra/docker-compose.yml up -d

# 4. Verify health
watch docker compose -f infra/docker-compose.yml ps

# 5. Train the model (run once before streaming)
docker compose -f infra/docker-compose.yml run --rm spark-master \
    python -m spark.train

# 6. Start streaming
docker compose -f infra/docker-compose.yml run --rm spark-master \
    python -m spark.stream
```

### 1.4 Service URLs

| Service | URL | Description |
|---|---|---|
| Dashboard | `http://localhost` | Real-time visualizations |
| API Docs | `http://localhost:8000/docs` | Swagger UI |
| API Health | `http://localhost:8000/health` | Health probe |
| Spark Master UI | `http://localhost:8080` | Spark cluster status |
| Spark Worker UI | `http://localhost:8081` | Worker status |

### 1.5 Stopping the Stack

```bash
# Graceful stop (preserves volumes)
docker compose -f infra/docker-compose.yml down

# Full reset (removes volumes and data)
docker compose -f infra/docker-compose.yml down -v
```

### 1.6 Logs

```bash
# All services
docker compose -f infra/docker-compose.yml logs -f

# Specific service
docker compose -f infra/docker-compose.yml logs -f api
```

---

## 2. Jenkins CI/CD Pipeline

### 2.1 Prerequisites

- Jenkins 2.400+ with the following plugins:
  - **Docker Pipeline**
  - **Pipeline Stage View**
  - **Git**

### 2.2 Jenkinsfile Overview

The pipeline (`infra/Jenkinsfile`) implements a 5-stage declarative workflow:

```groovy
pipeline {
    agent any
    options {
        skipStagesAfterUnstable()
        timeout(time: 30, unit: 'MINUTES')
    }
    stages {
        stage('Checkout') { ... }
        stage('Build')    { ... }
        stage('Test')     { ... }
        stage('Lint')     { ... }
        stage('Deploy')   { ... }
    }
}
```

**Gating:** `skipStagesAfterUnstable()` ensures that if Test or Lint fails, Deploy is skipped.

### 2.3 Jenkins Job Setup

1. **New Item** → **Pipeline** → Name: `sentiment-stream`
2. **Pipeline** section → **Definition:** `Pipeline script from SCM`
3. **SCM:** Git → Repository URL: `https://github.com/<user>/sentiment-stream.git`
4. **Script Path:** `infra/Jenkinsfile`
5. **Save**

### 2.4 Jenkins Agent Requirements

The agent must have:
- Docker installed and the `jenkins` user in the `docker` group
- Docker Compose v2.0+
- At least 4 GB RAM
- Ports 80, 8000 available (or modify `infra/docker-compose.yml`)

### 2.5 Pipeline Variables

You can override behavior via Jenkins environment variables:

| Variable | Default | Description |
|---|---|---|
| `COMPOSE_PROJECT_NAME` | `sentiment-stream-${BUILD_NUMBER}` | Compose project isolation |
| `MODEL_VERSION` | `v1_${BUILD_NUMBER}` | Model version tag |

---

## 3. Environment Variables Reference

### API Service

| Variable | Default | Description |
|---|---|---|
| `MONGO_URI` | `mongodb://mongodb:27017` | MongoDB connection string |
| `MONGO_DB` | `sentiment_stream` | Database name |
| `MODEL_PATH` | `/app/model` | Path to saved PipelineModel |

### Spark Service

| Variable | Default | Description |
|---|---|---|
| `MONGO_URI` | `mongodb://mongodb:27017/sentiment_stream` | MongoDB URI with DB name |
| `CSV_PATH` | `/app/data/dataset_sentimientos_500.csv` | Input dataset path |
| `MODEL_PATH` | `/app/model` | Output model path |
| `SPARK_MODE` | `master` / `worker` | Spark runtime mode |

### MongoDB Service

| Variable | Default | Description |
|---|---|---|
| `MONGO_INITDB_DATABASE` | `sentiment_stream` | Initial database created on first start |

---

## 4. Production Considerations

### 4.1 Security

- **Do not expose MongoDB port (`27017`) to the public internet.** The current `docker-compose.yml` binds it to `0.0.0.0` for local development. In production, remove the `ports:` section or restrict to `127.0.0.1:27017:27017`.
- **Enable MongoDB authentication** by setting `MONGO_INITDB_ROOT_USERNAME` and `MONGO_INITDB_ROOT_PASSWORD`.
- **Use HTTPS** in front of the FastAPI service (e.g., Traefik, Nginx reverse proxy, or cloud load balancer).
- **Restrict CORS origins** in `api/config.py` instead of `allow_origins=["*"]`.

### 4.2 Scaling

- **API:** Scale horizontally by running multiple API containers behind a load balancer. Ensure the `model_storage` volume is shared (e.g., NFS) or switch to S3/MinIO for model artifacts.
- **Spark:** Increase worker count in `docker-compose.yml` or migrate to a managed Spark cluster (e.g., AWS EMR, Databricks).
- **MongoDB:** For production workloads, replace the single MongoDB container with a MongoDB Atlas cluster or a replica set deployment.

### 4.3 Monitoring

- **Health checks** are built into Docker Compose for MongoDB, API, and Dashboard.
- **FastAPI `/health`** can be used by external monitoring tools (e.g., UptimeRobot, Datadog).
- **Jenkins pipeline logs** are archived automatically via the `post { always { ... } }` block.

### 4.4 Backup

- **MongoDB data:** The `mongo-data` volume contains all persistent data. Back it up regularly:
  ```bash
  docker run --rm -v sentiment-stream_mongo-data:/data -v $(pwd):/backup alpine tar czf /backup/mongo-backup.tar.gz -C /data .
  ```
- **Model artifacts:** The `model_storage` volume contains the trained PipelineModel. Back it up alongside MongoDB data.

### 4.5 Known Limitations

- The dataset is extremely small (~30 unique samples). Do not use this model for production sentiment analysis.
- PySpark startup in the API container adds ~10–20 seconds to container boot time.
- The dashboard polls via HTTP every 10 seconds; for high-frequency real-time needs, consider WebSockets or Server-Sent Events.

---

## 5. Troubleshooting Deployment Issues

| Symptom | Cause | Fix |
|---|---|---|
| `Modelo no disponible` (503) | Training not run | Execute `spark/train.py` before starting the API |
| MongoDB connection refused | Healthcheck not yet passed | Wait for `mongodb` status = `healthy` in `docker compose ps` |
| Spark worker cannot connect | Master not ready | Ensure `spark-master` starts before `spark-worker` via `depends_on` |
| Dashboard blank page | API unreachable | Check `http://localhost:8000/health`; verify CORS settings |
| Out of memory | Docker memory limit too low | Allocate ≥4 GB RAM to Docker Desktop / daemon |
| Radar chart empty | No model metrics | Run training to populate `model_metrics` collection |
| Jenkins deploy stage fails | Ports already in use | Stop local stack: `docker compose -f infra/docker-compose.yml down` |
