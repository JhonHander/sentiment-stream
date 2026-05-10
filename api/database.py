from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorClient

from api.config import settings


class Database:
    """Cliente asíncrono de MongoDB vía Motor con helpers de acceso."""

    def __init__(self) -> None:
        self.client = AsyncIOMotorClient(settings.mongo_uri)
        self.db = self.client[settings.mongo_db]

    async def create_indexes(self) -> None:
        """Crea índices idempotentes en las colecciones principales."""
        await self.db.predictions.create_index([("timestamp", -1)])
        await self.db.predictions.create_index([("prediction", 1)])
        await self.db.predictions.create_index([("confidence", -1)])
        await self.db.model_metrics.create_index([("model_version", 1)], unique=True)

    async def insert_prediction(self, prediction: dict) -> str:
        """Persiste un documento de predicción en MongoDB.

        Convierte el campo *timestamp* de str a datetime si es necesario
        para mantener consistencia con el esquema ISODate del spec.
        """
        doc = dict(prediction)
        ts = doc.get("timestamp")
        if isinstance(ts, str):
            doc["timestamp"] = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        result = await self.db.predictions.insert_one(doc)
        return str(result.inserted_id)

    async def get_predictions(
        self,
        limit: int = 50,
        offset: int = 0,
        sentiment: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> dict:
        """Devuelve predicciones paginadas con filtros opcionales."""
        query: dict = {}
        if sentiment:
            query["prediction"] = sentiment
        if date_from or date_to:
            query["timestamp"] = {}
            if date_from:
                query["timestamp"]["$gte"] = date_from
            if date_to:
                query["timestamp"]["$lte"] = date_to

        total = await self.db.predictions.count_documents(query)
        cursor = self.db.predictions.find(query, {"_id": 0}).sort("timestamp", -1).skip(offset).limit(limit)
        items = await cursor.to_list(length=limit)
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    async def get_stats(self, period: str = "day") -> dict:
        """Agrega estadísticas: distribución, confianza promedio y serie temporal."""
        # Distribución por clase de sentimiento
        distribution: dict[str, int] = {}
        async for doc in self.db.predictions.aggregate([{"$group": {"_id": "$prediction", "count": {"$sum": 1}}}]):
            distribution[doc["_id"]] = doc["count"]

        # Confianza promedio y total de documentos
        avg_result = await self.db.predictions.aggregate(
            [
                {
                    "$group": {
                        "_id": None,
                        "avg_confidence": {"$avg": "$confidence"},
                        "total": {"$sum": 1},
                    }
                }
            ]
        ).to_list(length=1)

        avg_confidence = avg_result[0]["avg_confidence"] if avg_result else 0.0
        total = avg_result[0]["total"] if avg_result else 0

        # Serie temporal usando $dateTrunc (MongoDB 5.0+)
        timeseries: list[dict] = []
        async for doc in self.db.predictions.aggregate(
            [
                {
                    "$group": {
                        "_id": {"$dateTrunc": {"date": "$timestamp", "unit": period}},
                        "count": {"$sum": 1},
                    }
                },
                {"$sort": {"_id": 1}},
            ]
        ):
            ts_val = doc["_id"]
            ts_iso = ts_val.isoformat() if hasattr(ts_val, "isoformat") else str(ts_val)
            timeseries.append({"timestamp": ts_iso, "count": doc["count"]})

        return {
            "distribution": distribution,
            "avg_confidence": avg_confidence,
            "total": total,
            "timeseries": timeseries,
        }

    async def get_model_metrics(self) -> dict | None:
        """Recupera las métricas más recientes del modelo desde MongoDB.

        Devuelve la última entrada de la colección *model_metrics* ordenada
        por *trained_at* descendente, o *None* si aún no existen métricas.
        """
        doc = await self.db.model_metrics.find_one({}, sort={"trained_at": -1})
        if not doc:
            return None

        # Normaliza el documento para el contrato de respuesta
        precision = doc.get("precision", {})
        recall = doc.get("recall", {})
        f1 = doc.get("f1_score", 0.0)

        # Construye el diccionario de métricas por clase
        classes = ["positivo", "negativo", "neutral"]
        metrics: dict[str, dict[str, float]] = {}
        for cls in classes:
            metrics[cls] = {
                "precision": float(precision.get(cls, 0.0)),
                "recall": float(recall.get(cls, 0.0)),
                "f1": float(f1) if cls == "positivo" else float(f1),
            }
            # Ajuste: si no hay métricas por clase, distribuye el f1 global
            metrics[cls]["f1"] = float(f1)

        return {
            "metrics": metrics,
            "model_version": doc.get("model_version", "unknown"),
            "trained_at": doc.get("trained_at", datetime.utcnow()),
        }
