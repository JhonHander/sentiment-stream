# Pruebas Manuales — Sentiment Stream

Esta guía explica cómo probar cada componente del sistema de forma manual,
sin depender de Jenkins ni scripts automatizados.

## Requisitos Previos

- Docker y Docker Compose instalados
- Python 3.11+ (para desarrollo local, opcional)
- Git (para clonar el repositorio)

---

## 1. Arrancar la Infraestructura

```bash
# Desde la raíz del proyecto
docker compose -f infra/docker-compose.yml up -d
```

Esto levanta 5 servicios:
- `mongodb` (puerto 27017)
- `spark-master` (puerto 8080)
- `spark-worker` (puerto 8081)
- `api` (puerto 8000)
- `dashboard` (puerto 80)

Verificar que todo esté corriendo:
```bash
docker compose -f infra/docker-compose.yml ps
docker compose -f infra/docker-compose.yml logs api | tail -20
```

---

## 2. Entrenar el Modelo

El modelo NO se entrena automáticamente al levantar los contenedores. Hay que ejecutar
el entrenamiento manualmente:

```bash
# Ejecutar entrenamiento en el contenedor spark-master
docker compose -f infra/docker-compose.yml run spark-master python -m spark.train
```

Esto hace:
1. Lee el CSV de `/app/data/dataset_sentimientos_500.csv`
2. Deduplica los registros (~30 únicos de ~500)
3. Mapea labels español → numérico (positivo=0, negativo=1, neutral=2)
4. Entrena el pipeline MLlib
5. Evalúa métricas (precision, recall, f1 por clase)
6. Guarda el modelo en `/app/model` (volumen compartido)
7. Persiste métricas en MongoDB → colección `model_metrics`

Salida esperada:
```
[INFO] spark.train - Training pipeline...
[INFO] spark.train - Accuracy: 0.XXXX
[INFO] spark.train - Precision: {...}
[INFO] spark.train - Recall: {...}
[INFO] spark.train - F1 Score: 0.XXXX
[INFO] spark.train - Model saved to /app/model
[INFO] spark.train - Metrics written to MongoDB
```

---

## 3. Probar la API con curl

### 3.1 Healthcheck

```bash
curl http://localhost:8000/health
```

Respuesta esperada:
```json
{"status": "ok"}
```

### 3.2 Predicción de Sentimiento

```bash
# Sentimiento positivo
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"text": "I love this product, it is amazing!"}'

# Sentimiento negativo
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"text": "This is terrible, I hate it."}'
```

Respuesta esperada:
```json
{
  "prediction": "positivo",
  "confidence": 0.85,
  "timestamp": "2026-04-30T12:00:00Z"
}
```

### 3.3 Listado de Sentimientos (con filtros)

```bash
# Listado paginado (primeros 10)
curl "http://localhost:8000/sentiments?limit=10&offset=0"

# Filtrar solo positivos
curl "http://localhost:8000/sentiments?limit=20&sentiment=positivo"

# Filtrar por rango de fechas
curl "http://localhost:8000/sentiments?date_from=2026-04-01T00:00:00&date_to=2026-04-30T23:59:59"
```

Respuesta esperada:
```json
{
  "data": [
    {
      "original_text": "...",
      "prediction": "positivo",
      "confidence": 0.85,
      "timestamp": "2026-04-30T12:00:00Z"
    }
  ],
  "total": 5,
  "limit": 10,
  "offset": 0
}
```

### 3.4 Estadísticas

```bash
# Estadísticas generales (por día)
curl http://localhost:8000/stats

# Estadísticas por hora
curl "http://localhost:8000/stats?period=hour"
```

Respuesta esperada:
```json
{
  "distribution": {
    "positivo": 2,
    "negativo": 1,
    "neutral": 2
  },
  "avg_confidence": {
    "positivo": 0.82,
    "negativo": 0.75,
    "neutral": 0.68,
    "overall": 0.75
  },
  "total": 5,
  "timeseries": [
    {"date": "2026-04-30T12:00:00Z", "count": 3, ...},
    {"date": "2026-04-30T13:00:00Z", "count": 2, ...}
  ]
}
```

