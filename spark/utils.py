"""
Shared utilities for the Spark sentiment pipeline.

Handles MongoDB connections, logging setup, configuration constants,
and label mapping between Spanish labels and numeric indices required
by PySpark MLlib NaiveBayes.
"""

import logging
import os
from datetime import datetime
from pymongo import MongoClient

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongodb:27017/sentiment_stream")
MONGO_DB = os.getenv("MONGO_DB", "sentiment_stream")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "predictions")
MONGO_METRICS_COLLECTION = os.getenv("MONGO_METRICS_COLLECTION", "model_metrics")
MODEL_PATH = os.getenv("MODEL_PATH", "/app/model")
CSV_PATH = os.getenv("CSV_PATH", "/app/data/dataset_sentimientos_500.csv")

NUM_FEATURES = 500
SMOOTHING = 1.0
MODEL_TYPE = "multinomial"
TRIGGER_INTERVAL = "5 seconds"

# ---------------------------------------------------------------------------
# Label mapping: Spanish string -> numeric index for NaiveBayes
# ---------------------------------------------------------------------------
LABEL_MAP = {
    "positivo": 0.0,
    "negativo": 1.0,
    "neutral": 2.0,
}

REVERSE_LABEL_MAP = {v: k for k, v in LABEL_MAP.items()}


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def get_logger(name: str) -> logging.Logger:
    """Return a configured logger with stream handler."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


# ---------------------------------------------------------------------------
# MongoDB helpers
# ---------------------------------------------------------------------------
def get_mongo_client() -> MongoClient:
    """Create a synchronous MongoDB client."""
    return MongoClient(MONGO_URI)


def write_metrics_to_mongo(metrics: dict):
    """Insert a single metrics document into the model_metrics collection."""
    client = get_mongo_client()
    try:
        db = client[MONGO_DB]
        collection = db[MONGO_METRICS_COLLECTION]
        collection.insert_one(metrics)
    finally:
        client.close()


def write_predictions_to_mongo(records: list):
    """Insert multiple prediction documents into the predictions collection."""
    if not records:
        return
    client = get_mongo_client()
    try:
        db = client[MONGO_DB]
        collection = db[MONGO_COLLECTION]
        collection.insert_many(records)
    finally:
        client.close()
