from pydantic import BaseModel
from typing import List, Literal, Optional, Union

class ChatHistoryMessageSchema(BaseModel):
    role: Literal["user", "assistant"]
    content: str

class PDFChatRequestSchema(BaseModel):
    filename: str
    question: str
    history: Optional[List[ChatHistoryMessageSchema]] = []

class PDFChatSourceSchema(BaseModel):
    chunk_id: str
    page: str
    similarity_score: float

class PDFChatResponseSchema(BaseModel):
    success: bool
    answer: str
    sources: List[PDFChatSourceSchema]

# Schemas for Feature A RAG Chat API (POST /api/v1/chat/query)
class ChatQueryRequestSchema(BaseModel):
    vector_store_id: str
    question: str

class ChatQuerySourceSchema(BaseModel):
    chunk_id: Union[int, str]
    score: float
    preview: str

class ChatQueryResponseSchema(BaseModel):
    success: bool
    answer: str
    retrieved_chunks: int
    sources: List[ChatQuerySourceSchema]

