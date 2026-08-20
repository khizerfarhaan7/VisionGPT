from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class WorkspaceQueryRequestSchema(BaseModel):
    session_id: str = Field(..., description="UUID or identifier of the workspace session")
    question: str = Field(..., description="User query or cross-document question")
    document_ids: Optional[List[str]] = Field(default=None, description="Optional list of document UUIDs to filter by")
    media_types: Optional[List[str]] = Field(default=None, description="Optional list of media types ('pdf', 'audio', 'video', 'image') to filter by")
    mode: Optional[str] = Field(default=None, description="Optional provider override ('local', 'cloud', 'auto')")


class DocumentSummarySchema(BaseModel):
    document_id: str
    filename: str
    media_type: str
    status: str
    is_indexed: bool
    created_at: Optional[str] = None


class WorkspaceSummarySchema(BaseModel):
    session_id: str
    total_documents: int
    modality_distribution: Dict[str, int]
    documents: List[DocumentSummarySchema]
    available_evidence_types: List[str]
    message_count: int


class CitationSchema(BaseModel):
    citation_id: str
    document_id: str
    filename: str
    source_type: str
    locator: str
    relevance_score: float
    supporting_content: str
    metadata: Dict[str, Any] = {}


class SourceUsedSchema(BaseModel):
    document_id: Optional[str] = None
    filename: Optional[str] = None
    source_type: Optional[str] = None


class WorkspaceQueryResponseSchema(BaseModel):
    session_id: str
    workspace_summary: WorkspaceSummarySchema
    answer: str
    citations: List[CitationSchema]
    evidence_count: int
    sources_used: List[SourceUsedSchema]
    confidence: float
    insufficient_evidence: bool
    model_provider: str
    model_name: str
