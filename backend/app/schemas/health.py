from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class LivenessResponseSchema(BaseModel):
    status: str = Field("alive", description="Process liveness status")


class ReadinessResponseSchema(BaseModel):
    status: str = Field("ready", description="Application readiness status")
    database: str = Field("healthy", description="Database connectivity status")
    profile: str = Field("local", description="Active AI model profile")


class ComponentStatusSchema(BaseModel):
    database: str = Field("healthy", description="PostgreSQL database status")
    ollama: str = Field("healthy", description="Ollama endpoint availability")
    gemini: str = Field("configured", description="Gemini API configuration presence")
    model_manager: str = Field("healthy", description="ModelManager status")
    cuda: str = Field("available", description="PyTorch CUDA GPU availability")


class SystemMemorySchema(BaseModel):
    total_gb: Optional[float] = Field(None, description="Total system RAM in GB")
    available_gb: Optional[float] = Field(None, description="Available system RAM in GB")
    percent_used: Optional[float] = Field(None, description="RAM utilization percentage")


class HealthResponseSchema(BaseModel):
    status: str = Field("healthy", description="Overall health status ('healthy' or 'degraded')")
    environment: str = Field("development", description="Application environment")
    profile: str = Field("local", description="Active VisionGPT resource profile")
    components: ComponentStatusSchema
    models_loaded: List[str] = Field(default_factory=list, description="Currently loaded AI models in RAM")
    system_memory: Optional[SystemMemorySchema] = Field(None, description="Host system memory metrics")
    version: str = Field("0.1.0", description="API version")


# Backwards compatibility schema
class HealthCheckSchema(BaseModel):
    status: str
    environment: str
    database: str
    version: str
