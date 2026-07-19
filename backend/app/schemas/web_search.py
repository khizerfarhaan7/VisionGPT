from pydantic import BaseModel, Field, field_validator
from typing import List, Literal

ContentTypeLiteral = Literal["pdf", "youtube", "audio"]

class WebSearchRequestSchema(BaseModel):
    query: str = Field(..., description="Search query string")
    content_type: ContentTypeLiteral = Field(..., description="Content type filter: pdf, youtube, or audio")

    @field_validator("query")
    @classmethod
    def validate_query_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("query cannot be empty")
        return v.strip()

class SearchResultItemSchema(BaseModel):
    title: str
    url: str
    type: ContentTypeLiteral

class WebSearchResponseSchema(BaseModel):
    success: bool
    results: List[SearchResultItemSchema]
