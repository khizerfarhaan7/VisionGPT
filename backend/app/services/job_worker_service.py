import os
import time
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.config import settings
from app.services.job_service import JobService

logger = logging.getLogger(__name__)


class JobWorkerService:
    """
    Background Task Execution Worker for PDF indexing, Audio transcription, and Video timeline processing.
    Updates job progress at stages: 0 (queued), 10 (started), 25 (extraction), 50 (model/indexing),
    75 (persistence/finalization), 100 (completed).
    Respects JobService cancellation flags and enforces 4GB RAM concurrency limits via JobService semaphore locks.
    """

    @classmethod
    async def run_pdf_indexing_task(
        cls,
        job_id: str,
        filename: str,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Background worker task for PDF text extraction and FAISS vector indexing.
        """
        safe_filename = os.path.basename(filename)
        pdf_id = os.path.splitext(safe_filename)[0]
        pdf_path = Path(settings.UPLOAD_DIR) / "pdfs" / safe_filename

        await JobService.update_job_progress(job_id, 10, status="running", metadata={"stage": "started", "file": safe_filename})
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file '{safe_filename}' not found in uploads directory.")

        # Stage 25: Extract text using PyMuPDF
        job_state = await JobService.get_job(job_id)
        if job_state and job_state.get("cancel_requested"):
            await JobService.update_job_progress(job_id, 25, status="cancelled")
            return {"status": "cancelled"}

        await JobService.update_job_progress(job_id, 25, status="running", metadata={"stage": "text_extraction"})
        import fitz
        doc = fitz.open(str(pdf_path))
        page_count = doc.page_count
        extracted_text_list = []
        for page_num in range(page_count):
            page = doc.load_page(page_num)
            text = page.get_text("text") or ""
            extracted_text_list.append(text)
        doc.close()

        # Stage 50: Chunk & Generate FAISS Embeddings
        job_state = await JobService.get_job(job_id)
        if job_state and job_state.get("cancel_requested"):
            await JobService.update_job_progress(job_id, 50, status="cancelled")
            return {"status": "cancelled"}

        await JobService.update_job_progress(job_id, 50, status="running", metadata={"stage": "faiss_embedding"})
        import faiss
        import json
        from app.core.rag import get_embedding_model

        chunks = []
        target_min_words = 500
        target_max_words = 800
        current_words = []
        current_pages = set()

        for idx, page_content in enumerate(extracted_text_list):
            page_num = idx + 1
            paragraphs = page_content.split("\n\n")
            for para in paragraphs:
                para_stripped = para.strip()
                if not para_stripped:
                    continue
                words = para_stripped.split()
                if len(current_words) >= target_min_words and (len(current_words) + len(words) > target_max_words):
                    chunk_text = " ".join(current_words)
                    chunks.append({
                        "chunk_id": f"chunk_{len(chunks)}",
                        "page": min(current_pages) if current_pages else 1,
                        "text": chunk_text
                    })
                    current_words = []
                    current_pages = set()

                current_words.extend(words)
                current_pages.add(page_num)

        if current_words:
            chunks.append({
                "chunk_id": f"chunk_{len(chunks)}",
                "page": min(current_pages) if current_pages else 1,
                "text": " ".join(current_words)
            })

        embed_model = get_embedding_model()
        texts_to_embed = [c["text"] for c in chunks] if chunks else ["empty"]
        embeddings = embed_model.encode(texts_to_embed, convert_to_numpy=True).astype("float32")

        dim = embeddings.shape[1]
        index = faiss.IndexFlatL2(dim)
        index.add(embeddings)

        # Stage 75: Save Vector Store & Database Metadata
        job_state = await JobService.get_job(job_id)
        if job_state and job_state.get("cancel_requested"):
            await JobService.update_job_progress(job_id, 75, status="cancelled")
            return {"status": "cancelled"}

        await JobService.update_job_progress(job_id, 75, status="running", metadata={"stage": "persistence"})
        vector_store_dir = Path(settings.UPLOAD_DIR) / "vector_store" / pdf_id
        vector_store_dir.mkdir(parents=True, exist_ok=True)

        faiss.write_index(index, str(vector_store_dir / "faiss.index"))
        with open(vector_store_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(chunks, f, indent=2)

        del index

        result_meta = {
            "document_id": pdf_id,
            "session_id": session_id,
            "modality": "pdf",
            "total_vectors": len(chunks),
            "index_location": f"uploads/vector_store/{pdf_id}/faiss.index",
            "metadata_location": f"uploads/vector_store/{pdf_id}/metadata.json"
        }

        return result_meta

    @classmethod
    async def run_audio_transcription_task(
        cls,
        job_id: str,
        filename: str,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Background worker task for Whisper audio transcription and FAISS vector indexing.
        """
        safe_filename = os.path.basename(filename)
        audio_id = os.path.splitext(safe_filename)[0]
        audio_path = Path(settings.UPLOAD_DIR) / "audio" / safe_filename

        await JobService.update_job_progress(job_id, 10, status="running", metadata={"stage": "started", "file": safe_filename})
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file '{safe_filename}' not found in uploads directory.")

        # Stage 25: Speech-to-Text Transcription via Faster-Whisper
        job_state = await JobService.get_job(job_id)
        if job_state and job_state.get("cancel_requested"):
            await JobService.update_job_progress(job_id, 25, status="cancelled")
            return {"status": "cancelled"}

        await JobService.update_job_progress(job_id, 25, status="running", metadata={"stage": "whisper_transcription"})
        from app.api.v1.endpoints.audio import get_whisper_model, chunk_whisper_segments
        whisper_model = get_whisper_model()
        segments, info = whisper_model.transcribe(str(audio_path), language="en", task="transcribe")
        segments_list = list(segments)

        # Stage 50: Chunking & FAISS Vector Indexing
        job_state = await JobService.get_job(job_id)
        if job_state and job_state.get("cancel_requested"):
            await JobService.update_job_progress(job_id, 50, status="cancelled")
            return {"status": "cancelled"}

        await JobService.update_job_progress(job_id, 50, status="running", metadata={"stage": "vector_indexing"})
        import faiss
        import json
        from app.core.rag import get_embedding_model

        metadata_chunks = chunk_whisper_segments(segments_list, target_min_words=120, target_max_words=180)
        embed_model = get_embedding_model()
        texts_to_embed = [c["text"] for c in metadata_chunks] if metadata_chunks else ["empty"]
        embeddings = embed_model.encode(texts_to_embed, convert_to_numpy=True).astype("float32")

        dim = embeddings.shape[1]
        index = faiss.IndexFlatL2(dim)
        index.add(embeddings)

        # Stage 75: Persistence
        job_state = await JobService.get_job(job_id)
        if job_state and job_state.get("cancel_requested"):
            await JobService.update_job_progress(job_id, 75, status="cancelled")
            return {"status": "cancelled"}

        await JobService.update_job_progress(job_id, 75, status="running", metadata={"stage": "persistence"})
        vector_store_dir = Path(settings.UPLOAD_DIR) / "vector_store" / "audio" / audio_id
        vector_store_dir.mkdir(parents=True, exist_ok=True)

        faiss.write_index(index, str(vector_store_dir / "faiss.index"))
        with open(vector_store_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata_chunks, f, indent=2)

        del index

        full_transcript = " ".join([s.text for s in segments_list]).strip()
        result_meta = {
            "document_id": audio_id,
            "session_id": session_id,
            "modality": "audio",
            "duration": round(info.duration, 2),
            "word_count": len(full_transcript.split()),
            "total_vectors": len(metadata_chunks),
            "index_location": f"uploads/vector_store/audio/{audio_id}/faiss.index"
        }

        return result_meta

    @classmethod
    async def run_video_indexing_task(
        cls,
        job_id: str,
        filename: str,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Background worker task for Video frame extraction, visual captioning, speech STT, and timeline indexing.
        """
        safe_filename = os.path.basename(filename)
        video_id = os.path.splitext(safe_filename)[0]
        video_path = Path(settings.UPLOAD_DIR) / "audio" / safe_filename

        await JobService.update_job_progress(job_id, 10, status="running", metadata={"stage": "started", "file": safe_filename})
        if not video_path.exists():
            raise FileNotFoundError(f"Video file '{safe_filename}' not found in uploads directory.")

        # Stage 25: Frame sampling & Speech STT
        job_state = await JobService.get_job(job_id)
        if job_state and job_state.get("cancel_requested"):
            await JobService.update_job_progress(job_id, 25, status="cancelled")
            return {"status": "cancelled"}

        await JobService.update_job_progress(job_id, 25, status="running", metadata={"stage": "multimodal_processing"})
        from app.core.video import index_video_multimodal

        res = index_video_multimodal(
            video_path=video_path,
            interval_seconds=settings.VIDEO_INTERVAL_SECONDS,
            window_size=settings.VIDEO_WINDOW_SIZE
        )

        await JobService.update_job_progress(job_id, 75, status="running", metadata={"stage": "persistence"})
        result_meta = {
            "document_id": video_id,
            "session_id": session_id,
            "modality": "video",
            "frames_processed": res.get("total_frames_processed", 0),
            "chunks_indexed": res.get("total_chunks_indexed", 0),
            "index_location": f"uploads/vector_store/video/{video_id}/faiss.index"
        }

        return result_meta
