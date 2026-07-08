from pydantic import BaseModel

class ImageAnalysisRequestSchema(BaseModel):
    filename: str
    user_prompt: str

class ImageAnalysisResponseSchema(BaseModel):
    success: bool
    answer: str
    confidence: float
