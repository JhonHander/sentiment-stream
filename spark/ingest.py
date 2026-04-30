"""
Data ingestion and cleaning module.

Reads the raw sentiment CSV, validates the expected schema, deduplicates
texts, and adds synthetic identifiers and timestamps where missing.

Dataset limitations:
- The CSV contains ~500 rows but ~94% are duplicates (~30 unique).
- Average text length is ~28 characters.
- Labels are in Spanish (positivo/negativo/neutral) while text is in English.
"""

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import monotonically_increasing_id, current_timestamp
from spark.utils import CSV_PATH, get_logger

logger = get_logger(__name__)


def load_and_clean_csv(spark: SparkSession, path: str = CSV_PATH) -> DataFrame:
    """
    Load the sentiment CSV, deduplicate, and enrich with synthetic columns.

    Parameters
    ----------
    spark : SparkSession
        Active Spark session.
    path : str
        Path to the CSV file. Defaults to the value from utils.CSV_PATH.

    Returns
    -------
    DataFrame
        Cleaned DataFrame with columns: texto, etiqueta, id, timestamp.
    """
    logger.info(f"Loading CSV from {path}")

    df = spark.read.csv(path, header=True, inferSchema=True)

    # Validate expected columns
    expected = {"texto", "etiqueta"}
    actual = set(df.columns)
    if not expected.issubset(actual):
        missing = expected - actual
        raise ValueError(f"CSV missing columns: {missing}. Found: {actual}")

    # Deduplicate on text content — the dataset has ~94% duplicates
    original_count = df.count()
    df = df.dropDuplicates(["texto"])
    deduped_count = df.count()
    logger.info(f"Deduplicated: {original_count} -> {deduped_count} rows")

    # Add synthetic id if missing
    if "id" not in df.columns:
        df = df.withColumn("id", monotonically_increasing_id())

    # Add timestamp if missing
    if "timestamp" not in df.columns:
        df = df.withColumn("timestamp", current_timestamp())

    return df
