import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SessionCreateSchema(BaseModel):
    title: Optional[str] = Field(None, description="Optional title for the workspace session")


class SessionUpdateSchema(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="New title for the workspace session")


class SourceReferenceResponseSchema(BaseModel):
    id: uuid.UUID
    source_type: str
    locator: str
    metadata_json: Dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True


class ChatMessageResponseSchema(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    created_at: datetime
    sources: List[SourceReferenceResponseSchema] = []

    class Config:
        from_attributes = True


class VectorStoreResponseSchema(BaseModel):
    id: uuid.UUID
    index_path: str
    embedding_model: str
    chunk_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentResponseSchema(BaseModel):
    id: uuid.UUID
    filename: str
    original_source: str
    media_type: str
    file_path: str
    status: str
    created_at: datetime
    vector_stores: List[VectorStoreResponseSchema] = []

    class Config:
        from_attributes = True


class SessionListItemSchema(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SessionDetailResponseSchema(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime
    documents: List[DocumentResponseSchema] = []
    chat_messages: List[ChatMessageResponseSchema] = []

    class Config:
        from_attributes = True
