# Verificación: Sentiment Stream

**Fecha**: 2026-04-30
**Verificador**: SDD Verify Phase
**Estado General**: ✅ PASS (0 issues — 1 WARNING menor corregido)

---

## 1. Estructura del Proyecto

**Estado**: ✅ PASS

**Requisito**: Repo con carpetas `/spark`, `/api`, `/infra`, `/docs`

**Hallazgos**:
- ✅ `/spark/` — Completo (ingest.py, train.py, stream.py, utils.py, Dockerfile, requirements.txt)
- ✅ `/api/` — Completo (main.py, models.py, database.py, routes/, services/, Dockerfile, requirements.txt)
- ✅ `/dashboard/` — Completo (index.html, css/, js/, Dockerfile)
- ✅ `/infra/` — Completo (docker-compose.yml, docker-compose.test.yml, Jenkinsfile, mongodb-init.js, scripts/)
- ✅ `/docs/` — Completo (ARCHITECTURE.md, API.md, DEPLOYMENT.md)
- ✅ `/data/` — Dataset en ubicación correcta
- ✅ `/tests/` — Tests unitarios e integración
- ✅ `README.md` — Documentación raíz completa
- ✅ `pyproject.toml` — Configuración de proyecto moderna

---

## 2. Spark Pipeline

**Estado**: ✅ PASS

**Requisito**: Pipeline PySpark (Tokenizer → StopWordsRemover → HashingTF/IDF → NaiveBayes), streaming, deduplicación

**Hallazgos**:
- ✅ `spark/train.py` implementa exactamente las 5 etapas requeridas:
  1. Tokenizer (inputCol="texto", outputCol="words")
  2. StopWordsRemover (inputCol="words", outputCol="filtered")
  3. HashingTF (numFeatures=500, inputCol="filtered", outputCol="rawFeatures")
  4. IDF (inputCol="rawFeatures", outputCol="features")
  5. NaiveBayes (multinomial)
- ✅ Mapeo de labels español → numérico antes de entrenar (NaiveBayes requiere labels numéricos)
- ✅ `PipelineModel.save()` persiste modelo en `/app/model`
- ✅ Métricas de evaluación (precision, recall, f1) persistidas en MongoDB `model_metrics`
- ✅ `spark/stream.py` usa `Structured Streaming` con:
  - `readStream.format("csv")`
  - `dropDuplicates(["texto"])` para deduplicación
  - `trigger(processingTime='5 seconds')`
  - `foreachBatch` para escritura a MongoDB
- ✅ Extracción de confianza desde el vector de probabilidad
- ✅ Mapeo inverso numérico → español en las predicciones

**Nota**: El dataset tiene ~30 muestras únicas después de deduplicar, lo cual está documentado honestamente. El pipeline es correcto para propósitos educativos.

---

## 3. FastAPI Backend

**Estado**: ✅ PASS

**Requisito**: FastAPI con endpoints /sentiments, /stats, /predict

**Hallazgos**:
- ✅ `api/main.py` usa `lifespan` async context manager (FastAPI v0.115+ best practice)
- ✅ Startup: conecta MongoDB, crea índices, carga modelo
- ✅ Shutdown: cierra conexión Motor
- ✅ CORS middleware configurado para dashboard
- ✅ Healthcheck en `/health`

**Endpoints verificados**:
| Endpoint | Método | Parámetros | Estado |
|----------|--------|------------|--------|
| `/predict` | POST | `{text: string}` | ✅ Implementado, persiste en MongoDB, maneja 503/422 |
| `/sentiments` | GET | limit, offset, sentiment, date_from, date_to | ✅ Implementado con paginación y filtros |
| `/stats` | GET | period (hour/day) | ✅ Implementado con distribución, avg_confidence, timeseries |
| `/model-metrics` | GET | — | ✅ Implementado (extra, no requerido originalmente) |
| `/health` | GET | — | ✅ Implementado |

