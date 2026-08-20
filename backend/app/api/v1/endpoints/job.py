import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, status

from app.schemas.job import (
    JobCancelResponseSchema,
    JobListResponseSchema,
    JobResponseSchema,
)
from app.services.job_service import JobService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/{job_id}",
    response_model=JobResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Get background job status and progress by job_id"
)
async def get_job_status(job_id: str):
    """
    Retrieves the status, progress (0-100), timestamps, and result metadata of a background job.
    """
    job = JobService.get_job(job_id.strip())
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID '{job_id}' was not found."
        )
    return job


@router.get(
    "",
    response_model=JobListResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="List background jobs with optional session filter"
)
async def list_jobs(session_id: Optional[str] = None, limit: int = 50):
    """
    Lists registered background jobs, sorted by creation time descending.
    """
    jobs = JobService.list_jobs(session_id=session_id, limit=limit)
    return {
        "jobs": jobs,
        "total_count": len(jobs)
    }


@router.post(
    "/{job_id}/cancel",
    response_model=JobCancelResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Cancel a queued or running background job"
)
async def cancel_job(job_id: str):
    """
    Requests cancellation for a background job.
    Queued jobs are cancelled immediately; running jobs set a cancellation flag for worker cleanup.
    """
    job = JobService.cancel_job(job_id.strip())
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID '{job_id}' was not found."
        )
    return {
        "message": f"Job '{job_id}' cancellation request recorded.",
        "job": job
    }
