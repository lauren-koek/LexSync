from fastapi.testclient import TestClient

from backend.main import app


def test_health_returns_backend_status():
    response = TestClient(app).get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "lexsync-backend"}
