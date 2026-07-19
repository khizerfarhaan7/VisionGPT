from fastapi import APIRouter, HTTPException, status
from app.schemas.chat import ChatQueryRequestSchema, ChatQueryResponseSchema
from app.services.rag_service import RAGService

router = APIRouter()

@router.post("/query", response_model=ChatQueryResponseSchema, status_code=status.HTTP_200_OK)
async def query_rag(payload: ChatQueryRequestSchema):
    """
    RAG Chat API endpoint.
    Accepts a vector_store_id and user question, retrieves relevant knowledge chunks,
    generates a grounded response using Gemini, and returns sources with text previews.
    """
    if not payload.vector_store_id or not payload.vector_store_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="vector_store_id cannot be empty."
        )

    if not payload.question or not payload.question.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="question cannot be empty."
        )

    return await RAGService.answer_question(
        vector_store_id=payload.vector_store_id.strip(),
        question=payload.question.strip()
    )
