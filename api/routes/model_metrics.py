from fastapi import APIRouter, Request, HTTPException

from api.models import ModelMetricsResponse

router = APIRouter(tags=["model-metrics"])


@router.get("/", response_model=ModelMetricsResponse)
async def get_model_metrics(request: Request):
    """Devuelve las métricas de evaluación del modelo más reciente.

    Recupera precision, recall y f1-score por clase (positivo, negativo, neutral)
    desde la colección *model_metrics* de MongoDB.

    Raises:
        HTTPException: 404 si aún no existen métricas (entrenamiento no ejecutado).
    """
    db = request.app.state.db
    data = await db.get_model_metrics()

    if data is None:
        raise HTTPException(
            status_code=404,
            detail="No se encontraron métricas del modelo. " "Ejecute el entrenamiento (spark/train.py) primero.",
        )

    return ModelMetricsResponse(**data)
