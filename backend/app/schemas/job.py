from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class JobResponseSchema(BaseModel):
    job_id: str = Field(..., description="UUID identifier of the background job")
    job_type: str = Field(..., description="Type of background job ('pdf_indexing', 'audio_transcription', 'video_processing')")
    status: str = Field(..., description="Current state ('queued', 'running', 'completed', 'failed', 'cancelled')")
    progress: int = Field(..., description="Job progress percentage (0-100)")
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None
    document_id: Optional[str] = None
    metadata: Dict[str, Any] = {}
    cancel_requested: bool = False


class JobListResponseSchema(BaseModel):
    jobs: List[JobResponseSchema]
    total_count: int


class JobCancelResponseSchema(BaseModel):
    message: str
    job: JobResponseSchema