- ✅ Motor async para MongoDB (no bloqueante)
- ✅ `run_in_executor` para inferencia PySpark (no bloquea event loop)
- ✅ Modelo cargado una vez en lifespan, reutilizado por requests
- ✅ Manejo de errores: 503 si modelo no cargado, 422 si texto vacío, 404 si métricas no existen

---

## 4. MongoDB

**Estado**: ✅ PASS

**Requisito**: Colección de predicciones con original_text, prediction, confidence, timestamp

**Hallazgos**:
- ✅ `infra/mongodb-init.js` crea:
  - Colección `predictions` con schema validation
  - Colección `model_metrics`
  - Índices: `timestamp` (desc), `prediction`, `confidence`
- ✅ `api/database.py` usa Motor (async)
- ✅ Documentos de predicción incluyen: `original_text`, `prediction`, `confidence`, `timestamp`, `model_version`
- ✅ Helper `get_model_metrics()` lee desde `model_metrics`

---

## 5. Dashboard

**Estado**: ✅ PASS

**Requisito**: HTML/CSS/JS profesional con Chart.js, distribución, tendencias, tabla

**Hallazgos**:
- ✅ Tema oscuro profesional con CSS custom properties
- ✅ Responsive (320px+)
- ✅ 5 visualizaciones implementadas:
  1. Doughnut chart — distribución de sentimientos
  2. Horizontal bar chart — confianza promedio por clase
  3. Line chart — volumen de predicciones en el tiempo
  4. Radar chart — métricas del modelo (precision/recall por clase) ← **usa `/model-metrics`**
  5. Tabla paginada — predicciones recientes con búsqueda
- ✅ KPI cards con métricas principales
- ✅ Auto-refresh cada 10 segundos con toggle on/off
- ✅ Offline banner con reintentos (3 retries, backoff)
- ✅ Keyboard shortcut `R` para refresh forzado
- ✅ Loading states y empty states manejados
- ✅ Conectado a API REST vía `fetch()`
- ✅ Servido por nginx:alpine con gzip

**Nota**: El usuario pidió "algo más completico" que lo mínimo requerido. El dashboard cumple sobradamente.

---

## 6. Docker Compose

**Estado**: ✅ PASS (con 1 WARNING)

**Requisito**: Orquestar MongoDB, Spark, FastAPI, Dashboard

**Hallazgos**:
- ✅ 5 servicios definidos: mongodb, spark-master, spark-worker, api, dashboard
- ✅ `depends_on` con `condition: service_healthy` para MongoDB → API
- ✅ Healthchecks en todos los servicios
- ✅ Volumen compartido `model_storage` entre spark-master, spark-worker, api
- ✅ Volumen `mongo-data` para persistencia de BD
- ✅ Network bridge `sentiment-network`
- ✅ `mongodb-init.js` montado en `/docker-entrypoint-initdb.d/`
- ✅ Spark monta `./data` como read-only

**WARNING RESUELTO ✅** (2026-04-30):
- ~~El `spark-master` y `spark-worker` usan `build` con `dockerfile: spark/Dockerfile`, pero la imagen bitnami/spark tiene un entrypoint que puede entrar en conflicto con el `CMD` del Dockerfile de Spark (que ejecuta train.py).~~
- **Fix aplicado**: Se eliminó el `CMD` del `spark/Dockerfile`. El entrypoint nativo de `bitnami/spark` ahora maneja `SPARK_MODE` sin interferencias. Para ejecutar entrenamiento: `docker compose run spark-master python -m spark.train`.

---

## 7. Jenkins Pipeline

**Estado**: ✅ PASS

**Requisito**: Jenkinsfile declarativo con CI/CD

**Hallazgos**:
- ✅ Declarative Pipeline
- ✅ Stages: Checkout → Build → Test → Lint → Deploy
- ✅ `skipStagesAfterUnstable()` para gatear deploys rotos
- ✅ `timeout` de 30 minutos
- ✅ `buildDiscarder` para rotar logs
- ✅ Variables de entorno: `COMPOSE_PROJECT_NAME`, `MODEL_VERSION`
- ✅ Post-actions: logs en always, mensajes en success/failure/unstable
- ✅ Deploy verifica health de API y Dashboard con `curl`

