from pydantic import BaseModel

class PDFExtractRequestSchema(BaseModel):
    filename: str

class PDFExtractResponseSchema(BaseModel):
    success: bool
    page_count: int
    word_count: int
    character_count: int
    extracted_text: str
