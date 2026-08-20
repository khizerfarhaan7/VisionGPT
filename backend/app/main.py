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

tags_metadata = [
    {
        "name": "health",
        "description": "System health diagnostics, PostgreSQL connectivity, ModelManager status, Ollama availability, Gemini readiness, and host resource statistics."
    },
    {
        "name": "jobs",
        "description": "Asynchronous background processing job queue for tracked PDF indexing, audio transcription, and video processing with real-time polling and cancellation."
    },
    {
        "name": "metrics",
        "description": "Lightweight performance and observability metrics reporting HTTP request counts, average & p95 latencies, RAG provider usage, and AI model invocation counts."
    },
    {
        "name": "chat",
        "description": "Multimodal Grounded Answer engine, RAG query router, evidence citation engine, and interactive document chat."
    },
    {
        "name": "workspace-intelligence",
        "description": "Unified session workspace context analysis, cross-modal knowledge summaries, and workspace-wide RAG query routing."
    },
    {
        "name": "pdf",
        "description": "PDF document extraction, intelligent chunking, FAISS vector indexing, and PDF document chat."
    },
    {
        "name": "audio",
        "description": "Voice audio transcription using Faster-Whisper, timestamped chunk indexing, and voice Q&A."
    },
    {
        "name": "video",
        "description": "Multimodal video analysis using keyframe extraction, Florence-2 vision processing, timeline indexing, and video chat."
    },
    {
        "name": "upload",
        "description": "Multi-format file upload storage and workspace document registration."
    },
    {
        "name": "analyze",
        "description": "Vision model image description, object detection, and visual Q&A."
    },
    {
        "name": "web-search",
        "description": "Web search integration, real-time internet context retrieval, and web page reading."
    },
    {
        "name": "import",
        "description": "Dynamic web page scraping, resource analysis, and web page indexing."
    },
    {
        "name": "sessions",
        "description": "Workspace session creation, document grouping, and session lifecycle management."
    }
]

app_description = """
### VisionGPT Multimodal RAG & Intelligence System

VisionGPT is an enterprise-grade, privacy-first **Multimodal Retrieval-Augmented Generation (RAG)** platform capable of understanding PDFs, images, voice audio, video timelines, and web content.

#### Core Platform Features
* **Traceable Evidence & Citation Engine**: Every answer claim is grounded in verifiable evidence with precise locators (PDF page numbers, audio timestamps, video timestamps, image references).
* **Intelligent Query Router**: Automatically classifies incoming user queries into `single_source`, `multimodal`, `workspace`, or `comparison` pipelines.
* **Workspace Intelligence**: Operates over an entire connected workspace session as a single unified context.
* **Persistent Async Job Queue**: Non-blocking long-running task processing backed by PostgreSQL with real-time polling and job cancellation.
* **Production Diagnostics & Observability**: Health readiness endpoints and in-memory performance metrics (request rates, p95 latencies, model invocation counters).
* **4GB RAM Safety Profile**: Lazy model loading and strict single-job concurrency (`MAX_CONCURRENT_JOBS=1`) ensure consumer laptop compatibility.
"""

app = FastAPI(
    title="VisionGPT Multimodal RAG & Intelligence API",
    description=app_description,
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    openapi_tags=tags_metadata,
    lifespan=lifespan
)

# Configure CORS Middleware using settings
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin).rstrip("/") for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Register Request Logging & Exception Handlers
from app.core.middleware import setup_middleware_and_exceptions
setup_middleware_and_exceptions(app)

# Include API endpoints under API version prefix
app.include_router(api_router, prefix=settings.API_V1_STR)

# Mount uploads folder to serve static files (images, audio, etc.)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

@app.get("/", tags=["health"])
def read_root():
    """
    Root API endpoint returning basic project metadata.
    """
    return {
        "project": settings.PROJECT_NAME,
        "version": "1.0.0",
        "docs_url": "/docs",
        "openapi_url": f"{settings.API_V1_STR}/openapi.json",
        "api_v1_url": settings.API_V1_STR
    }
