from fastapi import APIRouter, Request, Query

from api.models import StatsResponse

router = APIRouter(tags=["statistics"])


@router.get("/", response_model=StatsResponse)
async def get_stats(
    request: Request, period: str = Query("day", pattern="^(hour|day)$")
):
    """Devuelve estadísticas agregadas de las predicciones almacenadas."""
    db = request.app.state.db
    data = await db.get_stats(period=period)
    return StatsResponse(**data)
