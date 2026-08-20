import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from fastapi import HTTPException, status

from app.core.config import settings
from app.core.rag import execute_local_rag
from app.services.rag_service import RAGService

logger = logging.getLogger(__name__)


class RagOrchestrator:
    """
    Unified RAG Orchestration Layer for VisionGPT.
    Routes RAG queries to Local RAG (FAISS + Ollama) or Cloud RAG (Gemini)
    without duplicating retrieval logic, and normalizes responses into a single structure.
    Designed for future extensibility (multimodal routing, evidence ranking, agents).
    """

    @classmethod
    async def query(
        cls,
        question: str,
        vector_store_dir: Optional[Union[str, Path]] = None,
        vector_store_id: Optional[str] = None,
        history: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        k: int = 3,
        session_id: Optional[Any] = None,
        mode: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Unified RAG query entrance.
        Determines requested mode ('local', 'cloud', 'auto'), executes retrieval,
        and returns a normalized response contract.
        """
        start_time = time.time()
        requested_mode = (mode or getattr(settings, "RAG_PROVIDER", "local")).lower().strip()

        if requested_mode not in ("local", "cloud", "auto"):
            logger.warning(f"RagOrchestrator: Invalid RAG mode '{requested_mode}'. Defaulting to 'local'.")
            requested_mode = "local"

        # Determine effective provider (Privacy rule: 'auto' defaults to 'local' if local index exists)
        resolved_provider = cls._resolve_provider(
            mode=requested_mode,
            vector_store_dir=vector_store_dir,
            vector_store_id=vector_store_id
        )

        logger.info(
            f"RagOrchestrator: Dispatching query (mode='{requested_mode}' -> resolved='{resolved_provider}') "
            f"for question: '{question[:50]}...'"
        )

        if resolved_provider == "local":
            return await cls._execute_local_flow(
                question=question,
                vector_store_dir=vector_store_dir,
                history=history or [],
                system_prompt=system_prompt,
                k=k,
                session_id=session_id,
                start_time=start_time
            )
        else:
            return await cls._execute_cloud_flow(
                question=question,
                vector_store_id=vector_store_id,
                k=k,
                session_id=session_id,
                start_time=start_time
            )

    @classmethod
    def _resolve_provider(
        cls,
        mode: str,
        vector_store_dir: Optional[Union[str, Path]],
        vector_store_id: Optional[str]
    ) -> str:
        """
        Resolves effective provider ('local' vs 'cloud').
        Enforces privacy: 'auto' mode will NEVER send private document content to cloud if local vector store directory is passed.
        """
        if mode == "local":
            return "local"
        elif mode == "cloud":
            return "cloud"
        else:  # 'auto' mode
            if vector_store_dir is not None:
                return "local"
            if vector_store_id:
                return "cloud"
            return "local"

    @classmethod
    async def _execute_local_flow(
        cls,
        question: str,
        vector_store_dir: Optional[Union[str, Path]],
        history: List[Dict[str, Any]],
        system_prompt: Optional[str],
        k: int,
        session_id: Optional[Any],
        start_time: float
    ) -> Dict[str, Any]:
        if not vector_store_dir:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Local RAG requires a valid vector_store_dir path."
            )

        v_dir = Path(vector_store_dir)
        default_prompt = (
            system_prompt or
            "You are VisionGPT. Answer strictly using the provided context."
        )

        local_result = await execute_local_rag(
            vector_store_dir=v_dir,
            question=question,
            history=history,
            system_prompt=default_prompt,
            k=k,
            session_id=session_id
        )

        elapsed = round(time.time() - start_time, 3)
        sources = local_result.get("sources", [])
        
        # Build normalized citation list
        citations = []
        for s in sources:
            citations.append({
                "source_type": s.get("page", "document"),
                "locator": str(s.get("page", s.get("chunk_id", "unknown"))),
                "score": s.get("score", 0.0),
                "text_snippet": s.get("text", s.get("preview", ""))[:150]
            })

        return {
            "success": local_result.get("success", True),
            "answer": local_result.get("answer", ""),
            "sources": sources,
            "citations": citations,
            "retrieval_metadata": {
                "provider": "local_ollama",
                "model": settings.OLLAMA_MODEL,
                "search_k": k,
                "processing_time": elapsed
            },
            "model_provider": "local",
            "model_name": settings.OLLAMA_MODEL,
            "session_id": str(session_id) if session_id else None
        }

    @classmethod
    async def _execute_cloud_flow(
        cls,
        question: str,
        vector_store_id: Optional[str],
        k: int,
        session_id: Optional[Any],
        start_time: float
    ) -> Dict[str, Any]:
        if not vector_store_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cloud RAG requires a valid vector_store_id."
            )

        cloud_result = await RAGService.answer_question(
            vector_store_id=vector_store_id,
            question=question,
            top_k=k
        )

        elapsed = round(time.time() - start_time, 3)
        raw_sources = cloud_result.get("sources", [])

        sources = []
        citations = []
        for s in raw_sources:
            sources.append({
                "chunk_id": s.get("chunk_id"),
                "score": s.get("score"),
                "preview": s.get("preview")
            })
            citations.append({
                "source_type": "vector_chunk",
                "locator": str(s.get("chunk_id", "unknown")),
                "score": s.get("score", 0.0),
                "text_snippet": s.get("preview", "")
            })

        return {
            "success": cloud_result.get("success", True),
            "answer": cloud_result.get("answer", ""),
            "sources": sources,
            "citations": citations,
            "retrieval_metadata": {
                "provider": "cloud_gemini",
                "model": settings.GEMINI_MODEL,
                "search_k": k,
                "processing_time": elapsed
            },
            "model_provider": "cloud",
            "model_name": settings.GEMINI_MODEL,
            "session_id": str(session_id) if session_id else None
        }
