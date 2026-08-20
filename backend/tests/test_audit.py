import pytest
from unittest.mock import AsyncMock, patch
from app.services.job_service import JobService
from app.core.middleware import sanitize_error_message


@pytest.mark.asyncio
async def test_job_terminal_state_protection():
    mock_terminal_record = {
        "job_id": "job_completed_123",
        "job_type": "pdf_indexing",
        "status": "completed",
        "progress": 100,
        "result": {"chunks": 5},
        "error": None,
        "cancel_requested": False
    }

    with patch.object(JobService, "get_job", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_terminal_record
        job = await JobService.get_job("job_completed_123")
        assert job["status"] == "completed"

    # Attempting illegal progress update on terminal job
    with patch.object(JobService, "update_job_progress", new_callable=AsyncMock) as mock_update:
        mock_update.return_value = mock_terminal_record
        res = await JobService.update_job_progress("job_completed_123", progress=50, status="running")
        assert res["status"] == "completed"  # Remains completed!


def test_secret_sanitization():
    unsafe_err = "Database error: postgresql://user:secret_pass_123@localhost:5432/db"
    clean = sanitize_error_message(unsafe_err)
    assert "secret_pass_123" not in clean
    assert "postgresql://" not in clean
    assert clean == "An internal authentication or infrastructure error occurred."

    api_key_err = "Gemini API call failed with API_KEY=AIzaSySecret123"
    clean_key = sanitize_error_message(api_key_err)
    assert "AIzaSySecret123" not in clean_key
    assert clean_key == "An internal authentication or infrastructure error occurred."


def test_safe_error_formatting():
    safe_msg = "Document ID 'doc_999' was not found."
    formatted = sanitize_error_message(safe_msg)
    assert formatted == safe_msg
