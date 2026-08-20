import pytest
import asyncio
from app.services.job_service import JobService


@pytest.mark.asyncio
async def test_job_service_lifecycle():
    # 1. Create Job
    job = await JobService.create_job(
        job_type="pdf_indexing",
        session_id="test_sess_001",
        document_id="doc_123",
        metadata={"filename": "test.pdf"}
    )
    assert job is not None
    job_id = job["job_id"]
    assert job["status"] == "queued"
    assert job["progress"] == 0

    # 2. Update Progress & Start
    updated = await JobService.update_job(
        job_id=job_id,
        status="running",
        progress=45,
        metadata_update={"stage": "embedding"}
    )
    assert updated is not None
    assert updated["status"] == "running"
    assert updated["progress"] == 45

    # 3. Complete Job
    completed = await JobService.complete_job(
        job_id=job_id,
        result_metadata={"indexed_chunks": 12}
    )
    assert completed is not None
    assert completed["status"] == "completed"
    assert completed["progress"] == 100
    assert completed["result"]["indexed_chunks"] == 12

    # 4. Fetch Job Status
    fetched = await JobService.get_job(job_id)
    assert fetched is not None
    assert fetched["status"] == "completed"


@pytest.mark.asyncio
async def test_job_cancellation():
    job = await JobService.create_job(
        job_type="audio_transcription",
        metadata={"filename": "sample.mp3"}
    )
    job_id = job["job_id"]

    cancelled = await JobService.cancel_job(job_id)
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
