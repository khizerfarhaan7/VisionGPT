from fastapi import APIRouter
from app.api.v1.endpoints import health, upload

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(upload.router, prefix="/upload", tags=["upload"])
