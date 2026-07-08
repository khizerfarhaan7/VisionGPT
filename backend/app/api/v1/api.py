from fastapi import APIRouter
from app.api.v1.endpoints import health, upload, analysis, pdf, audio

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(upload.router, prefix="/upload", tags=["upload"])
api_router.include_router(analysis.router, prefix="/analyze", tags=["analyze"])
api_router.include_router(pdf.router, prefix="/pdf", tags=["pdf"])
api_router.include_router(audio.router, prefix="/audio", tags=["audio"])
