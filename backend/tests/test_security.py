import pytest
from pathlib import Path
from app.core.config import settings, Settings
from app.core.security import sanitize_filename, validate_safe_path
from app.core.exceptions import PermissionError, ValidationError
from app.core.middleware import InProcessRateLimiter


def test_sanitize_filename_valid():
    clean = sanitize_filename("report_2026.pdf")
    assert clean == "report_2026.pdf"


def test_sanitize_filename_traversal():
    clean = sanitize_filename("../../etc/passwd.pdf")
    assert ".." not in clean
    assert "/" not in clean
    assert clean == "passwd.pdf"


def test_sanitize_filename_dangerous_extension():
    with pytest.raises(ValidationError) as exc:
        sanitize_filename("malicious_script.exe")
    assert "prohibited" in str(exc.value).lower()

    with pytest.raises(ValidationError) as exc2:
        sanitize_filename("shell.sh")
    assert "prohibited" in str(exc2.value).lower()


def test_validate_safe_path_valid():
    base_dir = Path("uploads").resolve()
    target = base_dir / "images" / "test.png"
    safe = validate_safe_path(base_dir, target)
    assert safe == target.resolve()


def test_validate_safe_path_traversal():
    base_dir = Path("uploads").resolve()
    target = (base_dir / ".." / "config.py").resolve()
    with pytest.raises(PermissionError) as exc:
        validate_safe_path(base_dir, target)
    assert "traversal" in str(exc.value).lower()


def test_security_response_headers(client):
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


def test_payload_too_large_413(client):
    # Send Content-Length header exceeding MAX_UPLOAD_SIZE_MB
    oversized_bytes = (settings.MAX_UPLOAD_SIZE_MB + 10) * 1024 * 1024
    response = client.get("/api/v1/health/live", headers={"Content-Length": str(oversized_bytes)})
    assert response.status_code == 413
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "PAYLOAD_TOO_LARGE"
    assert "request_id" in data["error"]


def test_rate_limiter_429(client):
    InProcessRateLimiter.reset()
    orig_limit = settings.SECURITY_RATE_LIMIT_REQUESTS
    settings.SECURITY_RATE_LIMIT_REQUESTS = 3

    # Send 3 requests (within limit)
    for _ in range(3):
        r = client.get("/api/v1/health/live")
        assert r.status_code == 200

    # 4th request exceeds rate limit -> HTTP 429
    r_overflow = client.get("/api/v1/health/live")
    assert r_overflow.status_code == 429
    data = r_overflow.json()
    assert data["success"] is False
    assert data["error"]["code"] == "TOO_MANY_REQUESTS"

    # Reset rate limit & restore configuration
    InProcessRateLimiter.reset()
    settings.SECURITY_RATE_LIMIT_REQUESTS = orig_limit


def test_cors_production_wildcard_rejection():
    with pytest.raises(ValueError) as exc:
        Settings(ENVIRONMENT="production", BACKEND_CORS_ORIGINS="*")
    assert "forbidden" in str(exc.value).lower()
