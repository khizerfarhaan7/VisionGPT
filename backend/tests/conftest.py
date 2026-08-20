import os
import shutil
import tempfile
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.metrics_service import MetricsService
from app.core.model_manager import model_manager


@pytest.fixture
def client():
    """
    FastAPI TestClient fixture.
    """
    with TestClient(app) as c:
        yield c


@pytest.fixture
def temp_upload_dir():
    """
    Isolated temporary directory fixture for uploads.
    """
    temp_dir = tempfile.mkdtemp(prefix="visiongpt_test_uploads_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(autouse=True)
def reset_metrics():
    """
    Automatically resets in-memory MetricsService metrics before each test.
    """
    MetricsService.reset_metrics()
    yield
