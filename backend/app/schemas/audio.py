from pydantic import BaseModel
from typing import List, Optional
from app.schemas.chat import ChatHistoryMessageSchema

class AudioUploadResponseSchema(BaseModel):
    success: bool
    filename: str
    original_name: str
    size: int
    path: str

class AudioTranscribeRequestSchema(BaseModel):
    filename: str

class AudioChunkSchema(BaseModel):
    chunk_id: str
    start_time: float
    end_time: float
    text: str

class AudioTranscribeResponseSchema(BaseModel):
    success: bool
    transcript: str
    detected_language: str
    duration: float
    processing_time: float
    word_count: int
    chunks: List[AudioChunkSchema]

class AudioChatSourceSchema(BaseModel):
    chunk_id: str
    page: str
    similarity_score: float
    start_time: Optional[float] = None
    end_time: Optional[float] = None

class AudioChatRequestSchema(BaseModel):
    filename: str
    question: str
    history: Optional[List[ChatHistoryMessageSchema]] = []

class AudioChatResponseSchema(BaseModel):
    success: bool
    answer: str
    sources: List[AudioChatSourceSchema]
