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


def parse_file_extensions(v: Union[str, List[str]]) -> List[str]:
    if isinstance(v, str):
        return [ext.strip().lower() if ext.strip().startswith(".") else f".{ext.strip().lower()}" for ext in v.split(",") if ext.strip()]
    elif isinstance(v, list):
        return [str(ext).strip().lower() if str(ext).strip().startswith(".") else f".{str(ext).strip().lower()}" for ext in v if str(ext).strip()]
    return [".pdf", ".txt", ".md", ".mp3", ".wav", ".m4a", ".mp4", ".mov", ".avi", ".webm", ".jpg", ".jpeg", ".png", ".webp"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"), env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )

    PROJECT_NAME: str = "VisionGPT"
    API_V1_STR: str = "/api/v1"
    
    # Environment & Debug
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

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

    # Storage & Upload Limits
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE_MB: int = 100
    ALLOWED_FILE_EXTENSIONS: Annotated[
        Union[List[str], str], BeforeValidator(parse_file_extensions)
    ] = [".pdf", ".txt", ".md", ".mp3", ".wav", ".m4a", ".mp4", ".mov", ".avi", ".webm", ".jpg", ".jpeg", ".png", ".webp"]

    # Resource Profile ("local", "high_quality", "custom")
    VISIONGPT_PROFILE: str = "local"

    # RAG Orchestration Settings ("local", "cloud", "auto")
    RAG_PROVIDER: str = "local"

    # Async Background Job Concurrency Limit (4GB RAM safe)
    MAX_CONCURRENT_JOBS: int = 1

    # Metrics & Observability Configuration
    METRICS_ENABLED: bool = True

    # Security & API Rate Limiting Configuration
    SECURITY_RATE_LIMIT_ENABLED: bool = True
    SECURITY_RATE_LIMIT_REQUESTS: int = 100
    SECURITY_RATE_LIMIT_WINDOW_SECONDS: int = 60

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
        # Validate ENVIRONMENT
        env = self.ENVIRONMENT.lower().strip()
        if env not in ("development", "production", "testing"):
            raise ValueError(f"Invalid ENVIRONMENT '{self.ENVIRONMENT}'. Must be 'development', 'production', or 'testing'.")

        if env == "production":
            self.DEBUG = False
            # Enforce CORS configuration in production
            if not self.BACKEND_CORS_ORIGINS:
                raise ValueError("BACKEND_CORS_ORIGINS must be explicitly specified in production environment.")
            if "*" in self.BACKEND_CORS_ORIGINS:
                raise ValueError("Wildcard '*' origin is forbidden in production when credential support is enabled.")

        # Validate Rate Limit Configuration
        if self.SECURITY_RATE_LIMIT_REQUESTS <= 0:
            raise ValueError(f"Invalid SECURITY_RATE_LIMIT_REQUESTS '{self.SECURITY_RATE_LIMIT_REQUESTS}'. Must be > 0.")
        if self.SECURITY_RATE_LIMIT_WINDOW_SECONDS <= 0:
            raise ValueError(f"Invalid SECURITY_RATE_LIMIT_WINDOW_SECONDS '{self.SECURITY_RATE_LIMIT_WINDOW_SECONDS}'. Must be > 0.")

        # Validate RAG_PROVIDER
        provider = self.RAG_PROVIDER.lower().strip()
        if provider not in ("local", "cloud", "auto"):
            raise ValueError(f"Invalid RAG_PROVIDER '{self.RAG_PROVIDER}'. Must be 'local', 'cloud', or 'auto'.")

        # Validate MAX_CONCURRENT_JOBS & MAX_UPLOAD_SIZE_MB
        if self.MAX_CONCURRENT_JOBS < 1:
            raise ValueError(f"Invalid MAX_CONCURRENT_JOBS '{self.MAX_CONCURRENT_JOBS}'. Must be >= 1.")
        if self.MAX_UPLOAD_SIZE_MB < 1:
            raise ValueError(f"Invalid MAX_UPLOAD_SIZE_MB '{self.MAX_UPLOAD_SIZE_MB}'. Must be >= 1.")

        # Validate LOG_LEVEL
        log_lvl = self.LOG_LEVEL.upper().strip()
        if log_lvl not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            raise ValueError(f"Invalid LOG_LEVEL '{self.LOG_LEVEL}'. Must be DEBUG, INFO, WARNING, ERROR, or CRITICAL.")

        # Validate VISIONGPT_PROFILE & apply profile defaults
        profile = self.VISIONGPT_PROFILE.lower().strip()
        if profile not in ("local", "high_quality", "custom"):
            raise ValueError(f"Invalid VISIONGPT_PROFILE '{self.VISIONGPT_PROFILE}'. Must be 'local', 'high_quality', or 'custom'.")

        if profile == "high_quality":
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

    def __repr__(self) -> str:
        """
        Custom repr representation preventing secret leaks in logs.
        """
        return (
            f"<Settings env='{self.ENVIRONMENT}' profile='{self.VISIONGPT_PROFILE}' "
            f"provider='{self.RAG_PROVIDER}' ollama='{self.OLLAMA_MODEL}' "
            f"gemini_key_set={bool(self.GEMINI_API_KEY)}>"
        )

    def __str__(self) -> str:
        return self.__repr__()


settings = Settings()