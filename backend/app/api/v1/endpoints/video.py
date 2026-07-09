import os
import time
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException, status

from app.core.config import settings
from app.schemas.video import VideoChatRequestSchema, VideoChatResponseSchema, VideoIndexRequestSchema
from app.core.rag import execute_local_rag
from app.core.video import index_video_multimodal

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/index", status_code=status.HTTP_200_OK)
async def index_video(payload: VideoIndexRequestSchema):
    """
    Triggers multimodal video frame extraction, speech transcription,
    timeline merging, embedding generation, and FAISS indexing.
    """
    safe_filename = os.path.basename(payload.filename)
    video_path = Path(settings.UPLOAD_DIR) / "audio" / safe_filename
    
    if not video_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested video file was not found in the uploads directory."
        )
        
    try:
        # Run indexing pipeline
        result = index_video_multimodal(
            video_path=video_path,
            interval_seconds=3.0,
            window_size=15.0
        )
        return result
    except Exception as e:
        logger.exception("Failed to index video file")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Video indexing failed: {str(e)}"
        )

@router.post("/chat", response_model=VideoChatResponseSchema, status_code=status.HTTP_200_OK)
async def chat_video(payload: VideoChatRequestSchema):
    """
    Perform local RAG chat over a video's multimodal timeline using FAISS vector retrieval and Ollama.
    Automatically handles missing indices, metadata, and Ollama connection failures gracefully.
    """
    start_time = time.time()
    
    safe_filename = os.path.basename(payload.filename)
    video_id = os.path.splitext(safe_filename)[0]
    
    vector_store_dir = Path(settings.UPLOAD_DIR) / "vector_store" / "video" / video_id
    
    logger.info(f"Received Video Chat request for video_id: '{video_id}'")
    logger.info(f"User Query: '{payload.question}'")
    
    # Verify index presence before calling RAG
    index_path = vector_store_dir / "faiss.index"
    metadata_path = vector_store_dir / "metadata.json"
    
    if not index_path.exists() or not metadata_path.exists():
        logger.error(f"Vector index or metadata missing for video_id '{video_id}' at: {vector_store_dir}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video vector index not found. Please index the video before starting a chat session."
        )
        
    system_prompt = (
        "You are a highly precise AI assistant answering questions based on the provided multimodal timeline (speech transcript + visual frame descriptions) of a video.\n"
        "Follow these strict directives:\n"
        "1. Base your answer ONLY on the provided context timeline (Speech transcripts and Vision captions). Do not assume, extrapolate, or invent facts. Never hallucinate.\n"
        "2. If the answer cannot be determined from the provided timeline context, state clearly that the information is not present in the video.\n"
        "3. Synthesize both visual context (Vision) and spoken context (Speech) to formulate your answer. Refer to timestamps when helpful.\n"
        "4. Keep your answers concise yet complete. Prefer structure and bullet lists when summarizing or listing items.\n"
        "5. Do not reference internal components, vector indexes, FAISS, embeddings, or technical systems in your answers."
    )
    
    try:
        # execute_local_rag handles embedding lookup, FAISS search, query rewriting, and Ollama invocation
        result = await execute_local_rag(
            vector_store_dir=vector_store_dir,
            question=payload.question,
            history=payload.history,
            system_prompt=system_prompt,
            k=3
        )
        
        elapsed_time = time.time() - start_time
        logger.info(f"Video Chat request completed successfully in {elapsed_time:.2f}s for video_id '{video_id}'")
        return result
        
    except HTTPException as he:
        # Passthrough FastAPI HTTPEndpoint exceptions
        logger.warning(f"HTTP exception in Video Chat pipeline: {he.detail}")
        raise he
    except Exception as e:
        logger.exception(f"Unhandled error in Video Chat pipeline: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Video conversational chat failed: {str(e)}"
        )
