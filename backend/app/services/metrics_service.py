import logging
import math
import time
from typing import Any, Dict, List, Optional
from collections import defaultdict

from app.core.config import settings

logger = logging.getLogger(__name__)


class MetricsService:
    """
    Lightweight, In-Memory Production Metrics & Observability System for VisionGPT.
    Tracks API performance, HTTP error rates, RAG query providers, background jobs,
    and AI model invocation frequencies without loading AI models or adding external servers.
    Enforces zero privacy leaks (no request bodies, no user text, no API keys).
    """

    _total_requests: int = 0
    _total_errors: int = 0
    _requests_by_route: Dict[str, int] = defaultdict(int)
    _errors_by_status: Dict[int, int] = defaultdict(int)
    _latencies_ms: List[float] = []

    _rag_total_queries: int = 0
    _rag_local_queries: int = 0
    _rag_cloud_queries: int = 0
    _multimodal_queries: int = 0
    _rag_latencies_ms: List[float] = []

    _jobs_by_type: Dict[str, int] = defaultdict(int)
    _jobs_by_status: Dict[str, int] = defaultdict(int)
    _job_durations_s: List[float] = []

    _model_invocations: Dict[str, int] = defaultdict(int)

    @classmethod
    def record_request(
        cls,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float
    ) -> None:
        """
        Records HTTP request metrics.
        """
        if not settings.METRICS_ENABLED:
            return

        cls._total_requests += 1
        route_key = f"{method.upper()} {path}"
        cls._requests_by_route[route_key] += 1

        if status_code >= 400:
            cls._total_errors += 1
            cls._errors_by_status[status_code] += 1

        # Keep last 1000 latency samples for bounded memory usage
        cls._latencies_ms.append(duration_ms)
        if len(cls._latencies_ms) > 1000:
            cls._latencies_ms.pop(0)

    @classmethod
    def record_rag_query(
        cls,
        provider: str,
        query_type: str = "single_source",
        duration_ms: float = 0.0
    ) -> None:
        """
        Records RAG query execution metrics.
        """
        if not settings.METRICS_ENABLED:
            return

        cls._rag_total_queries += 1
        prov_lower = str(provider).lower()
        if "local" in prov_lower or "ollama" in prov_lower:
            cls._rag_local_queries += 1
        elif "cloud" in prov_lower or "gemini" in prov_lower:
            cls._rag_cloud_queries += 1

        if "multimodal" in str(query_type).lower() or "workspace" in str(query_type).lower() or "comparison" in str(query_type).lower():
            cls._multimodal_queries += 1

        if duration_ms > 0:
            cls._rag_latencies_ms.append(duration_ms)
            if len(cls._rag_latencies_ms) > 1000:
                cls._rag_latencies_ms.pop(0)

    @classmethod
    def record_job_event(
        cls,
        job_type: str,
        status: str,
        duration_s: Optional[float] = None
    ) -> None:
        """
        Records background job processing metrics.
        """
        if not settings.METRICS_ENABLED:
            return

        cls._jobs_by_type[job_type] += 1
        cls._jobs_by_status[status] += 1

        if duration_s and duration_s > 0:
            cls._job_durations_s.append(duration_s)
            if len(cls._job_durations_s) > 500:
                cls._job_durations_s.pop(0)

    @classmethod
    def record_model_invocation(cls, provider_model: str) -> None:
        """
        Records AI model invocation count.
        """
        if not settings.METRICS_ENABLED:
            return

        cls._model_invocations[provider_model] += 1

    @classmethod
    def get_metrics_snapshot(cls) -> Dict[str, Any]:
        """
        Returns machine-readable JSON metrics snapshot.
        """
        if not settings.METRICS_ENABLED:
            return {
                "status": "disabled",
                "message": "Metrics collection is disabled via configuration."
            }

        lat_count = len(cls._latencies_ms)
        avg_lat = round(sum(cls._latencies_ms) / lat_count, 2) if lat_count > 0 else 0.0

        p95_lat = 0.0
        if lat_count > 0:
            sorted_lat = sorted(cls._latencies_ms)
            idx = math.ceil(0.95 * lat_count) - 1
            p95_lat = round(sorted_lat[min(max(idx, 0), lat_count - 1)], 2)

        rag_count = len(cls._rag_latencies_ms)
        avg_rag_lat = round(sum(cls._rag_latencies_ms) / rag_count, 2) if rag_count > 0 else 0.0

        return {
            "status": "enabled",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "profile": settings.VISIONGPT_PROFILE,
            "requests": {
                "total": cls._total_requests,
                "errors": cls._total_errors,
                "routes": dict(cls._requests_by_route),
                "error_codes": dict(cls._errors_by_status)
            },
            "latency_ms": {
                "count": lat_count,
                "average": avg_lat,
                "p95": p95_lat
            },
            "rag": {
                "total_queries": cls._rag_total_queries,
                "local_queries": cls._rag_local_queries,
                "cloud_queries": cls._rag_cloud_queries,
                "multimodal_queries": cls._multimodal_queries,
                "average_latency_ms": avg_rag_lat
            },
            "jobs": {
                "by_type": dict(cls._jobs_by_type),
                "by_status": dict(cls._jobs_by_status),
                "total_completed": cls._jobs_by_status.get("completed", 0),
                "total_failed": cls._jobs_by_status.get("failed", 0),
                "total_cancelled": cls._jobs_by_status.get("cancelled", 0)
            },
            "models": dict(cls._model_invocations)
        }

    @classmethod
    def reset_metrics(cls) -> None:
        """
        Resets metrics counters (useful for isolated testing).
        """
        cls._total_requests = 0
        cls._total_errors = 0
        cls._requests_by_route.clear()
        cls._errors_by_status.clear()
        cls._latencies_ms.clear()
        cls._rag_total_queries = 0
        cls._rag_local_queries = 0
        cls._rag_cloud_queries = 0
        cls._multimodal_queries = 0
        cls._rag_latencies_ms.clear()
        cls._jobs_by_type.clear()
        cls._jobs_by_status.clear()
        cls._job_durations_s.clear()
        cls._model_invocations.clear()
