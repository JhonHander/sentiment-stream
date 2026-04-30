import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from api.services.model_loader import ModelLoader

# Pool de hilos para ejecutar transformaciones de PySpark sin bloquear el loop async
_executor = ThreadPoolExecutor(max_workers=2)

# Mapeo numérico -> etiqueta en español (debe coincidir con spark/utils.py)
_LABEL_MAP = {
    0.0: "positivo",
    1.0: "negativo",
    2.0: "neutral",
}


def _sync_predict(loader: ModelLoader, text: str) -> dict:
    """Ejecuta la predicción de forma sincrónica dentro de un hilo.

    Crea un DataFrame de una sola fila, aplica el PipelineModel y extrae
    la etiqueta predicha junto con la probabilidad (confianza) de esa clase.
    """
    df = loader.spark.createDataFrame([(text,)], ["texto"])
    prediction_df = loader.model.transform(df)
    row = prediction_df.collect()[0]

    pred_numeric = float(row.prediction)
    label = _LABEL_MAP.get(pred_numeric, "unknown")

    # Extrae la probabilidad correspondiente a la clase predicha
    prob_vector = row.probability
    confidence = 0.0
    if prob_vector is not None:
        try:
            confidence = float(prob_vector[int(pred_numeric)])
        except Exception:
            confidence = float(max(prob_vector))

    return {
        "original_text": text,
        "prediction": label,
        "confidence": confidence,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "model_version": "unknown",
    }


async def predict_text(loader: ModelLoader, text: str) -> dict:
    """Orquesta la predicción en un ThreadPoolExecutor para no bloquear el event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _sync_predict, loader, text)
