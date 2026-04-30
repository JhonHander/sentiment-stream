from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import settings
from api.database import Database
from api.services.model_loader import ModelLoader
from api.routes import predict, sentiments, stats, model_metrics

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestiona el ciclo de vida de la aplicación:

    - **Startup**: conecta MongoDB, crea índices y carga el modelo PySpark.
    - **Shutdown**: cierra la conexión de Motor.
    """
    # --- Startup ---
    db = Database()
    await db.create_indexes()
    app.state.db = db
    logger.info("Conexión a MongoDB establecida e índices creados")

    try:
        model_loader = ModelLoader.load_from_path()
        app.state.model_loader = model_loader
        logger.info("Modelo de ML cargado en lifespan")
    except Exception as exc:
        logger.error(f"No se pudo cargar el modelo: {exc}")
        app.state.model_loader = None

    yield

    # --- Shutdown ---
    db.client.close()
    logger.info("Conexión a MongoDB cerrada")


app = FastAPI(
    title="Sentiment Stream API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(predict.router, prefix="/predict")
app.include_router(sentiments.router, prefix="/sentiments")
app.include_router(stats.router, prefix="/stats")
app.include_router(model_metrics.router, prefix="/model-metrics")


@app.get("/health")
async def health():
    """Healthcheck básico para Docker / orquestadores."""
    return {"status": "ok"}
