from pydantic import BaseModel

class PDFUploadResponseSchema(BaseModel):
    success: bool
    filename: str
    original_name: str
    page_count: int
    size: int
    path: str
