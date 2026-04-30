from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Request, Query

from api.models import SentimentsResponse

router = APIRouter(tags=["sentiments"])


@router.get("/", response_model=SentimentsResponse)
async def list_sentiments(
    request: Request,
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    sentiment: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
):
    """Devuelve predicciones paginadas con soporte de filtros por sentimiento y rango de fechas."""
    db = request.app.state.db
    result = await db.get_predictions(
        limit=limit,
        offset=offset,
        sentiment=sentiment,
        date_from=date_from,
        date_to=date_to,
    )
    return SentimentsResponse(**result)
