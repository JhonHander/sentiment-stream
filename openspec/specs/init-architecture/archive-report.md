# Archivo: sentiment-stream / init-architecture

**Fecha de archivo**: 2026-04-30
**Estado**: ✅ COMPLETADO

---

## Resumen del Cambio

Implementación completa de un pipeline de análisis de sentimiento para asignatura universitaria de Big Data/Data Engineering.

### Stack Final

| Componente | Versión |
|-----------|---------|
| Python | 3.12 |
| PySpark | 4.0.2 |
| Java | 21 |
| MongoDB | 7.0 (Docker) |
| FastAPI | 0.115+ |
| Motor | 3.5+ (async MongoDB) |
| Chart.js | CDN (dashboard) |
| Docker Compose | 5 servicios |
| Jenkins | Declarative Pipeline |

### Entregables

| Carpeta | Contenido |
|---------|-----------|
| `spark/` | Pipeline MLlib (Tokenizer → StopWordsRemover → HashingTF(500) → IDF → NaiveBayes), Structured Streaming |
| `api/` | FastAPI (5 endpoints: /health, /predict, /sentiments, /stats, /model-metrics) |
| `dashboard/` | HTML/CSS/JS + Chart.js (5 visualizaciones, auto-refresh, responsive) |
| `infra/` | Docker Compose (5 servicios), Jenkinsfile, MongoDB init |
| `docs/` | ARCHITECTURE.md, API.md, DEPLOYMENT.md, MANUAL_TESTING.md |
| `tests/` | 13 tests unitarios + 1 test de integración |
| `data/` | Dataset original (sin modificar) |

### Resultados de Verificación

- **10/10** áreas PASS
- **0** issues críticos
- **13/13** tests pasando
- Todos los endpoints probados en Docker

### Issues Resueltos Durante Desarrollo

1. Dataset 94% duplicado → documentado honestamente
2. bitnami/spark deprecado → spark:3.5.2 → python:3.12-slim + pip pyspark
3. Python 3.8 EOL → migrado a 3.12
4. PySpark 3.5.2 → migrado a 4.0.2
5. Build contexts en Docker Compose → corregidos
6. Permisos de volumen → root user
7. Healthchecks HEAD vs GET → corregidos
8. FastAPI trailing slash → documentado

### Limitaciones Conocidas (Documentadas)

- Dataset: ~30 muestras únicas, textos en inglés, muy cortos
- Modelo: NaiveBayes con features limitados, no apto para producción
- Spark: standalone mode (single node), sin HDFS
- 94% de registros duplicados en el CSV original
