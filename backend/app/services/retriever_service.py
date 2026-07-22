import os
import json
import logging
import faiss
from pathlib import Path
from typing import List, Dict, Any
from fastapi import HTTPException, status
from app.core.config import settings
from app.core.rag import get_embedding_model

logger = logging.getLogger(__name__)

class RetrieverService:
    """
    RetrieverService responsible for loading FAISS vector indexes and metadata,
    embedding user questions using the shared embedding model, and returning
    the Top-K most relevant document chunks.
    """

    @staticmethod
    def resolve_vector_store_dir(vector_store_id: str) -> Path:
        """
        Resolves the vector store directory from vector_store_id safely.
        Prevents directory traversal and checks root vector_store as well as subfolders.
        """
        if not vector_store_id or not vector_store_id.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="vector_store_id cannot be empty."
            )
        
        safe_id = os.path.basename(vector_store_id.strip())
        base_dir = Path(settings.UPLOAD_DIR) / "vector_store"
        
        # Check direct path: uploads/vector_store/<vector_store_id>
        direct_path = base_dir / safe_id
        if direct_path.exists() and direct_path.is_dir():
            return direct_path
        
        # Check potential category subfolders (audio, video, pdfs)
        for subfolder in ["audio", "video", "pdfs"]:
            sub_path = base_dir / subfolder / safe_id
            if sub_path.exists() and sub_path.is_dir():
                return sub_path
                
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested vector store was not found."
        )

    @classmethod
    def retrieve(
        cls,
        vector_store_id: str,
        question: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Retrieves Top-K relevant chunks for a question from the specified vector store.
        """
        if not question or not question.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Question cannot be empty."
            )

        vector_store_dir = cls.resolve_vector_store_dir(vector_store_id)
        index_path = vector_store_dir / "faiss.index"
        metadata_path = vector_store_dir / "metadata.json"

        logger.info(f"[Retrieval] Initiating search in vector store '{vector_store_id}' (Top-{top_k})")

        if not index_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="FAISS index file is missing for the requested vector store."
            )
        if not metadata_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Metadata file is missing for the requested vector store."
            )

        # 1. Load FAISS index & metadata
        try:
            index = faiss.read_index(str(index_path))
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load vector store or metadata for {vector_store_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to load vector store index or metadata."
            )

        if index.ntotal == 0 or not metadata:
            logger.info(f"[Retrieval] Vector store '{vector_store_id}' contains no vectors or metadata")
            return []

        # 2. Embed user question using cached embedding model
        try:
            model = get_embedding_model()
            query_vector = model.encode([question.strip()], convert_to_numpy=True).astype("float32")
        except Exception as e:
            logger.error(f"Failed to generate query embedding: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate embedding for the question."
            )

        # 3. Perform FAISS similarity search
        try:
            search_k = min(top_k, index.ntotal)
            distances, indices = index.search(query_vector, search_k)
        except Exception as e:
            logger.error(f"FAISS search execution failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="FAISS similarity search failed."
            )

        # 4. Format retrieved chunks
        retrieved_chunks = []
        for rank, idx_val in enumerate(indices[0]):
            if idx_val == -1 or idx_val >= len(metadata):
                continue
            chunk_info = metadata[idx_val]
            dist = float(distances[0][rank])
            
            chunk_id = chunk_info.get("chunk_id", rank)
            chunk_text = chunk_info.get("text", "")
            
            extra_meta = {
                k: v for k, v in chunk_info.items() 
                if k not in ("chunk_id", "text")
            }

            retrieved_chunks.append({
                "chunk_id": chunk_id,
                "chunk_text": chunk_text,
                "similarity_score": round(dist, 4),
                "metadata": extra_meta
            })

        logger.info(f"[Retrieval] Successfully retrieved {len(retrieved_chunks)} chunks from vector store '{vector_store_id}'")
        return retrieved_chunks
