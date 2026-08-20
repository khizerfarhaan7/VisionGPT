import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional
import httpx
from sqlalchemy import text

from app.core.config import settings
from app.core.model_manager import model_manager

logger = logging.getLogger(__name__)


class HealthService:
    """
    Production Health & Diagnostics Service for VisionGPT.
    Provides lightweight, non-blocking health checks for Liveness (/live),
    Readiness (/ready), and Detailed Component Diagnostics (/health).
    Enforces zero AI model loading during health checks and never exposes secrets.
    """

    @classmethod
    def get_liveness(cls) -> Dict[str, str]:
        """
        Extremely lightweight check. Returns 200 if backend process is alive.
        """
        return {"status": "alive"}

    @classmethod
    async def get_readiness(cls) -> Dict[str, str]:
        """
        Verifies critical readiness dependencies without loading any AI models.
        """
        db_status = await cls._check_database()
        is_ready = db_status == "healthy"

        return {
            "status": "ready" if is_ready else "degraded",
            "database": db_status,
            "profile": settings.VISIONGPT_PROFILE
        }

    @classmethod
    async def get_detailed_health(cls) -> Dict[str, Any]:
        """
        Returns complete component diagnostics, cached loaded models, active profile,
        and system memory info. Never exposes API keys, secrets, or loads AI models.
        """
        db_status = await cls._check_database()
        ollama_status = await cls._check_ollama()
        gemini_status = cls._check_gemini()
        cuda_status = cls._check_cuda()
        memory_info = cls._get_system_memory()

        # Report currently cached loaded models without calling get_model()
        models_loaded = list(model_manager._models.keys())

        # Determine overall health status
        is_healthy = (db_status in ("healthy", "unavailable")) and (ollama_status in ("healthy", "unavailable"))
        overall_status = "healthy" if is_healthy else "degraded"

        return {
            "status": overall_status,
            "environment": settings.ENVIRONMENT,
            "profile": settings.VISIONGPT_PROFILE,
            "components": {
                "database": db_status,
                "ollama": ollama_status,
                "gemini": gemini_status,
                "model_manager": "healthy",
                "cuda": cuda_status
            },
            "models_loaded": models_loaded,
            "system_memory": memory_info,
            "version": "0.1.0"
        }

    @classmethod
    async def _check_database(cls) -> str:
        """
        Performs the smallest safe connectivity query (SELECT 1).
        Does not create or modify tables. Handles DB unavailability gracefully.
        """
        try:
            from app.core.database import SessionLocal
            async with SessionLocal() as db:
                await db.execute(text("SELECT 1"))
            return "healthy"
        except Exception as e:
            logger.warning(f"HealthCheck: Database check failed: {e}")
            return "unavailable"

    @classmethod
    async def _check_ollama(cls) -> str:
        """
        Checks whether configured Ollama endpoint is reachable.
        Does NOT invoke model generation or trigger model downloads.
        """
        url = f"{settings.OLLAMA_BASE_URL}/api/version"
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return "healthy"
                return "unavailable"
        except Exception as e:
            logger.warning(f"HealthCheck: Ollama endpoint '{url}' unreachable: {e}")
            return "unavailable"

    @classmethod
    def _check_gemini(cls) -> str:
        """
        Checks presence of Gemini API key without exposing secret values.
        """
        key = settings.GEMINI_API_KEY
        if key and key != "your_gemini_api_key_here" and len(key.strip()) > 5:
            return "configured"
        return "not_configured"

    @classmethod
    def _check_cuda(cls) -> str:
        """
        Checks PyTorch CUDA GPU availability.
        """
        try:
            import torch
            if torch.cuda.is_available():
                return "available"
            return "unavailable"
        except Exception:
            return "unavailable"

    @classmethod
    def _get_system_memory(cls) -> Optional[Dict[str, float]]:
        """
        Gathers basic host system memory info if psutil is available.
        """
        try:
            import psutil
            mem = psutil.virtual_memory()
            return {
                "total_gb": round(mem.total / (1024 ** 3), 2),
                "available_gb": round(mem.available / (1024 ** 3), 2),
                "percent_used": round(mem.percent, 1)
            }
        except Exception:
            return None
