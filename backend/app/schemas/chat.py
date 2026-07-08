from pydantic import BaseModel
from typing import List, Literal, Optional

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