### 3.5 Métricas del Modelo

```bash
curl http://localhost:8000/model-metrics
```

Respuesta esperada:
```json
{
  "metrics": {
    "positivo": {"precision": 0.85, "recall": 0.80, "f1": 0.82},
    "negativo": {"precision": 0.78, "recall": 0.82, "f1": 0.80},
    "neutral": {"precision": 0.72, "recall": 0.75, "f1": 0.73}
  },
  "model_version": "v1_20260430_120000",
  "trained_at": "2026-04-30T12:00:00Z"
}
```

### 3.6 Casos de Error

```bash
# Texto vacío (debe devolver 422)
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"text": ""}'

# Métricas sin entrenar (debe devolver 404 si no hay métricas)
curl http://localhost:8000/model-metrics
```

---

## 4. Probar el Dashboard

Abrir en el navegador: **http://localhost**

Verificaciones:
- [ ] La página carga con tema oscuro
- [ ] Los KPI cards muestran valores (o "—" si no hay datos)
- [ ] El doughnut chart muestra distribución de sentimientos
- [ ] El bar chart muestra confianza promedio por clase
- [ ] El line chart muestra volumen de predicciones en el tiempo
- [ ] El radar chart muestra métricas del modelo
- [ ] La tabla de predicciones carga datos paginados
- [ ] El badge de estado muestra "Conectado" (verde)
- [ ] El auto-refresh actualiza cada 10 segundos
- [ ] El botón de pausa/reanudar funciona
- [ ] El botón de refresh fuerza actualización
- [ ] La tecla `R` fuerza actualización

Si la API no responde:
- [ ] Aparece el banner "Conexión perdida..."
- [ ] El botón "Reintentar" funciona
- [ ] Los charts mantienen los últimos datos válidos

---

## 5. Probar el Streaming

```bash
# Ejecutar streaming (procesa el CSV en micro-batches)
docker compose -f infra/docker-compose.yml run spark-master python -m spark.stream
```

El streaming:
1. Lee el CSV como fuente de stream
2. Procesa micro-batches cada 5 segundos
3. Deduplica por texto
4. Aplica el modelo entrenado
5. Escribe predicciones en MongoDB

Verificar después de ejecutar:
```bash
# Deben aparecer predicciones en la colección
curl http://localhost:8000/sentiments?limit=5
```

---

## 6. Limpiar

```bash
# Detener servicios
docker compose -f infra/docker-compose.yml down

# Detener y eliminar volúmenes (reset completo)
docker compose -f infra/docker-compose.yml down -v
```

---

## Check-list de Verificación Final

| # | Prueba | Comando / Acción | Estado |
|---|--------|-----------------|--------|
| 1 | `docker compose up -d` | Todos los servicios levantan | ☐ |
| 2 | Healthcheck API | `curl localhost:8000/health` | ☐ |
| 3 | Entrenar modelo | `docker compose run spark-master python -m spark.train` | ☐ |
| 4 | POST /predict | `curl -X POST ... -d '{"text":"I love this"}'` | ☐ |
| 5 | GET /sentiments | `curl "localhost:8000/sentiments?limit=5"` | ☐ |
| 6 | GET /stats | `curl localhost:8000/stats` | ☐ |
| 7 | GET /model-metrics | `curl localhost:8000/model-metrics` | ☐ |
| 8 | Dashboard carga | Abrir `http://localhost` en navegador | ☐ |
| 9 | KPI cards con datos | Verificar valores numéricos | ☐ |
| 10 | Charts renderizados | 5 visualizaciones visibles | ☐ |
| 11 | Auto-refresh | Esperar 10s, ver actualización | ☐ |
| 12 | Streaming | `docker compose run spark-master python -m spark.stream` | ☐ |
| 13 | Limpieza | `docker compose down` | ☐ |
