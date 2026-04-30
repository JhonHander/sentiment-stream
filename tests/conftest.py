"""pytest fixtures for the Sentiment Stream test suite.

Provides reusable mocks for the FastAPI application state (MongoDB database
and ML model loader) so that unit tests run without external dependencies.
"""

from datetime import datetime
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.services.model_loader import ModelLoader


class FakeDatabase:
    """In-memory fake that mimics the public interface of api.database.Database.

    This avoids the need for a real MongoDB instance during unit tests
    and keeps test execution fast and deterministic.
    """

    def __init__(self) -> None:
        self.predictions: list[dict] = []
        self.metrics: list[dict] = []
        self._id_counter = 0

    def _next_id(self) -> str:
        self._id_counter += 1
        return f"fake_id_{self._id_counter}"

    async def create_indexes(self) -> None:
        pass  # No-op for in-memory store

    async def insert_prediction(self, prediction: dict) -> str:
        doc = dict(prediction)
        doc.setdefault("_id", self._next_id())
        self.predictions.append(doc)
        return doc["_id"]

    async def get_predictions(
        self,
        limit: int = 50,
        offset: int = 0,
        sentiment: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> dict:
        items = self.predictions[:]
        if sentiment:
            items = [i for i in items if i.get("prediction") == sentiment]
        if date_from or date_to:
            filtered = []
            for i in items:
                ts = i.get("timestamp")
                if isinstance(ts, str):
                    ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if date_from and ts and ts < date_from:
                    continue
                if date_to and ts and ts > date_to:
                    continue
                filtered.append(i)
            items = filtered

        total = len(items)
        paginated = items[offset : offset + limit]
        # Strip internal _id for response compatibility
        for p in paginated:
            p.pop("_id", None)
        return {"items": paginated, "total": total, "limit": limit, "offset": offset}

    async def get_stats(self, period: str = "day") -> dict:
        distribution: dict[str, int] = {}
        for p in self.predictions:
            pred = p.get("prediction", "unknown")
            distribution[pred] = distribution.get(pred, 0) + 1

        if not self.predictions:
            return {
                "distribution": {},
                "avg_confidence": 0.0,
                "total": 0,
                "timeseries": [],
            }

        total = len(self.predictions)
        avg_confidence = sum(p.get("confidence", 0.0) for p in self.predictions) / total

        # Simple timeseries grouping by hour for test simplicity
        timeseries: list[dict] = []
        buckets: dict[str, int] = {}
        for p in self.predictions:
            ts = p.get("timestamp")
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            key = ts.strftime("%Y-%m-%dT%H:00:00") if ts else "unknown"
            buckets[key] = buckets.get(key, 0) + 1

        for key in sorted(buckets):
            timeseries.append({"timestamp": key, "count": buckets[key]})

        return {
            "distribution": distribution,
            "avg_confidence": avg_confidence,
            "total": total,
            "timeseries": timeseries,
        }

    async def get_model_metrics(self) -> dict | None:
        if not self.metrics:
            return None
        # Return the latest
        latest = max(self.metrics, key=lambda m: m.get("trained_at", datetime.min))
        precision = latest.get("precision", {})
        recall = latest.get("recall", {})
        f1 = latest.get("f1_score", 0.0)

        classes = ["positivo", "negativo", "neutral"]
        metrics: dict[str, dict[str, float]] = {}
        for cls in classes:
            metrics[cls] = {
                "precision": float(precision.get(cls, 0.0)),
                "recall": float(recall.get(cls, 0.0)),
                "f1": float(f1),
            }

        return {
            "metrics": metrics,
            "model_version": latest.get("model_version", "unknown"),
            "trained_at": latest.get("trained_at", datetime.utcnow()),
        }


def _make_fake_loader() -> MagicMock:
    """Build a MagicMock that satisfies the ModelLoader interface for inference."""
    fake = MagicMock(spec=ModelLoader)
    fake.spark = MagicMock()
    fake.model = MagicMock()
    return fake


@pytest.fixture
def fake_db() -> FakeDatabase:
    """Provide a fresh in-memory fake database per test."""
    return FakeDatabase()


@pytest.fixture
def fake_model_loader() -> MagicMock:
    """Provide a mocked ModelLoader that avoids PySpark startup."""
    return _make_fake_loader()


@pytest.fixture
def client(fake_db: FakeDatabase, fake_model_loader: MagicMock) -> TestClient:
    """Return a FastAPI TestClient with mocked app state.

    Overrides *app.state.db* and *app.state.model_loader* so that no
    real MongoDB or Spark session is required during tests.
    """
    app.state.db = fake_db
    app.state.model_loader = fake_model_loader
    return TestClient(app)
