from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SentimentPredictionRequest(BaseModel):
    """Body para solicitudes de predicción de sentimiento."""

    text: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Texto a clasificar",
    )


class SentimentPredictionResponse(BaseModel):
    """Respuesta de una predicción de sentimiento."""

    prediction: str
    confidence: float
    timestamp: datetime


class SentimentFilter(BaseModel):
    """Filtros para consultar predicciones almacenadas."""

    limit: int = Field(50, ge=1, le=1000)
    offset: int = Field(0, ge=0)
    sentiment: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None


class SentimentsResponse(BaseModel):
    """Respuesta paginada de predicciones almacenadas."""

    items: list[dict]
    total: int
    limit: int
    offset: int


class StatsResponse(BaseModel):
    """Estadísticas agregadas de predicciones."""

    distribution: dict[str, int]
    avg_confidence: float
    total: int
    timeseries: list[dict]


class ModelMetricsResponse(BaseModel):
    """Métricas de evaluación del modelo por clase."""

    metrics: dict[str, dict[str, float]]
    model_version: str
    trained_at: datetime


class ErrorResponse(BaseModel):
    """Formato común de error."""

    detail: str
