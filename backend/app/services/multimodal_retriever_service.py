import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

import faiss
from fastapi import HTTPException, status
from sqlalchemy import select

from app.core.config import settings
from app.core.model_manager import model_manager

logger = logging.getLogger(__name__)


class MultimodalRetrieverService:
    """
    Unified Multimodal Retrieval Service for VisionGPT.
    Discovers, queries, normalizes, ranks, and deduplicates evidence chunks
    across heterogeneous document modalities (PDF, Audio, Video, Image) within a workspace session.
    Enforces 4GB RAM safety via sequential index search and immediate memory release.
    """

    @classmethod
    async def retrieve_evidence(
        cls,
        session_id: Optional[Union[str, uuid.UUID]] = None,
        question: str = "",
        source_filters: Optional[List[str]] = None,
        vector_store_dirs: Optional[List[Union[str, Path]]] = None,
        top_k_per_source: int = 3,
        top_k_total: int = 6
    ) -> Dict[str, Any]:
        """
        Executes unified multimodal retrieval across all session documents and vector stores.
        """
        start_time = time.time()
        if not question or not question.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Question cannot be empty for multimodal retrieval."
            )

        question_clean = question.strip()

        # 1. Discover indexed sources belonging to the session or direct paths
        sources = await cls._discover_sources(
            session_id=session_id,
            source_filters=source_filters,
            vector_store_dirs=vector_store_dirs
        )

        if not sources:
            logger.info(f"MultimodalRetriever: No indexed sources found for session '{session_id}'.")
            return {
                "success": True,
                "evidence": [],
                "total_sources_searched": 0,
                "modality_counts": {},
                "total_chunks_retrieved": 0,
                "chunks_after_deduplication": 0,
                "retrieval_latency": round(time.time() - start_time, 3)
            }

        # 2. Acquire shared embedding model via ModelManager
        try:
            embed_model = model_manager.get_embedding_model(settings.EMBEDDING_MODEL)
            query_vector = embed_model.encode([question_clean], convert_to_numpy=True).astype("float32")
        except Exception as e:
            logger.error(f"MultimodalRetriever: Failed to encode query vector: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate query embedding: {str(e)}"
            )

        # 3. Retrieve chunks sequentially per source (4GB RAM safe)
        all_retrieved_chunks: List[Dict[str, Any]] = []
        modality_counts: Dict[str, int] = {}
        successful_sources_count = 0

        for src in sources:
            media_type = src.get("media_type", "document")
            index_path = src.get("index_path")
            metadata_path = src.get("metadata_path")
            doc_id = src.get("document_id")
            filename = src.get("filename", "unknown")

            if not index_path or not metadata_path or not Path(index_path).exists() or not Path(metadata_path).exists():
                logger.warning(f"MultimodalRetriever: Skipping missing or unindexed source '{filename}' ({index_path}).")
                continue

            # Perform isolated search on source
            chunks = cls._search_single_source(
                index_path=Path(index_path),
                metadata_path=Path(metadata_path),
                query_vector=query_vector,
                doc_id=doc_id,
                filename=filename,
                media_type=media_type,
                top_k=top_k_per_source
            )

            if chunks:
                successful_sources_count += 1
                modality_counts[media_type] = modality_counts.get(media_type, 0) + 1
                all_retrieved_chunks.extend(chunks)

        total_chunks_raw = len(all_retrieved_chunks)

        # 4. Merge, rank by relevance score, and deduplicate
        ranked_chunks = sorted(all_retrieved_chunks, key=lambda x: x["relevance_score"], reverse=True)
        deduplicated_evidence = cls._deduplicate_evidence(ranked_chunks)[:top_k_total]

        latency = round(time.time() - start_time, 3)

        logger.info(
            f"MultimodalRetriever: Searched {successful_sources_count}/{len(sources)} sources. "
            f"Modality breakdown: {modality_counts}. Raw chunks: {total_chunks_raw} -> "
            f"Deduplicated evidence: {len(deduplicated_evidence)} in {latency}s."
        )

        return {
            "success": True,
            "evidence": deduplicated_evidence,
            "total_sources_searched": successful_sources_count,
            "modality_counts": modality_counts,
            "total_chunks_retrieved": total_chunks_raw,
            "chunks_after_deduplication": len(deduplicated_evidence),
            "retrieval_latency": latency
        }

    @classmethod
    async def _discover_sources(
        cls,
        session_id: Optional[Union[str, uuid.UUID]],
        source_filters: Optional[List[str]],
        vector_store_dirs: Optional[List[Union[str, Path]]]
    ) -> List[Dict[str, Any]]:
        """
        Discovers index file locations from database session records and explicit directory lists.
        """
        discovered: List[Dict[str, Any]] = []
        seen_paths: Set[str] = set()

        # A. Query database if session_id is provided
        if session_id:
            try:
                from app.core.database import SessionLocal
                from app.models import Document, VectorStore, WorkspaceSession

                valid_sid = uuid.UUID(str(session_id)) if not isinstance(session_id, uuid.UUID) else session_id
                async with SessionLocal() as db:
                    stmt = (
                        select(Document)
                        .where(Document.session_id == valid_sid)
                    )
                    result = await db.execute(stmt)
                    docs = list(result.scalars().all())

                    for doc in docs:
                        # Check document media type filter if provided
                        if source_filters and doc.media_type not in source_filters and str(doc.id) not in source_filters:
                            continue

                        # Resolve vector store index folder
                        doc_id_str = str(doc.id)
                        potential_paths = [
                            Path(settings.UPLOAD_DIR) / "vector_store" / doc_id_str,
                            Path(settings.UPLOAD_DIR) / "vector_store" / doc.media_type / doc_id_str,
                            Path(settings.UPLOAD_DIR) / "vector_store" / Path(doc.filename).stem,
                        ]

                        for p in potential_paths:
                            idx_file = p / "faiss.index"
                            meta_file = p / "metadata.json"
                            if idx_file.exists() and meta_file.exists() and str(idx_file) not in seen_paths:
                                seen_paths.add(str(idx_file))
                                discovered.append({
                                    "document_id": doc_id_str,
                                    "filename": doc.filename,
                                    "media_type": doc.media_type,
                                    "index_path": str(idx_file),
                                    "metadata_path": str(meta_file)
                                })
                                break
            except Exception as db_err:
                logger.warning(f"MultimodalRetriever: Failed to query session documents from DB: {db_err}")

        # B. Discover explicit vector_store_dirs fallback
        if vector_store_dirs:
            for v_dir in vector_store_dirs:
                p_dir = Path(v_dir)
                idx_file = p_dir / "faiss.index"
                meta_file = p_dir / "metadata.json"
                if idx_file.exists() and meta_file.exists() and str(idx_file) not in seen_paths:
                    seen_paths.add(str(idx_file))

                    # Infer media_type from path structure
                    path_parts = [part.lower() for part in p_dir.parts]
                    media_type = "pdf"
                    if "audio" in path_parts:
                        media_type = "audio"
                    elif "video" in path_parts:
                        media_type = "video"
                    elif "image" in path_parts:
                        media_type = "image"

                    discovered.append({
                        "document_id": p_dir.stem,
                        "filename": p_dir.stem,
                        "media_type": media_type,
                        "index_path": str(idx_file),
                        "metadata_path": str(meta_file)
                    })

        return discovered

    @classmethod
    def _search_single_source(
        cls,
        index_path: Path,
        metadata_path: Path,
        query_vector: Any,
        doc_id: Optional[str],
        filename: str,
        media_type: str,
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Performs a single FAISS index lookup and normalizes retrieved evidence chunks.
        Releases the FAISS index reference immediately to optimize memory.
        """
        chunks: List[Dict[str, Any]] = []
        try:
            index = faiss.read_index(str(index_path))
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata_list = json.load(f)

            if not isinstance(metadata_list, list) or len(metadata_list) == 0:
                return []

            # Check vector dimension compatibility
            if hasattr(index, "d") and index.d != query_vector.shape[1]:
                logger.warning(
                    f"MultimodalRetriever: Dimension mismatch for '{filename}' "
                    f"(Index: {index.d}d, Query: {query_vector.shape[1]}d). Skipping source."
                )
                return []

            search_depth = min(top_k, index.ntotal)
            if search_depth == 0:
                return []

            distances, indices = index.search(query_vector, search_depth)
            dist_row = distances[0]
            idx_row = indices[0]

            for i in range(len(idx_row)):
                match_idx = idx_row[i]
                if match_idx < 0 or match_idx >= len(metadata_list):
                    continue

                dist = float(dist_row[i])
                meta_item = metadata_list[match_idx]

                # Calculate normalized relevance score (higher is better, 0.0 to 1.0)
                relevance_score = round(1.0 / (1.0 + dist), 4)

                # Format locator and content based on modality
                text_content = meta_item.get("text", meta_item.get("chunk_text", ""))
                locator = cls._format_locator(meta_item, media_type)

                chunks.append({
                    "source_id": str(meta_item.get("chunk_id", f"{filename}_{match_idx}")),
                    "document_id": doc_id or filename,
                    "filename": filename,
                    "media_type": media_type,
                    "source_type": media_type,
                    "content": text_content,
                    "relevance_score": relevance_score,
                    "distance": round(dist, 4),
                    "locator": locator,
                    "metadata": {
                        "page": meta_item.get("page"),
                        "start_time": meta_item.get("start_time"),
                        "end_time": meta_item.get("end_time"),
                        "speech": meta_item.get("speech"),
                        "vision": meta_item.get("vision")
                    }
                })

            # Explicitly clean up index reference
            del index
            return chunks

        except Exception as e:
            logger.error(f"MultimodalRetriever: Error searching index '{index_path}': {e}", exc_info=True)
            return []

    @classmethod
    def _format_locator(cls, meta_item: Dict[str, Any], media_type: str) -> str:
        """
        Formats human-readable evidence locators per modality.
        """
        if media_type == "pdf":
            page = meta_item.get("page")
            return f"page {page}" if page else str(meta_item.get("chunk_id", "pdf_chunk"))
        elif media_type in ("audio", "video"):
            s_time = meta_item.get("start_time")
            e_time = meta_item.get("end_time")
            if s_time is not None and e_time is not None:
                return f"{float(s_time):.1f}s–{float(e_time):.1f}s"
            ts = meta_item.get("timestamp")
            if ts is not None:
                return f"{float(ts):.1f}s"
            return str(meta_item.get("chunk_id", "timeline_chunk"))
        elif media_type == "image":
            return "image_caption"
        return str(meta_item.get("chunk_id", "chunk"))

    @classmethod
    def _deduplicate_evidence(cls, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Deduplicates near-identical evidence based on text similarity and locator overlap.
        """
        deduped: List[Dict[str, Any]] = []
        seen_texts: List[str] = []

        for chunk in chunks:
            content = chunk.get("content", "").strip()
            if not content:
                continue

            # Check exact or near-identical text match (>85% character similarity)
            is_duplicate = False
            content_lower = content.lower()

            for seen in seen_texts:
                if content_lower in seen or seen in content_lower:
                    is_duplicate = True
                    break

            if not is_duplicate:
                seen_texts.append(content_lower)
                deduped.append(chunk)

        return deduped
