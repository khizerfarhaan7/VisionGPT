import pytest
from app.core.model_manager import model_manager


def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "project" in data
    assert "version" in data
    assert "docs_url" in data


def test_health_overview(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "components" in data
    assert "models_loaded" in data
    assert isinstance(data["models_loaded"], list)


def test_health_liveness(client):
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("alive", "live")


def test_health_readiness(client):
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("ready", "degraded")


def test_health_zero_model_loading(client):
    # Ensure checking health endpoints loads 0 model weights into memory
    client.get("/api/v1/health")
    client.get("/api/v1/health/live")
    client.get("/api/v1/health/ready")
    assert len(model_manager._models) == 0
