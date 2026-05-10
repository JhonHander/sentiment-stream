"""Tests for POST /predict endpoint.

Scenarios:
- Valid input returns prediction with confidence and timestamp.
- Empty text returns 422.
- Model not loaded returns 503.
"""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from tests.conftest import FakeDatabase


def _mock_transform(
    loader: MagicMock, text: str, prediction_label: str, confidence: float
):
    """Configure the fake loader so that predict_text returns known values."""
    row = MagicMock()
    row.prediction = {"positivo": 0.0, "negativo": 1.0, "neutral": 2.0}.get(
        prediction_label, 0.0
    )
    row.probability = [0.1, 0.1, 0.1]
    # Set the confidence on the predicted class index
    idx = {"positivo": 0, "negativo": 1, "neutral": 2}.get(prediction_label, 0)
    row.probability[idx] = confidence

    prediction_df = MagicMock()
    prediction_df.collect.return_value = [row]
    loader.model.transform.return_value = prediction_df
    loader.spark.createDataFrame.return_value = MagicMock()


class TestPredict:
    def test_predict_valid_input(
        self, client: TestClient, fake_db: FakeDatabase, fake_model_loader: MagicMock
    ):
        _mock_transform(fake_model_loader, "I love this", "positivo", 0.92)

        response = client.post("/predict", json={"text": "I love this product"})

        assert response.status_code == 200
        data = response.json()
        assert data["prediction"] == "positivo"
        assert 0.0 <= data["confidence"] <= 1.0
        assert "timestamp" in data

        # Verify persistence
        assert len(fake_db.predictions) == 1
        assert fake_db.predictions[0]["original_text"] == "I love this product"

    def test_predict_empty_text(self, client: TestClient, fake_model_loader: MagicMock):
        _mock_transform(fake_model_loader, "", "neutral", 0.0)

        response = client.post("/predict", json={"text": "   "})

        assert response.status_code == 422
        assert (
            "vacío" in response.json()["detail"].lower()
            or "empty" in response.json()["detail"].lower()
        )

    def test_predict_model_not_loaded(self, client: TestClient, fake_db: FakeDatabase):
        # Simulate model load failure
        client.app.state.model_loader = None

        response = client.post("/predict", json={"text": "hello"})

        assert response.status_code == 503
        assert (
            "no disponible" in response.json()["detail"].lower()
            or "not available" in response.json()["detail"].lower()
        )

    def test_predict_too_long_text(self, client: TestClient):
        response = client.post("/predict", json={"text": "x" * 1001})
        assert response.status_code == 422
