# Exploration Report: Sentiment-Stream Project

## Project Overview

**Project Name:** sentiment-stream  
**Type:** University Big Data/Data Engineering Assignment  
**Artifact Store:** openspec  
**Date:** 2025-04-29

---

## 1. Dataset Analysis

### 1.1 Dataset Structure

**File:** `dataset_sentimientos_500.csv`  
**Format:** CSV with UTF-8 encoding  
**Size:** 502 records (503 lines including header)

**Columns:**
| Column | Type | Description |
|--------|------|-------------|
| `texto` | String | Text content for sentiment analysis |
| `etiqueta` | Categorical | Sentiment label (positivo/negativo/neutral) |

**⚠️ Data Quality Issues Identified:**
1. **High duplication rate:** 472 duplicate texts out of 502 records (94% duplicates)
2. **English language content:** Despite Spanish labels, all text is in English
3. **Short texts:** Average 28.3 characters per text (very short for robust ML)
4. **No ID column:** No unique identifier as mentioned in requirements
5. **No timestamp:** Missing `fecha` column mentioned in requirements

### 1.2 Class Distribution

The dataset is perfectly balanced across three sentiment classes:

| Class | Count | Percentage |
|-------|-------|------------|
| positivo | 168 | 33.5% |
| negativo | 167 | 33.3% |
| neutral | 167 | 33.3% |

### 1.3 Text Characteristics

- **Min length:** 19 characters
- **Max length:** 38 characters
- **Average length:** 28.3 characters
- **Language:** English (despite Spanish column names)

**Sample Texts:**
- *positivo:* "Amazing experience with the service"
- *negativo:* "I would not recommend it"
- *neutral:* "The file was uploaded successfully"

---

## 2. Current Project State

### 2.1 Existing Files

```
/home/jhonh/Code/iue/sentiment-stream/
├── .atl/
│   └── skill-registry.md       # Agent team conventions
└── dataset_sentimientos_500.csv # Training dataset
```

### 2.2 Missing Components (All Required)

| Component | Status | Priority |
|-----------|--------|----------|
| Ingestion Layer | ❌ Not present | High |
| Processing Layer (PySpark) | ❌ Not present | High |
| Persistence Layer (MongoDB) | ❌ Not present | High |
| API Layer (FastAPI) | ❌ Not present | High |
| Dashboard (HTML/CSS/JS) | ❌ Not present | Medium |
| Docker Compose | ❌ Not present | High |
| Jenkins CI/CD | ❌ Not present | Medium |
| Documentation | ❌ Not present | Medium |

---

## 3. Technical Stack Assessment

