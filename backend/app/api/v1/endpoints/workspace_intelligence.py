import logging
from fastapi import APIRouter, HTTPException, status

from app.schemas.workspace_intelligence import (
    WorkspaceQueryRequestSchema,
    WorkspaceQueryResponseSchema,
    WorkspaceSummarySchema,
)
from app.services.workspace_intelligence_service import WorkspaceIntelligenceService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/query",
    response_model=WorkspaceQueryResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Query workspace knowledge context across heterogeneous documents"
)
async def query_workspace(payload: WorkspaceQueryRequestSchema):
    """
    Multimodal Workspace Intelligence Query endpoint.
    Performs cross-document and cross-modality reasoning across all session documents,
    applies optional document or media_type filters, and returns a grounded answer with citations.
    """
    if not payload.session_id or not payload.session_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="session_id cannot be empty."
        )

    if not payload.question or not payload.question.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="question cannot be empty."
        )

    try:
        return await WorkspaceIntelligenceService.query_workspace(
            session_id=payload.session_id.strip(),
            question=payload.question.strip(),
            document_ids=payload.document_ids,
            media_types=payload.media_types,
            mode=payload.mode
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error in query_workspace endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something went wrong while processing workspace query. Please try again."
        )


@router.get(
    "/{session_id}/summary",
    response_model=WorkspaceSummarySchema,
    status_code=status.HTTP_200_OK,
    summary="Get workspace context summary without invoking LLM"
)
async def get_workspace_summary(session_id: str):
    """
    Returns workspace session summary (document count, modality distribution, indexed status)
    without invoking any LLM models.
    """
    if not session_id or not session_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="session_id cannot be empty."
        )

    try:
        return await WorkspaceIntelligenceService.get_workspace_summary(
            session_id=session_id.strip()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error in get_workspace_summary endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something went wrong while retrieving workspace summary."
        )
