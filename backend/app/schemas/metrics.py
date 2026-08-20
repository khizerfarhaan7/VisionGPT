from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class RequestsMetricsSchema(BaseModel):
    total: int = Field(0, description="Total HTTP requests processed")
    errors: int = Field(0, description="Total HTTP error responses (>= 400)")
    routes: Dict[str, int] = Field(default_factory=dict, description="Request counts per route")
    error_codes: Dict[int, int] = Field(default_factory=dict, description="Error counts per HTTP status code")


class LatencyMetricsSchema(BaseModel):
    count: int = Field(0, description="Number of latency samples recorded")
    average: float = Field(0.0, description="Average HTTP request latency in ms")
    p95: float = Field(0.0, description="95th percentile HTTP latency in ms")


class RagMetricsSchema(BaseModel):
    total_queries: int = Field(0, description="Total RAG queries processed")
    local_queries: int = Field(0, description="Local Ollama/FAISS RAG queries")
    cloud_queries: int = Field(0, description="Cloud Gemini RAG queries")
    multimodal_queries: int = Field(0, description="Multimodal & workspace RAG queries")
    average_latency_ms: float = Field(0.0, description="Average RAG query latency in ms")


class JobsMetricsSchema(BaseModel):
    by_type: Dict[str, int] = Field(default_factory=dict)
    by_status: Dict[str, int] = Field(default_factory=dict)
    total_completed: int = 0
    total_failed: int = 0
    total_cancelled: int = 0


class MetricsSnapshotSchema(BaseModel):
    status: str = Field("enabled", description="Metrics status ('enabled' or 'disabled')")
    timestamp: Optional[str] = None
    profile: Optional[str] = None
    requests: Optional[RequestsMetricsSchema] = None
    latency_ms: Optional[LatencyMetricsSchema] = None
    rag: Optional[RagMetricsSchema] = None
    jobs: Optional[JobsMetricsSchema] = None
    models: Optional[Dict[str, int]] = Field(default_factory=dict, description="AI model invocation counts")
    message: Optional[str] = None
