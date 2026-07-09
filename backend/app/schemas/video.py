from pydantic import BaseModel
from typing import List, Optional
from app.schemas.chat import ChatHistoryMessageSchema

class VideoChatSourceSchema(BaseModel):
    chunk_id: str
    page: str
    similarity_score: float
    start_time: Optional[float] = None
    end_time: Optional[float] = None

class VideoChatRequestSchema(BaseModel):
    filename: str
    question: str
    history: Optional[List[ChatHistoryMessageSchema]] = []

class VideoChatResponseSchema(BaseModel):
    success: bool
    answer: str
    sources: List[VideoChatSourceSchema]

class VideoIndexRequestSchema(BaseModel):
    filename: str
