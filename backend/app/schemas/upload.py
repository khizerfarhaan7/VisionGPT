from pydantic import BaseModel

class ImageUploadResponseSchema(BaseModel):
    success: bool
    filename: str
    original_name: str
    content_type: str
    size: int
    path: str
