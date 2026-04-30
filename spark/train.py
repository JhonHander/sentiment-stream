"""
Model training module.

Builds a PySpark MLlib Pipeline (Tokenizer -> StopWordsRemover ->
HashingTF(500 features) -> IDF -> NaiveBayes), trains it on the deduplicated
dataset, evaluates multiclass metrics, persists the PipelineModel to disk,
and stores metrics to MongoDB.

Dataset limitations:
- Only ~30 unique samples remain after deduplication.
- Short texts (~28 chars avg) lead to a very small vocabulary.
- Results are suitable for demonstration, not production use.
"""

from datetime import datetime, timezone
import os
import shutil

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, when
from pyspark.ml import Pipeline
from pyspark.ml.feature import Tokenizer, StopWordsRemover, HashingTF, IDF
from pyspark.ml.classification import NaiveBayes
from pyspark.ml.evaluation import MulticlassClassificationEvaluator

from spark.utils import (
    get_logger,
    NUM_FEATURES,
    SMOOTHING,
    MODEL_TYPE,
    MODEL_PATH,
    write_metrics_to_mongo,
    REVERSE_LABEL_MAP,
    LABEL_MAP,
)
from spark.ingest import load_and_clean_csv

logger = get_logger(__name__)


def build_pipeline() -> Pipeline:
    """
    Construct the ML pipeline with the five required stages.

    Pipeline:
        1. Tokenizer         — split text into words
        2. StopWordsRemover  — remove default English stop words
        3. HashingTF         — map terms to a 500-feature vector
        4. IDF               — compute inverse document frequency
        5. NaiveBayes        — multinomial Naive Bayes classifier
    """
    tokenizer = Tokenizer(inputCol="texto", outputCol="words")
    remover = StopWordsRemover(inputCol="words", outputCol="filtered")
    hashing_tf = HashingTF(
        inputCol="filtered",
        outputCol="rawFeatures",
        numFeatures=NUM_FEATURES,
    )
    idf = IDF(inputCol="rawFeatures", outputCol="features")
    nb = NaiveBayes(
        smoothing=SMOOTHING,
        modelType=MODEL_TYPE,
        labelCol="label",
        featuresCol="features",
    )
    return Pipeline(stages=[tokenizer, remover, hashing_tf, idf, nb])


def train_model(spark: SparkSession):
    """
    Train the sentiment classification pipeline.

    Steps:
        1. Load and deduplicate CSV via ingest.py.
        2. Map Spanish string labels to numeric indices for NaiveBayes.
        3. Fit the Pipeline.
        4. Evaluate accuracy and F1 on the training set.
        5. Compute per-class precision and recall.
        6. Save the fitted PipelineModel to MODEL_PATH.
        7. Persist metrics to MongoDB.

    Returns
    -------
    tuple[PipelineModel, dict]
        The trained model and the metrics dictionary.
    """
    df = load_and_clean_csv(spark)

    # Map string labels to numeric indices required by NaiveBayes
    df = df.withColumn(
        "label",
        when(col("etiqueta") == "positivo", LABEL_MAP["positivo"])
        .when(col("etiqueta") == "negativo", LABEL_MAP["negativo"])
        .when(col("etiqueta") == "neutral", LABEL_MAP["neutral"])
        .otherwise(None),
    ).filter(col("label").isNotNull())

    if df.count() == 0:
        raise ValueError("No valid training data after label filtering.")

    pipeline = build_pipeline()
    model = pipeline.fit(df)

    predictions = model.transform(df)

    evaluator = MulticlassClassificationEvaluator(
        labelCol="label", predictionCol="prediction"
    )

    accuracy = evaluator.evaluate(predictions, {evaluator.metricName: "accuracy"})
    f1 = evaluator.evaluate(predictions, {evaluator.metricName: "f1"})

    # Per-class precision / recall
    labels = sorted(REVERSE_LABEL_MAP.keys())
    precision_per_class = {}
    recall_per_class = {}

    for lbl in labels:
        label_name = REVERSE_LABEL_MAP[lbl]
        tp = predictions.filter(
            (col("label") == lbl) & (col("prediction") == lbl)
        ).count()
        fp = predictions.filter(
            (col("label") != lbl) & (col("prediction") == lbl)
        ).count()
        fn = predictions.filter(
            (col("label") == lbl) & (col("prediction") != lbl)
        ).count()

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0

        precision_per_class[label_name] = round(precision, 4)
        recall_per_class[label_name] = round(recall, 4)

    model_version = f"v1_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    ...
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "model_version": model_version,
    }

    # Persist model — clean old files inside mount point (cannot rmtree Docker volume)
    if os.path.exists(MODEL_PATH):
        for item in os.listdir(MODEL_PATH):
            item_path = os.path.join(MODEL_PATH, item)
            if os.path.isfile(item_path) or os.path.islink(item_path):
                os.unlink(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)
    os.makedirs(MODEL_PATH, exist_ok=True)

    model.write().overwrite().save(MODEL_PATH)
    logger.info(f"Model saved to {MODEL_PATH}")

    write_metrics_to_mongo(metrics)
    logger.info("Metrics stored to MongoDB")

    return model, metrics


if __name__ == "__main__":
    spark = SparkSession.builder.appName("SentimentTrain").getOrCreate()
    try:
        model, metrics = train_model(spark)
        logger.info("Training completed successfully.")
    except Exception as e:
        logger.error(f"Training failed: {e}")
        raise
    finally:
        spark.stop()
