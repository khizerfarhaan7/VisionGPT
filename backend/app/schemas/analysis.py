from pydantic import BaseModel
from typing import List

class ImageAnalysisRequestSchema(BaseModel):
    filename: str

class ImageAnalysisResponseSchema(BaseModel):
    success: bool
    caption: str
    objects_detected: List[str]
    ocr_text: str
    confidence: float
