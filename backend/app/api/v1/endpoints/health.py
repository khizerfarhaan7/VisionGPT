from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.config import settings
from app.schemas.health import HealthCheckSchema

router = APIRouter()

@router.get("", response_model=HealthCheckSchema, status_code=200)
async def check_health(db: AsyncSession = Depends(get_db)):
    """
    Perform a health check verification.
    Verifies that the API service is running and PostgreSQL is reachable.
    """
    db_status = "healthy"
    try:
        # Perform basic database connectivity query
        await db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
        
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "database": db_status,
        "version": "0.1.0"
    }
