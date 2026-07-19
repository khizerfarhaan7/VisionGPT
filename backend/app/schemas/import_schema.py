from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional

ContentTypeLiteral = Literal["pdf", "youtube", "audio"]

class ImportAnalyzeRequestSchema(BaseModel):
    url: str = Field(..., description="Valid HTTP/HTTPS URL of the resource to import")
    content_type: ContentTypeLiteral = Field(..., description="Content type: pdf, youtube, or audio")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("URL cannot be empty")
        url_str = v.strip()
        if not (url_str.startswith("http://") or url_str.startswith("https://")):
            raise ValueError("URL must start with http:// or https://")
        return url_str

class ImportAnalyzeResponseSchema(BaseModel):
    success: bool
    message: str
    content_type: ContentTypeLiteral
    status: str
    filename: Optional[str] = None
    page_count: Optional[int] = None
    total_vectors: Optional[int] = None
    index_location: Optional[str] = None
    metadata_location: Optional[str] = None
