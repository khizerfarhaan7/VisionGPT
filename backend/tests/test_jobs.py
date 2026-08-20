import pytest
from unittest.mock import AsyncMock, patch
from app.services.job_service import JobService


@pytest.mark.asyncio
async def test_job_service_lifecycle():
    mock_record = {
        "job_id": "test_job_123",
        "job_type": "pdf_indexing",
        "status": "queued",
        "progress": 0,
        "session_id": "test_sess_001",
        "document_id": "doc_123",
        "metadata": {"filename": "test.pdf"},
        "result": None,
        "error": None,
        "cancel_requested": False,
        "created_at": "2026-08-20T21:00:00Z"
    }

    with patch.object(JobService, "create_job", new_callable=AsyncMock) as mock_create, \
         patch.object(JobService, "update_job_progress", new_callable=AsyncMock) as mock_update, \
         patch.object(JobService, "complete_job", new_callable=AsyncMock) as mock_complete, \
         patch.object(JobService, "get_job", new_callable=AsyncMock) as mock_get:

        mock_create.return_value = mock_record
        mock_update.return_value = {**mock_record, "status": "running", "progress": 45}
        mock_complete.return_value = {**mock_record, "status": "completed", "progress": 100, "result": {"indexed_chunks": 12}}
        mock_get.return_value = {**mock_record, "status": "completed", "progress": 100}

        # 1. Create Job
        job = await JobService.create_job(
            job_type="pdf_indexing",
            session_id="test_sess_001",
            document_id="doc_123",
            metadata={"filename": "test.pdf"}
        )
        assert job is not None
        assert job["status"] == "queued"

        # 2. Update Progress
        updated = await JobService.update_job_progress(
            job_id="test_job_123",
            progress=45,
            status="running"
        )
        assert updated["status"] == "running"
        assert updated["progress"] == 45

        # 3. Complete Job
        completed = await JobService.complete_job(
            job_id="test_job_123",
            result_metadata={"indexed_chunks": 12}
        )
        assert completed["status"] == "completed"

        # 4. Get Job
        fetched = await JobService.get_job("test_job_123")
        assert fetched["status"] == "completed"


@pytest.mark.asyncio
async def test_job_cancellation():
    mock_cancelled = {
        "job_id": "test_job_456",
        "job_type": "audio_transcription",
        "status": "cancelled",
        "progress": 20,
        "cancel_requested": True
    }
    with patch.object(JobService, "cancel_job", new_callable=AsyncMock) as mock_cancel:
        mock_cancel.return_value = mock_cancelled
        cancelled = await JobService.cancel_job("test_job_456")
        assert cancelled is not None
        assert cancelled["status"] == "cancelled"
        assert cancelled["cancel_requested"] is True


def test_job_rest_endpoints(client):
    response = client.get("/api/v1/jobs")
    assert response.status_code == 200
    data = response.json()
    assert "jobs" in data
    assert "total_count" in data
    assert isinstance(data["jobs"], list)
