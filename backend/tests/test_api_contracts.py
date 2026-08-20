import json
import pytest
from app.main import app
from app.core.config import Settings


def test_request_id_generation(client):
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    assert len(response.headers["X-Request-ID"]) > 10


def test_request_id_propagation(client):
    custom_id = "custom-test-req-9999"
    response = client.get("/api/v1/health/live", headers={"X-Request-ID": custom_id})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == custom_id


def test_structured_404_response(client):
    response = client.get("/api/v1/non_existent_route_12345")
    assert response.status_code == 404
    data = response.json()
    assert data["success"] is False
    assert "error" in data
    assert data["error"]["code"] in ("NOT_FOUND", "HTTP_ERROR")
    assert "request_id" in data["error"]


def test_structured_422_validation_response(client):
    response = client.post("/api/v1/pdf/index", json={})
    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert "details" in data["error"]
    assert "request_id" in data["error"]


def test_openapi_schema_generation():
    schema = app.openapi()
    assert schema["info"]["title"] == "VisionGPT Multimodal RAG & Intelligence API"
    assert schema["info"]["version"] == "1.0.0"
    paths = schema["paths"]
    assert "/api/v1/health" in paths
    assert "/api/v1/metrics" in paths
    assert "/api/v1/jobs" in paths
    assert "/api/v1/chat/query" in paths


def test_secret_masking_in_settings():
    s = Settings(POSTGRES_PASSWORD="my_db_secret_pass_123", GEMINI_API_KEY="my_gemini_secret_key_456")
    repr_str = repr(s)
    assert "my_db_secret_pass_123" not in repr_str
    assert "my_gemini_secret_key_456" not in repr_str