### 3.1 Recommended Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATA FLOW                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────────┐     ┌─────────────────┐     ┌─────────────┐   │
│   │  CSV File   │────▶│  Spark Streaming│────▶│  MongoDB    │   │
│   │ (Dataset)   │     │  (Micro-batch)  │     │ (Predictions│   │
│   └─────────────┘     └─────────────────┘     └──────┬──────┘   │
│           │                    │                      │          │
│           │                    ▼                      ▼          │
│           │           ┌─────────────────┐     ┌─────────────┐   │
│           │           │  ML Pipeline    │     │   FastAPI   │   │
│           │           │  (Naive Bayes)  │     │  (REST API) │   │
│           │           └─────────────────┘     └──────┬──────┘   │
│           │                                          │          │
│           ▼                                          ▼          │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │               HTML/CSS/JS Dashboard                       │  │
│   │         (Charts: Distribution, Trends, Table)            │  │
│   └──────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Technology Deep Dive

#### 3.2.1 Ingestion Layer Options

**Option A: Socket Simulation (Python socket)**
- **Pros:** Simple to implement, good for educational purposes, direct control over streaming rate
- **Cons:** Not production-grade, requires custom client code, limited scalability
- **Effort:** Low

**Option B: Spark Structured Streaming (Micro-batch)**
- **Pros:** Production-grade, built-in fault tolerance, integrates seamlessly with ML pipeline
- **Cons:** More complex setup, requires Spark cluster understanding
- **Effort:** Medium

**Recommendation:** Option B (Spark Structured Streaming) - aligns better with Big Data course objectives and provides real-world experience.

#### 3.2.2 Processing Layer (PySpark)

**Pipeline Stages:**

1. **Text Cleaning**
   - Lowercase conversion
   - Remove special characters/punctuation
   - Handle duplicates

2. **Tokenization**
   ```python
   from pyspark.ml.feature import Tokenizer
   tokenizer = Tokenizer(inputCol="texto", outputCol="palabras")
   ```

3. **Stop Words Removal**
   ```python
   from pyspark.ml.feature import StopWordsRemover
   remover = StopWordsRemover(inputCol="palabras", outputCol="filtrado")
   ```

4. **Feature Extraction (TF-IDF)**
   ```python
   from pyspark.ml.feature import HashingTF, IDF
   hashingTF = HashingTF(inputCol="filtrado", outputCol="rawFeatures", numFeatures=1000)
   idf = IDF(inputCol="rawFeatures", outputCol="features")
   ```

5. **Classification (Naive Bayes)**
   ```python
   from pyspark.ml.classification import NaiveBayes
   nb = NaiveBayes(smoothing=1.0, modelType="multinomial")
   ```

**Model Persistence:** Save trained model for API inference

#### 3.2.3 Persistence Layer (MongoDB)

**Schema Design:**
```json
{
  "_id": ObjectId,
  "texto": "string",
  "prediccion": "string",  // positivo/negativo/neutral
  "confianza": "double",
  "timestamp": ISODate,
  "modelo_version": "string"
}
```

**Why MongoDB:**
- Schema flexibility for evolving prediction formats
- Excellent Python driver (pymongo)
- Docker-friendly
- Sufficient for 500 records + real-time predictions

#### 3.2.4 API Layer (FastAPI)

**Required Endpoints:**

| Endpoint | Method | Description | Query Params |
|----------|--------|-------------|--------------|
| `/sentiments` | GET | List predictions with filters | `sentiment`, `start_date`, `end_date`, `limit` |
| `/stats` | GET | Class distribution & metrics | `period` (day/week/month) |
| `/predict` | POST | Inference on new text | Body: `{ "texto": "..." }` |

**Architecture Pattern:**
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load ML model on startup
    ml_model = load_model("/models/sentiment_model")
    yield
    # Cleanup
```

**Async Considerations:**
- PySpark is CPU-bound (use `run_in_executor` for async API)
- MongoDB operations can be async with `motor` library

#### 3.2.5 Dashboard (HTML/CSS/JS)

**Recommended Libraries:**
- **Charting:** Chart.js (simple, professional) or D3.js (advanced)
- **Styling:** Bootstrap 5 or Tailwind CSS
- **Data Fetching:** Fetch API or Axios

**Dashboard Components:**
1. **Sentiment Distribution Pie/Bar Chart**
2. **Temporal Trends Line Chart** (Note: dataset has no dates - use prediction timestamp)
3. **Recent Predictions Table** (paginated, sortable)
4. **Prediction Form** (input text, get prediction)

**Architecture:**
- Static HTML/CSS/JS served via FastAPI static files
- OR separate lightweight web server (nginx)

#### 3.2.6 Infrastructure (Docker Compose)

**Services Required:**

```yaml
services:
  mongodb:
    image: mongo:7.0
    ports: ["27017:27017"]
    volumes: ["mongo_data:/data/db"]
  
  spark-master:
    image: bitnami/spark:3.5.0
    environment:
      - SPARK_MODE=master
  
  spark-worker:
    image: bitnami/spark:3.5.0
    environment:
      - SPARK_MODE=worker
      - SPARK_MASTER_URL=spark://spark-master:7077
  
  api:
    build: ./api
    ports: ["8000:8000"]
    depends_on: [mongodb]
  
  dashboard:
    build: ./dashboard
    ports: ["8080:80"]
```

#### 3.2.7 CI/CD (Jenkins)

**Pipeline Stages:**
1. Checkout
2. Install dependencies
3. Run tests (pytest for API, Spark tests)
4. Build Docker images
5. Push to registry
6. Deploy (optional for assignment)

---

## 4. Key Challenges & Decisions

### 4.1 Critical Challenges

| Challenge | Impact | Mitigation |
|-----------|--------|------------|
| **94% duplicate data** | Model will overfit to few examples | Data augmentation, deduplication, or accept as educational limitation |
| **Very short texts** (avg 28 chars) | Limited feature extraction, lower accuracy | Use bigrams/trigrams, lower HashingTF features |
| **English text/Spanish labels** | Confusion for Spanish sentiment analysis | Acknowledge in documentation, or translate dataset |
| **No timestamps in data** | Cannot show true temporal trends | Use prediction timestamp instead |
| **Single-machine Spark** | Not truly "Big Data" | Accept as educational demo, use local[*] mode |

### 4.2 Architectural Decisions Required

**Decision 1: How to handle streaming?**
- **Option A:** Simulate with socket + Python client (simpler)
- **Option B:** Spark Structured Streaming from CSV (more educational)
- **Recommendation:** Option B for course alignment

**Decision 2: Where to run ML inference?**
- **Option A:** In Spark job, store predictions to MongoDB (batch approach)
- **Option B:** FastAPI loads model, does inference on-demand (API approach)
- **Recommendation:** Hybrid - Spark for batch training, FastAPI for real-time inference

**Decision 3: Dashboard architecture?**
- **Option A:** Pure HTML/CSS/JS static files
- **Option B:** React/Vue SPA (overkill for assignment)
- **Recommendation:** Option A - vanilla JS with Chart.js

**Decision 4: Dataset preprocessing?**
- **Option A:** Use as-is (high duplicates)
- **Option B:** Deduplicate and acknowledge reduced dataset
- **Recommendation:** Option B - deduplicate to 30 unique samples, note in docs

---

## 5. Recommended Directory Structure

```
sentiment-stream/
├── openspec/
│   ├── config.yaml
│   ├── exploration.md              # ← This file
│   ├── specs/
│   │   └── main.yaml
│   └── changes/
│       └── init-architecture/
│           ├── proposal.md
│           ├── design.md
│           ├── spec.md
│           └── tasks.md
├── data/
│   ├── raw/
│   │   └── dataset_sentimientos_500.csv
│   └── processed/
│       └── dataset_clean.csv       # Deduplicated version
├── spark/
│   ├── pipeline.py                 # Training pipeline
│   ├── streaming.py                # Streaming ingestion
│   ├── model.py                    # Model persistence
│   └── requirements.txt
├── api/
│   ├── main.py                     # FastAPI app
│   ├── models.py                   # Pydantic models
│   ├── database.py                 # MongoDB connection
│   ├── routes/
│   │   ├── sentiments.py
│   │   ├── stats.py
│   │   └── predict.py
│   └── requirements.txt
├── dashboard/
│   ├── index.html
│   ├── css/
│   │   └── styles.css
│   ├── js/
│   │   ├── charts.js
│   │   └── api.js
│   └── Dockerfile
├── infra/
│   ├── docker-compose.yml
│   ├── Dockerfile.spark
│   ├── Dockerfile.api
│   └── jenkins/
│       └── Jenkinsfile
├── docs/
│   ├── README.md
│   ├── architecture.md
│   └── setup.md
└── .atl/
    └── skill-registry.md
```

---

## 6. Implementation Phases

### Phase 1: Foundation (Week 1)
- [ ] Deduplicate and clean dataset
- [ ] Set up Docker Compose with MongoDB
- [ ] Create PySpark training pipeline
- [ ] Train and persist Naive Bayes model

### Phase 2: API Development (Week 1-2)
- [ ] FastAPI project structure
- [ ] MongoDB connection and models
- [ ] Implement `/predict` endpoint
- [ ] Implement `/sentiments` endpoint
- [ ] Implement `/stats` endpoint

### Phase 3: Dashboard (Week 2)
- [ ] HTML/CSS/JS structure
- [ ] Chart.js integration
- [ ] API integration
- [ ] Real-time updates (WebSocket or polling)

### Phase 4: Streaming (Week 2-3)
- [ ] Spark Structured Streaming setup
- [ ] Micro-batch processing from CSV
- [ ] Integration with prediction pipeline
- [ ] Store streaming predictions to MongoDB

### Phase 5: DevOps (Week 3)
- [ ] Docker Compose orchestration
- [ ] Jenkins pipeline
- [ ] Documentation
- [ ] Testing

---

## 7. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Dataset too small for meaningful ML | High | Medium | Acknowledge educational purpose, focus on pipeline |
| Spark setup complexity | Medium | Medium | Use bitnami images, provide clear docs |
| FastAPI async with PySpark | Medium | Medium | Use ThreadPoolExecutor for blocking calls |
| MongoDB connection issues | Low | Low | Health checks, retry logic |
| Time constraints | High | High | Prioritize MVP, incremental delivery |

---

## 8. Recommendations

### Immediate Actions

1. **Accept dataset limitations** - This is an educational project, not production ML
2. **Start with Docker Compose** - Get infrastructure running first
3. **Build incrementally** - API first, then dashboard, then streaming
4. **Document everything** - University assignments value documentation highly

### Technical Recommendations

1. **Use `motor` library** for async MongoDB in FastAPI
2. **HashingTF with 500 features** (not 1000) given short texts
3. **Add timestamp field** to predictions even if dataset lacks it
4. **Use Pydantic models** for request/response validation
5. **Implement health checks** for all services

### Success Criteria

- ✅ FastAPI responds to all 3 endpoints correctly
- ✅ Dashboard displays charts and updates in real-time
- ✅ Spark job processes CSV and stores to MongoDB
- ✅ Docker Compose starts all services with one command
- ✅ Documentation is comprehensive and clear

---

## 9. Summary

**Current State:** Empty project with only raw dataset  
**Dataset Quality:** Poor (94% duplicates, short texts, English content)  
**Technical Feasibility:** High (standard stack, well-documented)  
**Recommended Approach:** Incremental build starting with API + Dashboard  
**Key Risk:** Dataset quality affecting model performance  

**Ready for Proposal:** YES

The project is well-defined with clear requirements. Despite dataset quality issues, this is a good educational exercise for learning Big Data pipeline concepts. The recommended next step is to create the Change Proposal for the initial architecture setup.

---

## Appendix: Useful Resources

- [PySpark MLlib Docs](https://spark.apache.org/docs/3.5.6/ml-guide.html)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [MongoDB PySpark Connector](https://docs.mongodb.com/spark-connector/)
- [Chart.js Examples](https://www.chartjs.org/docs/latest/samples/)
- [Docker Compose Reference](https://docs.docker.com/compose/)