---

## 8. Tests

**Estado**: ✅ PASS

**Requisito**: Tests de la API

**Hallazgos**:
- ✅ 13 tests pasando (pytest)
- ✅ `tests/conftest.py` con FakeDatabase mock y fixtures
- ✅ Cobertura:
  - `test_health.py` — Healthcheck
  - `test_predict.py` — Input válido, vacío, modelo no cargado, texto muy largo
  - `test_sentiments.py` — Paginación, filtrado, colección vacía, límites
  - `test_stats.py` — Estructura, parámetro de período
  - `test_model_metrics.py` — Métricas existentes, no encontradas (404)
- ✅ `tests/integration/test_docker_compose.sh` — Test end-to-end de la stack completa
- ✅ `pyproject.toml` con configuración de pytest

---

## 9. Documentación

**Estado**: ✅ PASS

**Requisito**: README, instrucciones de despliegue, documentación del proyecto

**Hallazgos**:
- ✅ `README.md` completo con:
  - Descripción del proyecto
  - Diagrama de arquitectura (text-based)
  - Prerrequisitos
  - Instrucciones de setup (`docker-compose up`)
  - Resumen de API con ejemplos de request/response
  - Features del dashboard
  - **Limitaciones del dataset documentadas honestamente** (duplicados, texto en inglés, muestras reducidas)
  - Instrucciones de Jenkins
  - Troubleshooting
- ✅ `docs/ARCHITECTURE.md` — Diagramas de componentes, flujo de datos, stack tecnológico, decisiones de diseño
- ✅ `docs/API.md` — Todos los endpoints con métodos, parámetros, ejemplos de request/response, códigos de error, comandos curl
- ✅ `docs/DEPLOYMENT.md` — Docker Compose, Jenkins, variables de entorno, consideraciones de producción

---

## 10. Calidad de Código

**Estado**: ✅ PASS

**Hallazgos**:
- ✅ Comentarios y docstrings significativos (explican POR QUÉ, no solo QUÉ)
- ✅ Nombres de variables y funciones descriptivos en inglés
- ✅ Texto de usuario en español (consistente con el assignment)
- ✅ Manejo de errores robusto en todos los endpoints
- ✅ Logging configurado en Spark
- ✅ Type hints en funciones principales
- ✅ Separación de responsabilidades (routes, services, database, models)
- ✅ Configuración centralizada en `api/config.py`

---

## Resumen Ejecutivo

| Área | Estado | Notas |
|------|--------|-------|
| Estructura | ✅ PASS | Todas las carpetas requeridas presentes |
| Spark Pipeline | ✅ PASS | Pipeline correcto, streaming, deduplicación |
| FastAPI Backend | ✅ PASS | 5 endpoints, async, Motor, run_in_executor |
| MongoDB | ✅ PASS | Colecciones, índices, schema validation |
| Dashboard | ✅ PASS | Profesional, 5 visualizaciones, responsive |
| Docker Compose | ✅ PASS ⚠️ | Warning menor sobre entrypoint de Spark |
| Jenkins | ✅ PASS | Pipeline declarativo completo |
| Tests | ✅ PASS | 13 tests pasando |
| Documentación | ✅ PASS | README honesto, docs completas |
| Código | ✅ PASS | Limpio, comentado, robusto |

**Issues Críticos**: 0
**Warnings**: 1 (entrypoint Spark en Docker Compose)
**Sugerencias**: 0

**Conclusión**: El proyecto cumple con TODOS los requisitos del assignment y los del usuario. La arquitectura está bien dividida, el código es limpio, los tests pasan, la documentación es honesta y completa. El único punto a ajustar es el entrypoint de Spark en Docker Compose para asegurar arranque correcto.
