import logging
import os

from pyspark.ml import PipelineModel
from pyspark.sql import SparkSession

from api.config import settings

logger = logging.getLogger(__name__)


class ModelLoader:
    """Wrapper para cargar y exponer un PipelineModel de PySpark."""

    def __init__(self, model: PipelineModel, spark: SparkSession) -> None:
        self.model = model
        self.spark = spark

    @classmethod
    def load_from_path(cls, path: str | None = None) -> "ModelLoader":
        """Carga el modelo desde el volumen compartido.

        Raises:
            FileNotFoundError: si el directorio del modelo no existe.
        """
        path = path or settings.model_path
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"No se encontró el modelo en {path}. "
                "Ejecute el entrenamiento (train.py) antes de iniciar la API."
            )

        logger.info(f"Cargando modelo desde {path}")
        spark = SparkSession.builder.appName("SentimentInference").getOrCreate()
        model = PipelineModel.load(path)
        logger.info("Modelo cargado correctamente")
        return cls(model=model, spark=spark)
