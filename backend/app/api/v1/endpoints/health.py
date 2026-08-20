import logging
from fastapi import APIRouter, status

from app.schemas.health import (
    HealthResponseSchema,
    LivenessResponseSchema,
    ReadinessResponseSchema,
)
from app.services.health_service import HealthService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "",
    response_model=HealthResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Detailed backend component health & resource diagnostics"
)
async def get_health():
    """
    Detailed component diagnostics endpoint.
    Reports database, Ollama, Gemini configuration presence, CUDA availability,
    currently cached loaded AI models in RAM, and host memory metrics.
    Guarantees zero AI model loading and never exposes API keys or secrets.
    """
    return await HealthService.get_detailed_health()


@router.get(
    "/live",
    response_model=LivenessResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Liveness probe endpoint"
)
async def get_liveness():
    """
    Liveness probe. Returns HTTP 200 if the backend application process is alive.
    """
    return HealthService.get_liveness()


@router.get(
    "/ready",
    response_model=ReadinessResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Readiness probe endpoint"
)
async def get_readiness():
    """
    Readiness probe. Verifies critical database connectivity without loading any AI models.
    """
    return await HealthService.get_readiness()
