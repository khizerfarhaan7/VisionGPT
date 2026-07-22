import logging
from fastapi import APIRouter, HTTPException, status
from app.schemas.import_schema import ImportAnalyzeRequestSchema, ImportAnalyzeResponseSchema
from app.services.import_service import ImportService

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_CONTENT_TYPES = {"pdf", "youtube", "audio"}

@router.post("/analyze", response_model=ImportAnalyzeResponseSchema)
async def import_and_analyze(request: ImportAnalyzeRequestSchema):
    """
    Import & Analyze backend endpoint foundation.
    Accepts resource URL and content_type, validating input and initializing import pipeline.
    """
    if not request.url or not request.url.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL cannot be empty"
        )

    url_str = request.url.strip()
    if not (url_str.startswith("http://") or url_str.startswith("https://")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid URL format. Must start with http:// or https://"
        )

    if request.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid content_type. Must be one of: {', '.join(ALLOWED_CONTENT_TYPES)}"
        )

    try:
        return await ImportService.import_and_analyze(
            url=url_str,
            content_type=request.content_type
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error in import_and_analyze for URL {url_str}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something went wrong while importing the resource. Please check the URL and try again."
        )
