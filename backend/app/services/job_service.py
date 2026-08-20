import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Union

from sqlalchemy import select, update
from app.core.config import settings
from app.core.database import SessionLocal, engine, Base
from app.models import JobRecord

logger = logging.getLogger(__name__)


class JobService:
    """
    Production Async Job Management Service with PostgreSQL Persistence.
    PostgreSQL is the source of truth for job history, statuses, progress, and metadata.
    Enforces 4GB RAM safety via asyncio.Semaphore concurrency locks (MAX_CONCURRENT_JOBS=1).
    Automatically cleans stale queued/running jobs on server restart.
    """

    _semaphore: Optional[asyncio.Semaphore] = None

    @classmethod
    def _get_semaphore(cls) -> asyncio.Semaphore:
        if cls._semaphore is None:
            cls._semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_JOBS)
        return cls._semaphore

    @classmethod
    async def _ensure_tables_exist(cls) -> None:
        """
        Ensures tables are created using AsyncEngine run_sync.
        """
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        except Exception as e:
            logger.warning(f"JobService: Table creation warning: {e}")

    @classmethod
    def _job_record_to_dict(cls, job: JobRecord) -> Dict[str, Any]:
        """
        Converts a JobRecord ORM entity into a standardized dictionary contract.
        """
        return {
            "job_id": str(job.id),
            "job_type": job.job_type,
            "status": job.status,
            "progress": job.progress,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "error": job.error,
            "result": job.result,
            "session_id": str(job.session_id) if job.session_id else None,
            "document_id": str(job.document_id) if job.document_id else None,
            "metadata": job.result or {},
            "cancel_requested": job.cancel_requested
        }

    @classmethod
    async def cleanup_stale_jobs_on_restart(cls) -> int:
        """
        Marks queued or running jobs from prior server sessions as 'interrupted'.
        Prevents stale jobs from falsely appearing active after a restart.
        """
        await cls._ensure_tables_exist()
        try:
            async with SessionLocal() as db:
                stmt = (
                    update(JobRecord)
                    .where(JobRecord.status.in_(["queued", "running"]))
                    .values(
                        status="interrupted",
                        error="Operation interrupted by server restart.",
                        completed_at=datetime.now(timezone.utc)
                    )
                )
                res = await db.execute(stmt)
                await db.commit()
                count = res.rowcount
                if count > 0:
                    logger.info(f"JobService: Marked {count} stale active job(s) as 'interrupted'.")
                return count
        except Exception as e:
            logger.warning(f"JobService: Stale job cleanup skipped/failed: {e}")
            return 0

    @classmethod
    async def create_job(
        cls,
        job_type: str,
        session_id: Optional[Union[str, uuid.UUID]] = None,
        document_id: Optional[Union[str, uuid.UUID]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Creates and persists a new job in PostgreSQL in 'queued' state.
        """
        await cls._ensure_tables_exist()
        job_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        job_rec = JobRecord(
            id=job_id,
            job_type=job_type,
            status="queued",
            progress=0,
            session_id=str(session_id) if session_id else None,
            document_id=str(document_id) if document_id else None,
            result=metadata or {},
            error=None,
            cancel_requested=False,
            created_at=now,
            started_at=None,
            completed_at=None
        )

        try:
            async with SessionLocal() as db:
                db.add(job_rec)
                await db.commit()
                await db.refresh(job_rec)
                logger.info(f"JobService: Persisted job '{job_id}' in DB (Type: '{job_type}')")
                return cls._job_record_to_dict(job_rec)
        except Exception as e:
            logger.error(f"JobService: Failed to create job in DB: {e}")
            # Fallback mock dict if DB is unreachable
            return {
                "job_id": str(job_id),
                "job_type": job_type,
                "status": "queued",
                "progress": 0,
                "created_at": now.isoformat(),
                "started_at": None,
                "completed_at": None,
                "error": None,
                "result": metadata or {},
                "session_id": str(session_id) if session_id else None,
                "document_id": str(document_id) if document_id else None,
                "metadata": metadata or {},
                "cancel_requested": False
            }

    @classmethod
    async def get_job(cls, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a job by UUID from PostgreSQL.
        """
        await cls._ensure_tables_exist()
        try:
            uid = uuid.UUID(str(job_id).strip())
        except ValueError:
            return None

        try:
            async with SessionLocal() as db:
                res = await db.execute(select(JobRecord).where(JobRecord.id == uid))
                job_rec = res.scalar_one_or_none()
                if job_rec:
                    return cls._job_record_to_dict(job_rec)
                return None
        except Exception as e:
            logger.error(f"JobService: Error retrieving job '{job_id}' from DB: {e}")
            return None

    @classmethod
    async def update_job_progress(
        cls,
        job_id: str,
        progress: int,
        status: str = "running",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Updates job progress (0-100) and status in PostgreSQL.
        """
        await cls._ensure_tables_exist()
        try:
            uid = uuid.UUID(str(job_id).strip())
        except ValueError:
            return None

        try:
            async with SessionLocal() as db:
                res = await db.execute(select(JobRecord).where(JobRecord.id == uid))
                job_rec = res.scalar_one_or_none()
                if not job_rec:
                    return None

                if job_rec.cancel_requested and status != "cancelled":
                    job_rec.status = "cancelled"
                    job_rec.completed_at = datetime.now(timezone.utc)
                    await db.commit()
                    await db.refresh(job_rec)
                    return cls._job_record_to_dict(job_rec)

                job_rec.progress = min(max(progress, 0), 100)
                job_rec.status = status

                if status == "running" and not job_rec.started_at:
                    job_rec.started_at = datetime.now(timezone.utc)

                if metadata:
                    curr_res = dict(job_rec.result or {})
                    curr_res.update(metadata)
                    job_rec.result = curr_res

                await db.commit()
                await db.refresh(job_rec)
                return cls._job_record_to_dict(job_rec)
        except Exception as e:
            logger.error(f"JobService: Failed updating job '{job_id}' progress: {e}")
            return None

    @classmethod
    async def complete_job(
        cls,
        job_id: str,
        result_metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Marks job as completed (100%) in PostgreSQL.
        """
        await cls._ensure_tables_exist()
        try:
            uid = uuid.UUID(str(job_id).strip())
        except ValueError:
            return None

        try:
            async with SessionLocal() as db:
                res = await db.execute(select(JobRecord).where(JobRecord.id == uid))
                job_rec = res.scalar_one_or_none()
                if not job_rec:
                    return None

                job_rec.status = "completed"
                job_rec.progress = 100
                job_rec.completed_at = datetime.now(timezone.utc)
                if result_metadata:
                    job_rec.result = result_metadata

                await db.commit()
                await db.refresh(job_rec)
                logger.info(f"JobService: Completed job '{job_id}' in DB.")
                return cls._job_record_to_dict(job_rec)
        except Exception as e:
            logger.error(f"JobService: Failed completing job '{job_id}' in DB: {e}")
            return None

    @classmethod
    async def fail_job(
        cls,
        job_id: str,
        error_message: str
    ) -> Optional[Dict[str, Any]]:
        """
        Marks job as failed with sanitized error string in PostgreSQL.
        """
        await cls._ensure_tables_exist()
        try:
            uid = uuid.UUID(str(job_id).strip())
        except ValueError:
            return None

        clean_err = str(error_message)
        if "API_KEY" in clean_err or "key=" in clean_err:
            clean_err = "Operation failed due to service provider authentication error."

        try:
            async with SessionLocal() as db:
                res = await db.execute(select(JobRecord).where(JobRecord.id == uid))
                job_rec = res.scalar_one_or_none()
                if not job_rec:
                    return None

                job_rec.status = "failed"
                job_rec.completed_at = datetime.now(timezone.utc)
                job_rec.error = clean_err

                await db.commit()
                await db.refresh(job_rec)
                logger.error(f"JobService: Failed job '{job_id}' in DB: {clean_err}")
                return cls._job_record_to_dict(job_rec)
        except Exception as e:
            logger.error(f"JobService: Error recording failure for job '{job_id}': {e}")
            return None

    @classmethod
    async def cancel_job(cls, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Requests cancellation for job in PostgreSQL.
        """
        await cls._ensure_tables_exist()
        try:
            uid = uuid.UUID(str(job_id).strip())
        except ValueError:
            return None

        try:
            async with SessionLocal() as db:
                res = await db.execute(select(JobRecord).where(JobRecord.id == uid))
                job_rec = res.scalar_one_or_none()
                if not job_rec:
                    return None

                if job_rec.status in ("completed", "failed", "cancelled"):
                    return cls._job_record_to_dict(job_rec)

                job_rec.cancel_requested = True
                if job_rec.status == "queued":
                    job_rec.status = "cancelled"
                    job_rec.completed_at = datetime.now(timezone.utc)

                await db.commit()
                await db.refresh(job_rec)
                return cls._job_record_to_dict(job_rec)
        except Exception as e:
            logger.error(f"JobService: Error cancelling job '{job_id}': {e}")
            return None

    @classmethod
    async def list_jobs(
        cls,
        session_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Lists jobs from PostgreSQL sorted by created_at descending.
        """
        await cls._ensure_tables_exist()
        try:
            async with SessionLocal() as db:
                query = select(JobRecord).order_by(JobRecord.created_at.desc()).limit(limit)
                if session_id:
                    query = select(JobRecord).where(JobRecord.session_id == session_id).order_by(JobRecord.created_at.desc()).limit(limit)

                res = await db.execute(query)
                job_recs = res.scalars().all()
                return [cls._job_record_to_dict(j) for j in job_recs]
        except Exception as e:
            logger.error(f"JobService: Error listing jobs from DB: {e}")
            return []

    @classmethod
    def submit_job_task(
        cls,
        job_id: str,
        coro_fn: Callable[..., Any],
        *args: Any,
        **kwargs: Any
    ) -> asyncio.Task:
        """
        Submits a background worker task guarded by the asyncio.Semaphore concurrency lock.
        Updates PostgreSQL on start, progress, completion, failure, and cancellation.
        """
        async def _worker():
            sem = cls._get_semaphore()
            async with sem:
                job = await cls.get_job(job_id)
                if not job or job.get("cancel_requested") or job.get("status") == "cancelled":
                    await cls.update_job_progress(job_id, 0, status="cancelled")
                    return

                await cls.update_job_progress(job_id, 10, status="running")
                try:
                    res = await coro_fn(job_id, *args, **kwargs)
                    curr_j = await cls.get_job(job_id)
                    if curr_j and not curr_j.get("cancel_requested"):
                        await cls.complete_job(job_id, result_metadata=res if isinstance(res, dict) else {"status": "success"})
                    else:
                        await cls.update_job_progress(job_id, curr_j.get("progress", 50) if curr_j else 50, status="cancelled")
                except Exception as ex:
                    logger.error(f"JobService: Worker task error for job '{job_id}': {ex}", exc_info=True)
                    await cls.fail_job(job_id, str(ex))

        return asyncio.create_task(_worker())
