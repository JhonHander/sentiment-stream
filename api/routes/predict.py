from fastapi import APIRouter, HTTPException, Request

from api.models import SentimentPredictionRequest, SentimentPredictionResponse
from api.services.inference import predict_text

router = APIRouter(tags=["prediction"])


@router.post("/", response_model=SentimentPredictionResponse)
async def predict(request: Request, body: SentimentPredictionRequest):
    """Predice el sentimiento de un texto y persiste el resultado en MongoDB."""
    loader = getattr(request.app.state, "model_loader", None)
    if loader is None:
        raise HTTPException(status_code=503, detail="Modelo no disponible")

    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="El texto no puede estar vacío")

    result = await predict_text(loader, text)

    db = request.app.state.db
    await db.insert_prediction(result)

    return SentimentPredictionResponse(
        prediction=result["prediction"],
        confidence=result["confidence"],
        timestamp=result["timestamp"],
    )
