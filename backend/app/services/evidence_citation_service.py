import logging
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SourceReference

logger = logging.getLogger(__name__)


class EvidenceCitationService:
    """
    Evidence & Citation Engine for VisionGPT.
    Converts retrieved multimodal evidence into structured, verifiable citations,
    formats locators (PDF page, Audio/Video timestamps MM:SS, Image captions),
    prevents duplicate citations, and persists source citations via SourceReference model.
    """

    @classmethod
    def build_citations(
        cls,
        evidence_chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Converts evidence chunks into structured, verified citations.
        Deduplicates near-identical locators and filters unretrieved references.
        """
        citations: List[Dict[str, Any]] = []
        seen_locators: set = set()

        for idx, chunk in enumerate(evidence_chunks, 1):
            doc_id = str(chunk.get("document_id", "unknown_doc"))
            filename = chunk.get("filename", "unknown_file")
            media_type = chunk.get("media_type", chunk.get("source_type", "document"))
            locator = cls.format_locator(chunk, media_type)

            dedup_key = f"{doc_id}:{locator}"
            if dedup_key in seen_locators:
                continue
            seen_locators.add(dedup_key)

            citation_id = f"cite_{idx}"
            supporting_text = chunk.get("content", "").strip()
            if len(supporting_text) > 200:
                supporting_text = supporting_text[:200] + "..."

            citations.append({
                "citation_id": citation_id,
                "document_id": doc_id,
                "filename": filename,
                "source_type": media_type,
                "locator": locator,
                "relevance_score": chunk.get("relevance_score", 0.0),
                "supporting_content": supporting_text,
                "metadata": chunk.get("metadata", {})
            })

        return citations

    @classmethod
    def format_locator(cls, chunk: Dict[str, Any], media_type: str) -> str:
        """
        Formats precise, human-readable locators:
        - PDF -> page X
        - Audio/Video -> MM:SS–MM:SS (XX.Xs–YY.Ys)
        - Image -> image_caption
        - Web -> URL
        Fallback -> location unknown
        """
        meta = chunk.get("metadata", {})
        existing_locator = chunk.get("locator")

        if media_type == "pdf":
            page = meta.get("page")
            if page is not None:
                return f"page {page}"
            if existing_locator and "page" in str(existing_locator).lower():
                return str(existing_locator)
            return "page unknown"

        elif media_type in ("audio", "video"):
            start_t = meta.get("start_time")
            end_t = meta.get("end_time")
            if start_t is not None and end_t is not None:
                return cls._format_timestamp_range(float(start_t), float(end_t))
            ts = meta.get("timestamp")
            if ts is not None:
                return cls._format_timestamp(float(ts))
            if existing_locator:
                return str(existing_locator)
            return "timestamp unknown"

        elif media_type == "image":
            if existing_locator:
                return str(existing_locator)
            return "image_caption"

        elif media_type == "web":
            url = meta.get("url") or chunk.get("original_source")
            if url:
                return str(url)
            return "web_url"

        return str(existing_locator) if existing_locator else "location unknown"

    @classmethod
    def _format_timestamp(cls, seconds: float) -> str:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins:02d}:{secs:02d} ({seconds:.1f}s)"

    @classmethod
    def _format_timestamp_range(cls, start_sec: float, end_sec: float) -> str:
        s_min, s_sec = int(start_sec // 60), int(start_sec % 60)
        e_min, e_sec = int(end_sec // 60), int(end_sec % 60)
        return f"{s_min:02d}:{s_sec:02d}–{e_min:02d}:{e_sec:02d} ({start_sec:.1f}s–{end_sec:.1f}s)"

    @classmethod
    async def persist_citations(
        cls,
        db: AsyncSession,
        message_id: uuid.UUID,
        citations: List[Dict[str, Any]]
    ) -> List[SourceReference]:
        """
        Persists structured citations into PostgreSQL via SourceReference model.
        """
        records: List[SourceReference] = []
        try:
            for cite in citations:
                doc_id_raw = cite.get("document_id")
                valid_doc_id = None
                if doc_id_raw:
                    try:
                        valid_doc_id = uuid.UUID(str(doc_id_raw))
                    except ValueError:
                        valid_doc_id = None

                ref = SourceReference(
                    message_id=message_id,
                    document_id=valid_doc_id,
                    source_type=cite.get("source_type", "document"),
                    locator=cite.get("locator", "location unknown"),
                    metadata_json={
                        "citation_id": cite.get("citation_id"),
                        "filename": cite.get("filename"),
                        "relevance_score": cite.get("relevance_score"),
                        "supporting_content": cite.get("supporting_content"),
                        "metadata": cite.get("metadata", {})
                    }
                )
                db.add(ref)
                records.append(ref)

            await db.commit()
            logger.info(f"EvidenceCitationService: Persisted {len(records)} citation records for message '{message_id}'.")
            return records
        except Exception as e:
            logger.error(f"EvidenceCitationService: Failed to persist citations: {e}", exc_info=True)
            await db.rollback()
            return []
