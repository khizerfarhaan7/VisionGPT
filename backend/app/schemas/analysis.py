from pydantic import BaseModel
from typing import List, Literal

class ChatMessageSchema(BaseModel):
    role: Literal["user", "assistant"]
    content: str

class ImageAnalysisRequestSchema(BaseModel):
    filename: str
    user_prompt: str
    history: List[ChatMessageSchema] = []

class ImageAnalysisResponseSchema(BaseModel):
    success: bool
    answer: str
