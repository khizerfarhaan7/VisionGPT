import os
from typing import Any, List, Union
from pydantic import BeforeValidator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Annotated


def parse_cors_origins(v: Union[str, List[str]]) -> List[str]:
    if isinstance(v, str):
        v = v.strip()
        if not v:
            return []
        if v.startswith("[") and v.endswith("]"):
            import json
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            except Exception:
                pass
        return [i.strip() for i in v.split(",") if i.strip()]
    elif isinstance(v, list):
        return [str(item).strip() for item in v if str(item).strip()]
    return []


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"), env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )

    PROJECT_NAME: str = "VisionGPT"
    API_V1_STR: str = "/api/v1"
    
    # Environment
    ENVIRONMENT: str = "development"

    # Database
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "visiongpt"
    POSTGRES_PORT: int = 5432
    
    DATABASE_URL: str | None = None

    @property
    def async_database_url(self) -> str:
        if self.DATABASE_URL:
            # Replace prefix if it's sync postgresql
            if self.DATABASE_URL.startswith("postgresql://"):
                return self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
            return self.DATABASE_URL
            
        server = self.POSTGRES_SERVER
        if server == "db" and not os.path.exists("/.dockerenv"):
            import socket
            try:
                socket.gethostbyname(server)
            except Exception:
                server = "localhost"

        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{server}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # JWT
    JWT_SECRET_KEY: str = "dev_placeholder_secret_key_do_not_use_in_production_1234567890"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # CORS
    BACKEND_CORS_ORIGINS: Annotated[
        Union[List[str], str], BeforeValidator(parse_cors_origins)
    ] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Storage
    UPLOAD_DIR: str = "uploads"

    # Resource Profile ("local", "high_quality", "custom")
    VISIONGPT_PROFILE: str = "local"

    # RAG Orchestration Settings ("local", "cloud", "auto")
    RAG_PROVIDER: str = "local"

    # Async Background Job Concurrency Limit (4GB RAM safe)
    MAX_CONCURRENT_JOBS: int = 1

    # API Keys
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-2.5-flash"
    
    # LLM Settings
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:3b"

    # Embedding Settings
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    EMBEDDING_DIMENSION: int = 384

    # Speech Recognition Settings
    WHISPER_MODEL: str = "small"
    WHISPER_DEVICE: str = "cpu"
    WHISPER_COMPUTE_TYPE: str = "int8"

    # Vision Model Settings
    FLORENCE_MODEL_ID: str = "microsoft/Florence-2-base"
    FLORENCE_DEVICE: str = "cpu"

    # Multimodal Video Settings
    VIDEO_INTERVAL_SECONDS: float = 3.0
    VIDEO_WINDOW_SIZE: float = 15.0

    def model_post_init(self, __context: Any) -> None:
        profile = self.VISIONGPT_PROFILE.lower().strip()
        if profile not in ("local", "high_quality", "custom"):
            raise ValueError(f"Invalid VISIONGPT_PROFILE '{self.VISIONGPT_PROFILE}'. Must be 'local', 'high_quality', or 'custom'.")

        if profile == "high_quality":
            # Apply high_quality defaults where defaults were kept
            if self.OLLAMA_MODEL == "qwen2.5:3b":
                self.OLLAMA_MODEL = "qwen2.5:14b"
            if self.EMBEDDING_MODEL == "BAAI/bge-small-en-v1.5":
                self.EMBEDDING_MODEL = "BAAI/bge-large-en-v1.5"
                self.EMBEDDING_DIMENSION = 1024
            if self.WHISPER_MODEL in ("small", "base"):
                self.WHISPER_MODEL = "large-v3"
                self.WHISPER_DEVICE = "cuda"
                self.WHISPER_COMPUTE_TYPE = "float16"
            if self.FLORENCE_MODEL_ID == "microsoft/Florence-2-base":
                self.FLORENCE_MODEL_ID = "microsoft/Florence-2-large"
                self.FLORENCE_DEVICE = "cuda"
            if self.VIDEO_INTERVAL_SECONDS == 3.0:
                self.VIDEO_INTERVAL_SECONDS = 1.0
            if self.VIDEO_WINDOW_SIZE == 15.0:
                self.VIDEO_WINDOW_SIZE = 5.0
            if self.GEMINI_MODEL == "gemini-2.5-flash":
                self.GEMINI_MODEL = "gemini-2.5-pro"


settings = Settings()