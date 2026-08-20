import logging
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from sqlalchemy import select

from app.core.config import settings
from app.services.rag_orchestrator import RagOrchestrator

logger = logging.getLogger(__name__)


class WorkspaceIntelligenceService:
    """
    Multimodal Workspace Intelligence Service for VisionGPT.
    Understands an entire workspace/session as one connected knowledge context across
    heterogeneous documents (PDF, Audio, Video, Image), supports cross-document and
    cross-modality reasoning, workspace summaries, and document-aware filtering.
    """

    @classmethod
    async def get_workspace_summary(
        cls,
        session_id: Union[str, uuid.UUID]
    ) -> Dict[str, Any]:
        """
        Analyzes a workspace session's persisted documents, modality distribution,
        indexed vector stores, and conversation count.
        """
        sid_str = str(session_id)
        valid_sid = None
        try:
            valid_sid = uuid.UUID(sid_str)
        except ValueError:
            valid_sid = None

        documents_summary: List[Dict[str, Any]] = []
        modality_distribution: Dict[str, int] = {}
        available_evidence_types: List[str] = []
        message_count = 0

        # Try fetching from DB if database is available
        if valid_sid:
            try:
                from app.core.database import SessionLocal
                from app.models import Document, ChatMessage

                async with SessionLocal() as db:
                    # 1. Fetch documents
                    doc_stmt = select(Document).where(Document.session_id == valid_sid)
                    doc_res = await db.execute(doc_stmt)
                    docs = list(doc_res.scalars().all())

                    for d in docs:
                        m_type = d.media_type.lower()
                        modality_distribution[m_type] = modality_distribution.get(m_type, 0) + 1
                        if m_type not in available_evidence_types:
                            available_evidence_types.append(m_type)

                        # Check index existence on disk
                        p_dir = Path(settings.UPLOAD_DIR) / "vector_store" / str(d.id)
                        is_indexed = (p_dir / "faiss.index").exists()

                        documents_summary.append({
                            "document_id": str(d.id),
                            "filename": d.filename,
                            "media_type": d.media_type,
                            "status": d.status,
                            "is_indexed": is_indexed,
                            "created_at": d.created_at.isoformat() if d.created_at else None
                        })

                    # 2. Fetch chat message count
                    msg_stmt = select(ChatMessage).where(ChatMessage.session_id == valid_sid)
                    msg_res = await db.execute(msg_stmt)
                    msgs = list(msg_res.scalars().all())
                    message_count = len(msgs)

            except Exception as db_err:
                logger.warning(f"WorkspaceIntelligence: DB query failed for summary, falling back to disk: {db_err}")

        # Disk scan fallback if no DB docs found
        if not documents_summary:
            cls._scan_disk_workspace(
                documents_summary=documents_summary,
                modality_distribution=modality_distribution,
                available_evidence_types=available_evidence_types
            )

        return {
            "session_id": sid_str,
            "total_documents": len(documents_summary),
            "modality_distribution": modality_distribution,
            "documents": documents_summary,
            "available_evidence_types": available_evidence_types,
            "message_count": message_count
        }

    @classmethod
    async def query_workspace(
        cls,
        session_id: Union[str, uuid.UUID],
        question: str,
        document_ids: Optional[List[str]] = None,
        media_types: Optional[List[str]] = None,
        mode: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes cross-document and cross-modality reasoning across a workspace session.
        Applies optional document_ids and media_types filters, retrieves evidence via
        MultimodalRetrieverService, generates grounded answer, and attaches workspace summary.
        """
        sid_str = str(session_id)

        # Build source filters list if document_ids or media_types specified
        source_filters: Optional[List[str]] = None
        if document_ids or media_types:
            source_filters = []
            if document_ids:
                source_filters.extend(document_ids)
            if media_types:
                source_filters.extend([m.lower() for m in media_types])

        # 1. Fetch workspace summary
        summary = await cls.get_workspace_summary(session_id=sid_str)

        # 2. Execute multimodal grounded query pipeline via RagOrchestrator
        grounded_res = await RagOrchestrator.answer_multimodal_query(
            question=question,
            session_id=sid_str,
            source_filters=source_filters,
            mode=mode
        )

        # 3. Combine into unified workspace intelligence contract
        return {
            "session_id": sid_str,
            "workspace_summary": summary,
            "answer": grounded_res.get("answer", ""),
            "citations": grounded_res.get("citations", []),
            "evidence_count": grounded_res.get("evidence_count", 0),
            "sources_used": grounded_res.get("sources_used", []),
            "confidence": grounded_res.get("confidence", 0.0),
            "insufficient_evidence": grounded_res.get("insufficient_evidence", False),
            "model_provider": grounded_res.get("model_provider", "local"),
            "model_name": grounded_res.get("model_name", "qwen2.5:3b")
        }

    @classmethod
    def _scan_disk_workspace(
        cls,
        documents_summary: List[Dict[str, Any]],
        modality_distribution: Dict[str, int],
        available_evidence_types: List[str]
    ) -> None:
        """
        Scans uploads directory to construct workspace summary when DB is unavailable or empty.
        """
        vs_root = Path(settings.UPLOAD_DIR) / "vector_store"
        if not vs_root.exists():
            return

        for root, dirs, files in os.walk(vs_root):
            if "faiss.index" in files and "metadata.json" in files:
                p_dir = Path(root)
                folder_name = p_dir.name
                
                # Infer modality
                rel_parts = [part.lower() for part in p_dir.relative_to(vs_root).parts]
                media_type = "pdf"
                if "audio" in rel_parts:
                    media_type = "audio"
                elif "video" in rel_parts:
                    media_type = "video"
                elif "image" in rel_parts:
                    media_type = "image"

                modality_distribution[media_type] = modality_distribution.get(media_type, 0) + 1
                if media_type not in available_evidence_types:
                    available_evidence_types.append(media_type)

                documents_summary.append({
                    "document_id": folder_name,
                    "filename": folder_name,
                    "media_type": media_type,
                    "status": "indexed",
                    "is_indexed": True,
                    "created_at": None
                })
