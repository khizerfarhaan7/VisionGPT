import logging
from fastapi import APIRouter, status

from app.schemas.metrics import MetricsSnapshotSchema
from app.services.metrics_service import MetricsService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "",
    response_model=MetricsSnapshotSchema,
    status_code=status.HTTP_200_OK,
    summary="Get application performance, RAG, job, and model metrics snapshot"
)
async def get_metrics():
    """
    Returns structured JSON performance metrics snapshot.
    Reports total HTTP requests, latencies (average & p95), RAG query counts by provider,
    async job counts, and model invocation frequencies.
    Guarantees zero AI model loading and never exposes API keys, request bodies, or user secrets.
    """
    return MetricsService.get_metrics_snapshot()
