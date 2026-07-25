import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.api.v1.api import api_router

def init_upload_directories() -> Path:
    """
    Ensure the upload directory and required subdirectories exist.
    """
    base_upload = Path(settings.UPLOAD_DIR).resolve()
    base_upload.mkdir(parents=True, exist_ok=True)
    for subfolder in ["images", "pdfs", "audio", "vector_store", "temp"]:
        (base_upload / subfolder).mkdir(parents=True, exist_ok=True)
    return base_upload

# Initialize upload storage directories synchronously before mounting StaticFiles
uploads_dir = init_upload_directories()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure upload directories remain initialized
    init_upload_directories()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# Configure CORS Middleware using settings
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        # Standardize origins list
        allow_origins=[str(origin).rstrip("/") for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Include API endpoints under API version prefix
app.include_router(api_router, prefix=settings.API_V1_STR)

# Mount uploads folder to serve static files (images, audio, etc.)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

@app.get("/")
def read_root():
    """
    Root API endpoint returning basic project metadata.
    """
    return {
        "project": settings.PROJECT_NAME,
        "docs_url": "/docs",
        "api_v1_url": settings.API_V1_STR
    }
