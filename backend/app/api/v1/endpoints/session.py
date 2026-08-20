import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.session import (
    SessionCreateSchema,
    SessionDetailResponseSchema,
    SessionListItemSchema,
    SessionUpdateSchema,
)
from app.services.workspace_service import WorkspaceService

router = APIRouter()


@router.post("", response_model=SessionDetailResponseSchema, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=SessionDetailResponseSchema, status_code=status.HTTP_201_CREATED, include_in_schema=False)
async def create_workspace_session(
    payload: Optional[SessionCreateSchema] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Creates a new workspace session.
    Supports anonymous creation (user_id=None).
    """
    title = payload.title if payload else None
    session = await WorkspaceService.create_session(db=db, title=title)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create workspace session."
        )
    return session


@router.get("", response_model=List[SessionListItemSchema], status_code=status.HTTP_200_OK)
@router.get("/", response_model=List[SessionListItemSchema], status_code=status.HTTP_200_OK, include_in_schema=False)
async def list_workspace_sessions(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """
    Lists workspace sessions ordered by update timestamp descending.
    """
    return await WorkspaceService.list_sessions(db=db, limit=limit, offset=offset)


@router.get("/{session_id}", response_model=SessionDetailResponseSchema, status_code=status.HTTP_200_OK)
async def get_workspace_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves detailed workspace session info including documents, vector store metadata, and chat history.
    """
    session = await WorkspaceService.get_session(db=db, session_id=session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace session not found."
        )
    return session


@router.patch("/{session_id}", response_model=SessionDetailResponseSchema, status_code=status.HTTP_200_OK)
async def update_workspace_session_title(
    session_id: uuid.UUID,
    payload: SessionUpdateSchema,
    db: AsyncSession = Depends(get_db)
):
    """
    Updates workspace session title.
    """
    session = await WorkspaceService.update_session_title(db=db, session_id=session_id, title=payload.title)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace session not found."
        )
    return session


@router.delete("/{session_id}", status_code=status.HTTP_200_OK)
async def delete_workspace_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Deletes a workspace session and cascades deletion to associated messages and documents.
    """
    success = await WorkspaceService.delete_session(db=db, session_id=session_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace session not found or deletion failed."
        )
    return {"success": True, "message": f"Session '{session_id}' deleted successfully."}
