from pydantic import BaseModel
from typing import List, Union

class ChunkItemSchema(BaseModel):
    chunk_id: str
    page: Union[int, str]
    text: str

class PDFChunkRequestSchema(BaseModel):
    text: str

class PDFChunkResponseSchema(BaseModel):
    success: bool
    total_chunks: int
    average_chunk_size: int
    chunks: List[ChunkItemSchema]
