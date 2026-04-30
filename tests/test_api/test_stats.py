"""Tests for GET /stats and GET /model-metrics endpoints.

Scenarios:
- Stats return distribution, avg_confidence, total, timeseries.
- Model metrics return per-class precision/recall/f1 when available.
- Model metrics return 404 when no metrics exist yet.
"""

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from tests.conftest import FakeDatabase


def _seed_predictions(fake_db: FakeDatabase):
    for i in range(6):
        sentiment = ["positivo", "negativo", "neutral"][i % 3]
        fake_db.predictions.append(
            {
                "original_text": f"Sample {i}",
                "prediction": sentiment,
                "confidence": 0.75 + (i % 3) * 0.05,
                "timestamp": datetime(2026, 4, 30, 12, i, 0, tzinfo=timezone.utc),
                "model_version": "v1_test",
            }
        )


def _seed_metrics(fake_db: FakeDatabase):
    fake_db.metrics.append(
        {
            "accuracy": 0.85,
            "precision": {"positivo": 0.9, "negativo": 0.8, "neutral": 0.7},
            "recall": {"positivo": 0.88, "negativo": 0.78, "neutral": 0.68},
            "f1_score": 0.82,
            "trained_at": datetime(2026, 4, 30, 10, 0, 0, tzinfo=timezone.utc),
            "model_version": "v1_20260430_100000",
        }
    )


class TestStats:
    def test_stats_structure(self, client: TestClient, fake_db: FakeDatabase):
        _seed_predictions(fake_db)

        response = client.get("/stats")

        assert response.status_code == 200
        data = response.json()
        assert "distribution" in data
        assert "avg_confidence" in data
        assert "total" in data
        assert "timeseries" in data
        assert data["total"] == 6

    def test_stats_period_param(self, client: TestClient, fake_db: FakeDatabase):
        _seed_predictions(fake_db)

        response = client.get("/stats?period=hour")
        assert response.status_code == 200

        response = client.get("/stats?period=day")
        assert response.status_code == 200

        response = client.get("/stats?period=invalid")
        assert response.status_code == 422


class TestModelMetrics:
    def test_model_metrics_exists(self, client: TestClient, fake_db: FakeDatabase):
        _seed_metrics(fake_db)

        response = client.get("/model-metrics")

        assert response.status_code == 200
        data = response.json()
        assert "metrics" in data
        assert "model_version" in data
        assert "trained_at" in data
        for cls in ["positivo", "negativo", "neutral"]:
            assert cls in data["metrics"]
            assert "precision" in data["metrics"][cls]
            assert "recall" in data["metrics"][cls]
            assert "f1" in data["metrics"][cls]

    def test_model_metrics_not_found(self, client: TestClient):
        response = client.get("/model-metrics")

        assert response.status_code == 404
        assert (
            "métricas" in response.json()["detail"].lower()
            or "metrics" in response.json()["detail"].lower()
        )
