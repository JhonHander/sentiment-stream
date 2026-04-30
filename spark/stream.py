"""
Spark Structured Streaming module.

Reads the CSV source as a streaming DataFrame, deduplicates each micro-batch,
applies the previously trained PipelineModel, and writes predictions to
MongoDB via foreachBatch.

Trigger interval: 5 seconds (processingTime).

Dataset limitations:
- The source CSV is static; streaming will process it once per file appearance.
- Deduplication (dropDuplicates) is applied within each micro-batch.
- With ~94% duplicate rows, expect at most ~30 unique predictions total.
"""

from datetime import datetime
import os

from pyspark.sql import SparkSession
from pyspark.ml import PipelineModel
from pyspark.sql.functions import col, lit

from spark.utils import (
    get_logger,
    CSV_PATH,
    MODEL_PATH,
    TRIGGER_INTERVAL,
    write_predictions_to_mongo,
    REVERSE_LABEL_MAP,
)

logger = get_logger(__name__)


def start_streaming(spark: SparkSession):
    """
    Start a Structured Streaming query that predicts sentiment and writes
    results to MongoDB.

    The function loads a pre-trained PipelineModel, sets up a CSV stream
    source, deduplicates incoming texts, transforms them through the model,
    and uses foreachBatch to insert documents into MongoDB.
    """
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"Model not found at {MODEL_PATH}. Run train.py first.")

    model = PipelineModel.load(MODEL_PATH)
    logger.info(f"Loaded model from {MODEL_PATH}")

    stream_df = (
        spark.readStream.format("csv")
        .option("header", True)
        .option("inferSchema", True)
        .option("maxFilesPerTrigger", 1)
        .load(CSV_PATH)
    )

    # Deduplicate within each micro-batch
    deduped = stream_df.dropDuplicates(["texto"])

    predictions = model.transform(deduped)

    # Select columns needed for the sink; keep numeric prediction to index
    # into the probability vector for confidence extraction.
    output = predictions.select(
        col("texto").alias("original_text"),
        col("prediction").alias("prediction_numeric"),
        col("probability").alias("probability"),
        lit("v1_streaming").alias("model_version"),
    )

    def write_batch_to_mongo(batch_df, batch_id):
        """Write a single micro-batch to MongoDB predictions collection."""
        logger.info(f"Processing batch {batch_id}")
        records = [row.asDict() for row in batch_df.collect()]
        if records:
            for r in records:
                r["timestamp"] = datetime.utcnow().isoformat() + "Z"
                prob = r.get("probability")
                pred_numeric = r.pop("prediction_numeric", None)

                if prob is not None and pred_numeric is not None:
                    try:
                        r["confidence"] = float(prob[int(pred_numeric)])
                    except Exception:
                        r["confidence"] = 0.0
                else:
                    r["confidence"] = 0.0

                r["prediction"] = REVERSE_LABEL_MAP.get(float(pred_numeric), "unknown")
                r.pop("probability", None)

            write_predictions_to_mongo(records)
            logger.info(f"Wrote {len(records)} records to MongoDB")

    query = (
        output.writeStream.foreachBatch(write_batch_to_mongo)
        .trigger(processingTime=TRIGGER_INTERVAL)
        .outputMode("append")
        .option("checkpointLocation", "/app/checkpoints")
        .start()
    )

    logger.info("Streaming query started. Waiting for termination...")
    query.awaitTermination()


if __name__ == "__main__":
    spark = SparkSession.builder.appName("SentimentStream").getOrCreate()
    try:
        start_streaming(spark)
    except Exception as e:
        logger.error(f"Streaming failed: {e}")
        raise
    finally:
        spark.stop()
