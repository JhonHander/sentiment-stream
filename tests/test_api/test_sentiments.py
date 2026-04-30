"""Tests for GET /sentiments endpoint.

Scenarios:
- Basic pagination returns correct shape.
- Filtering by sentiment works.
- Empty collection returns empty items with total 0.
"""

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from tests.conftest import FakeDatabase


def _seed_predictions(fake_db: FakeDatabase, n: int = 5):
    for i in range(n):
        sentiment = ["positivo", "negativo", "neutral"][i % 3]
        fake_db.predictions.append(
            {
                "original_text": f"Text {i}",
                "prediction": sentiment,
                "confidence": 0.8,
                "timestamp": datetime(2026, 4, 30, 12, i, 0, tzinfo=timezone.utc),
                "model_version": "v1_test",
            }
        )


class TestSentiments:
    def test_sentiments_pagination(self, client: TestClient, fake_db: FakeDatabase):
        _seed_predictions(fake_db, n=5)

        response = client.get("/sentiments?limit=2&offset=0")

        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 2
        assert data["offset"] == 0
        assert data["total"] == 5
        assert len(data["items"]) == 2

    def test_sentiments_filter_by_sentiment(
        self, client: TestClient, fake_db: FakeDatabase
    ):
        _seed_predictions(fake_db, n=6)

        response = client.get("/sentiments?sentiment=positivo")

        assert response.status_code == 200
        data = response.json()
        assert all(item["prediction"] == "positivo" for item in data["items"])

    def test_sentiments_empty_collection(self, client: TestClient):
        response = client.get("/sentiments")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_sentiments_limit_bounds(self, client: TestClient):
        response = client.get("/sentiments?limit=0")
        assert response.status_code == 422

        response = client.get("/sentiments?limit=2000")
        assert response.status_code == 422
