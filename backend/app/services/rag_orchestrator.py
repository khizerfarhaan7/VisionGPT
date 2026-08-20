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

        # Query classification via QueryRouterService
        from app.services.query_router_service import QueryRouterService
        routing_info = QueryRouterService.classify_query(
            question=question,
            session_id=session_id,
            vector_store_dir=vector_store_dir,
            vector_store_id=vector_store_id
        )

        logger.info(
            f"RagOrchestrator: Query classified as '{routing_info['query_type']}' "
            f"(Pipeline='{routing_info['selected_pipeline']}', Mode='{requested_mode}' -> Resolved='{resolved_provider}')"
        )

        # Record RAG query metrics
        from app.services.metrics_service import MetricsService
        duration_ms = round((time.time() - start_time) * 1000, 2)
        MetricsService.record_rag_query(
            provider=resolved_provider,
            query_type=routing_info.get("query_type", "single_source"),
            duration_ms=duration_ms
        )

        # Dispatch based on router classification if session_id is provided and query is workspace/comparison
        if session_id and routing_info["query_type"] in ("workspace", "comparison"):
            from app.services.workspace_intelligence_service import WorkspaceIntelligenceService
            res = await WorkspaceIntelligenceService.query_workspace(
                session_id=session_id,
                question=question,
                mode=resolved_provider
            )
            res["routing_metadata"] = routing_info
            return res

        if resolved_provider == "local":
            res = await cls._execute_local_flow(
                question=question,
                vector_store_dir=vector_store_dir,
                history=history or [],
                system_prompt=system_prompt,
                k=k,
                session_id=session_id,
                start_time=start_time
            )
        else:
            res = await cls._execute_cloud_flow(
                question=question,
                vector_store_id=vector_store_id,
                k=k,
                session_id=session_id,
                start_time=start_time
            )

        res["routing_metadata"] = routing_info
        return res

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

        # Build structured, verifiable citations via EvidenceCitationService
        from app.services.evidence_citation_service import EvidenceCitationService
        citations = EvidenceCitationService.build_citations(sources)

        sources_used = [
            {
                "document_id": c.get("document_id"),
                "filename": c.get("filename"),
                "source_type": c.get("source_type")
            }
            for c in citations
        ]

        return {
            "success": local_result.get("success", True),
            "answer": local_result.get("answer", ""),
            "citations": citations,
            "evidence_count": len(citations),
            "sources_used": sources_used,
            "sources": sources,
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

        from app.services.evidence_citation_service import EvidenceCitationService
        citations = EvidenceCitationService.build_citations([
            {
                "document_id": vector_store_id,
                "filename": f"vector_store_{vector_store_id}",
                "source_type": "vector_chunk",
                "locator": str(s.get("chunk_id", "chunk")),
                "content": s.get("preview", ""),
                "relevance_score": s.get("score", 0.0)
            }
            for s in raw_sources
        ])

        sources_used = [
            {
                "document_id": vector_store_id,
                "filename": f"vector_store_{vector_store_id}",
                "source_type": "vector_chunk"
            }
        ] if raw_sources else []

        return {
            "success": cloud_result.get("success", True),
            "answer": cloud_result.get("answer", ""),
            "citations": citations,
            "evidence_count": len(citations),
            "sources_used": sources_used,
            "sources": raw_sources,
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

    @classmethod
    async def retrieve_multimodal_evidence(
        cls,
        question: str,
        session_id: Optional[Union[str, Any]] = None,
        source_filters: Optional[List[str]] = None,
        vector_store_dirs: Optional[List[Union[str, Path]]] = None,
        top_k_per_source: int = 3,
        top_k_total: int = 6
    ) -> Dict[str, Any]:
        """
        Multimodal RAG Evidence Retrieval entry point.
        Discovers session sources, queries vector stores sequentially, normalizes,
        ranks, and deduplicates evidence chunks across PDF, Audio, Video, and Image modalities.
        """
        from app.services.multimodal_retriever_service import MultimodalRetrieverService

        return await MultimodalRetrieverService.retrieve_evidence(
            session_id=session_id,
            question=question,
            source_filters=source_filters,
            vector_store_dirs=vector_store_dirs,
            top_k_per_source=top_k_per_source,
            top_k_total=top_k_total
        )

    @classmethod
    async def answer_multimodal_query(
        cls,
        question: str,
        session_id: Optional[Union[str, Any]] = None,
        source_filters: Optional[List[str]] = None,
        vector_store_dirs: Optional[List[Union[str, Path]]] = None,
        mode: Optional[str] = None,
        history: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Full Multimodal RAG Grounded Answer pipeline.
        Retrieves evidence across session modalities, builds verifiable citations,
        generates grounded answer with confidence scoring, and enforces privacy rules.
        """
        from app.services.evidence_citation_service import EvidenceCitationService
        from app.services.grounded_answer_service import GroundedAnswerService

        requested_mode = (mode or getattr(settings, "RAG_PROVIDER", "local")).lower().strip()
        resolved_provider = cls._resolve_provider(
            mode=requested_mode,
            vector_store_dir=vector_store_dirs[0] if vector_store_dirs else None,
            vector_store_id=str(session_id) if session_id else None
        )

        retrieval_res = await cls.retrieve_multimodal_evidence(
            question=question,
            session_id=session_id,
            source_filters=source_filters,
            vector_store_dirs=vector_store_dirs
        )

        evidence = retrieval_res.get("evidence", [])
        citations = EvidenceCitationService.build_citations(evidence)

        return await GroundedAnswerService.generate_grounded_answer(
            question=question,
            evidence=evidence,
            citations=citations,
            mode=resolved_provider,
            session_id=session_id,
            history=history
        )
