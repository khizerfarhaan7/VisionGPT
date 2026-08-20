from fastapi import APIRouter
from app.api.v1.endpoints import health, upload, analysis, pdf, audio, video, web_search, import_analyze, dev, chat, session, workspace_intelligence, job

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(session.router, prefix="/sessions", tags=["sessions"])
api_router.include_router(job.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(workspace_intelligence.router, prefix="/workspace", tags=["workspace-intelligence"])
api_router.include_router(upload.router, prefix="/upload", tags=["upload"])
api_router.include_router(analysis.router, prefix="/analyze", tags=["analyze"])
api_router.include_router(pdf.router, prefix="/pdf", tags=["pdf"])
api_router.include_router(audio.router, prefix="/audio", tags=["audio"])
api_router.include_router(video.router, prefix="/video", tags=["video"])
api_router.include_router(web_search.router, prefix="/web-search", tags=["web-search"])
api_router.include_router(import_analyze.router, prefix="/import", tags=["import"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
# TEMPORARY DEVELOPMENT ENDPOINT ONLY
api_router.include_router(dev.router, prefix="/dev", tags=["dev"])



