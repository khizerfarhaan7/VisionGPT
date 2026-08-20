import pytest
from app.services.metrics_service import MetricsService
from app.core.config import settings


def test_metrics_request_recording():
    MetricsService.record_request("GET", "/api/v1/health", 200, 15.5)
    MetricsService.record_request("GET", "/api/v1/invalid", 404, 5.0)

    snap = MetricsService.get_metrics_snapshot()
    assert snap["status"] == "enabled"
    assert snap["requests"]["total"] == 2
    assert snap["requests"]["errors"] == 1
    assert snap["requests"]["error_codes"][404] == 1


def test_metrics_rag_recording():
    MetricsService.record_rag_query("local", "single_source", 100.0)
    MetricsService.record_rag_query("cloud", "multimodal", 300.0)

    snap = MetricsService.get_metrics_snapshot()
    assert snap["rag"]["total_queries"] == 2
    assert snap["rag"]["local_queries"] == 1
    assert snap["rag"]["cloud_queries"] == 1
    assert snap["rag"]["multimodal_queries"] == 1


def test_metrics_job_recording():
    MetricsService.record_job_event("pdf_indexing", "completed")
    MetricsService.record_job_event("pdf_indexing", "failed")

    snap = MetricsService.get_metrics_snapshot()
    assert snap["jobs"]["by_status"]["completed"] == 1
    assert snap["jobs"]["by_status"]["failed"] == 1


def test_metrics_disabled_setting():
    orig = settings.METRICS_ENABLED
    settings.METRICS_ENABLED = False

    MetricsService.record_request("GET", "/api/v1/health", 200, 10.0)
    snap = MetricsService.get_metrics_snapshot()
    assert snap["status"] == "disabled"

    settings.METRICS_ENABLED = orig
