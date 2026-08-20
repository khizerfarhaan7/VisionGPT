import os
from pathlib import Path
import pytest
from app.core.config import settings


def test_deployment_config_defaults():
    assert settings.MAX_CONCURRENT_JOBS == 1
    assert settings.VISIONGPT_PROFILE in ("local", "high_quality", "custom")
    assert settings.MAX_UPLOAD_SIZE_MB >= 1


def test_docker_compose_structure():
    compose_path = Path("../docker-compose.yml").resolve()
    if not compose_path.exists():
        compose_path = Path("docker-compose.yml").resolve()

    assert compose_path.exists(), "docker-compose.yml must exist in root directory."
    content = compose_path.read_text(encoding="utf-8")

    assert "services:" in content
    assert "db:" in content
    assert "backend:" in content
    assert "frontend:" in content
    assert "postgres_data:" in content
    assert "uploads_data:" in content


def test_dockerfiles_zero_model_downloads():
    backend_dockerfile = Path("Dockerfile").resolve()
    assert backend_dockerfile.exists()
    content = backend_dockerfile.read_text(encoding="utf-8")

    # Verify zero heavy model download commands during container image build
    forbidden_terms = ["ollama pull", "huggingface-cli download", "torch.hub.download"]
    for term in forbidden_terms:
        assert term not in content.lower(), f"Dockerfile must not download model weights at build time: '{term}'"

    # Verify non-root user
    assert "appuser" in content
    # Verify healthcheck endpoint
    assert "/api/v1/health/live" in content


def test_no_tracked_secrets_in_docker_compose():
    compose_path = Path("../docker-compose.yml").resolve()
    if not compose_path.exists():
        compose_path = Path("docker-compose.yml").resolve()

    content = compose_path.read_text(encoding="utf-8")
    assert "postgres_strong_password_change_me" not in content
    assert "AIzaSy" not in content
