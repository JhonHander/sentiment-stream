"""Tests for GET /health endpoint.

Scenarios:
- Health endpoint returns 200 and status ok.
"""

from fastapi.testclient import TestClient


class TestHealth:
    def test_health_ok(self, client: TestClient):
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
