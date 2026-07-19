from fastapi import APIRouter, HTTPException, status
from app.schemas.web_search import WebSearchRequestSchema, WebSearchResponseSchema
from app.services.web_search_service import WebSearchService

router = APIRouter()

ALLOWED_CONTENT_TYPES = {"pdf", "youtube", "audio"}

@router.post("", response_model=WebSearchResponseSchema)
@router.post("/", response_model=WebSearchResponseSchema, include_in_schema=False)
async def web_search(request: WebSearchRequestSchema):
    """
    Web search API endpoint foundation.
    Validates search query and content_type, returning mock search results.
    """
    if not request.query or not request.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query cannot be empty"
        )

    if request.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid content_type. Must be one of: {', '.join(ALLOWED_CONTENT_TYPES)}"
        )

    results = await WebSearchService.search(
        query=request.query.strip(),
        content_type=request.content_type
    )

    return WebSearchResponseSchema(
        success=True,
        results=results
    )
