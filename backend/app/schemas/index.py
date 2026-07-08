from pydantic import BaseModel

class PDFIndexRequestSchema(BaseModel):
    filename: str

class PDFIndexResponseSchema(BaseModel):
    success: bool
    embedding_model: str
    vector_dimension: int
    total_vectors: int
    index_location: str
    metadata_location: str
