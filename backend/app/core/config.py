import os
from typing import List, Union
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

    # API Keys
    GEMINI_API_KEY: str | None = None
    
    # LLM Settings
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:3b"

    # Speech Recognition Settings
    WHISPER_MODEL: str = "base"
    WHISPER_DEVICE: str = "cpu"
    WHISPER_COMPUTE_TYPE: str = "int8"


settings = Settings()