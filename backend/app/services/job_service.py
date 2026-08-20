import asyncio
import logging
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Union

from app.core.config import settings

logger = logging.getLogger(__name__)


class JobService:
    """
    In-process Production Async Job Management Service for VisionGPT.
    Tracks long-running multimodal operations (PDF indexing, Audio STT, Video processing)
    with non-blocking HTTP tracking, progress hooks, cancellation, and concurrency limits (MAX_CONCURRENT_JOBS=1 by default).
    Does NOT require Celery/Redis; enforces 4GB RAM memory safety via sequential asyncio semaphore locks.
    """

    _jobs: Dict[str, Dict[str, Any]] = {}
    _semaphore: Optional[asyncio.Semaphore] = None

    @classmethod
    def _get_semaphore(cls) -> asyncio.Semaphore:
        if cls._semaphore is None:
            cls._semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_JOBS)
        return cls._semaphore

    @classmethod
    def create_job(
        cls,
        job_type: str,
        session_id: Optional[Union[str, uuid.UUID]] = None,
        document_id: Optional[Union[str, uuid.UUID]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Creates and registers a new job in 'queued' state.
        """
        job_id = str(uuid.uuid4())
        now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        job = {
            "job_id": job_id,
            "job_type": job_type,
            "status": "queued",
            "progress": 0,
            "created_at": now_str,
            "started_at": None,
            "completed_at": None,
            "error": None,
            "result": None,
            "session_id": str(session_id) if session_id else None,
            "document_id": str(document_id) if document_id else None,
            "metadata": metadata or {},
            "cancel_requested": False
        }

        cls._jobs[job_id] = job
        logger.info(f"JobService: Created job '{job_id}' (Type: '{job_type}', Session: '{session_id}')")
        return job

    @classmethod
    def get_job(cls, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves job status dictionary by job_id.
        """
        return cls._jobs.get(job_id)

    @classmethod
    def update_job_progress(
        cls,
        job_id: str,
        progress: int,
        status: str = "running",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Updates job progress (0-100) and optional status or metadata.
        """
        job = cls._jobs.get(job_id)
        if not job:
            return None

        # Check if job was cancelled
        if job.get("cancel_requested") and status != "cancelled":
            job["status"] = "cancelled"
            job["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            logger.info(f"JobService: Job '{job_id}' transition halted due to cancellation request.")
            return job

        job["progress"] = min(max(progress, 0), 100)
        job["status"] = status

        if status == "running" and not job["started_at"]:
            job["started_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        if metadata:
            job["metadata"].update(metadata)

        logger.info(f"JobService: Job '{job_id}' progress -> {job['progress']}% ({status})")
        return job

    @classmethod
    def complete_job(
        cls,
        job_id: str,
        result_metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Marks job as completed (100% progress).
        """
        job = cls._jobs.get(job_id)
        if not job:
            return None

        job["status"] = "completed"
        job["progress"] = 100
        job["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        if result_metadata:
            job["result"] = result_metadata

        logger.info(f"JobService: Job '{job_id}' completed successfully.")
        return job

    @classmethod
    def fail_job(
        cls,
        job_id: str,
        error_message: str
    ) -> Optional[Dict[str, Any]]:
        """
        Marks job as failed cleanly without swallowing exception details.
        Sanitizes error string to prevent secret exposure.
        """
        job = cls._jobs.get(job_id)
        if not job:
            return None

        job["status"] = "failed"
        job["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        
        # Sanitize error message
        clean_err = str(error_message)
        if "API_KEY" in clean_err or "key=" in clean_err:
            clean_err = "Operation failed due to service provider authentication error."

        job["error"] = clean_err
        logger.error(f"JobService: Job '{job_id}' failed: {clean_err}")
        return job

    @classmethod
    def cancel_job(cls, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Requests job cancellation. If queued, cancels immediately.
        If running, sets cancel_requested flag for worker task cleanup.
        """
        job = cls._jobs.get(job_id)
        if not job:
            return None

        if job["status"] in ("completed", "failed", "cancelled"):
            return job

        job["cancel_requested"] = True
        if job["status"] == "queued":
            job["status"] = "cancelled"
            job["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            logger.info(f"JobService: Queued job '{job_id}' cancelled immediately.")
        else:
            logger.info(f"JobService: Cancellation requested for running job '{job_id}'.")

        return job

    @classmethod
    def list_jobs(
        cls,
        session_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Lists registered jobs, sorted by creation time descending.
        """
        all_jobs = list(cls._jobs.values())
        if session_id:
            all_jobs = [j for j in all_jobs if j.get("session_id") == session_id]

        all_jobs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return all_jobs[:limit]

    @classmethod
    def submit_job_task(
        cls,
        job_id: str,
        coro_fn: Callable[..., Any],
        *args: Any,
        **kwargs: Any
    ) -> asyncio.Task:
        """
        Submits a worker coroutine task to execute under the job concurrency semaphore limit (1 job by default).
        Handles progress tracking, completion, failure, and cancellation.
        """
        async def _worker():
            sem = cls._get_semaphore()
            async with sem:
                job = cls.get_job(job_id)
                if not job or job.get("cancel_requested") or job.get("status") == "cancelled":
                    cls.update_job_progress(job_id, 0, status="cancelled")
                    return

                cls.update_job_progress(job_id, 10, status="running")
                try:
                    res = await coro_fn(job_id, *args, **kwargs)
                    if not cls.get_job(job_id).get("cancel_requested"):
                        cls.complete_job(job_id, result_metadata=res if isinstance(res, dict) else {"status": "success"})
                    else:
                        cls.update_job_progress(job_id, job.get("progress", 50), status="cancelled")
                except Exception as ex:
                    logger.error(f"JobService: Worker execution error for job '{job_id}': {ex}", exc_info=True)
                    cls.fail_job(job_id, str(ex))

        return asyncio.create_task(_worker())
