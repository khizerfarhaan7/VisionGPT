import os
import fitz  # PyMuPDF
from pathlib import Path
import logging
import traceback
from fastapi import APIRouter, HTTPException, status
from app.core.config import settings
from app.schemas.extract import PDFExtractRequestSchema, PDFExtractResponseSchema

logger = logging.getLogger(__name__)

from app.core.rag import (
    get_embedding_model,
    execute_local_rag,
    exclude_embeddings,
    log_http_exception_details
)

router = APIRouter()

@router.post("/extract", response_model=PDFExtractResponseSchema, status_code=status.HTTP_200_OK)
async def extract_pdf_text(payload: PDFExtractRequestSchema):
    """
    Extract text, page count, word count, and character count from an uploaded PDF document.
    Uses PyMuPDF (fitz) to process page-by-page.
    """
    filename = payload.filename
    safe_filename = os.path.basename(filename)
    pdf_path = Path(settings.UPLOAD_DIR) / "pdfs" / safe_filename
    
    if not pdf_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested PDF document was not found in the uploads workspace."
        )
        
    try:
        doc = fitz.open(str(pdf_path))
        page_count = doc.page_count
        
        extracted_text_list = []
        total_words = 0
        total_chars = 0
        
        for page_num in range(page_count):
            page = doc.load_page(page_num)
            text = page.get_text("text") or ""
            
            # Count characters
            total_chars += len(text)
            
            # Count words
            words = text.split()
            total_words += len(words)
            
            # Keep original text segment
            extracted_text_list.append(text)
            
        doc.close()
        
        # Combine pages keeping structure
        full_extracted_text = "\n\n--- PAGE BREAK ---\n\n".join(extracted_text_list)
        
        return {
            "success": True,
            "page_count": page_count,
            "word_count": total_words,
            "character_count": total_chars,
            "extracted_text": full_extracted_text
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process and extract text from PDF: {str(e)}"
        )

from app.schemas.chunk import PDFChunkRequestSchema, PDFChunkResponseSchema

@router.post("/chunk", response_model=PDFChunkResponseSchema, status_code=status.HTTP_200_OK)
async def chunk_pdf_text(payload: PDFChunkRequestSchema):
    """
    Intelligently slice extracted PDF text into chunks targeting 500-800 words,
    preserving paragraph boundaries and page metadata tracking.
    """
    text = payload.text
    if not text:
        return {
            "success": True,
            "total_chunks": 0,
            "average_chunk_size": 0,
            "chunks": []
        }

    # 1. Split text into pages based on our separator
    page_sections = text.split("\n\n--- PAGE BREAK ---\n\n")
    
    chunks = []
    chunk_index = 0
    
    current_chunk_words = []
    current_chunk_pages = set()
    current_chunk_text_blocks = []

    target_min_words = 500
    target_max_words = 800

    for idx, page_content in enumerate(page_sections):
        page_num = idx + 1
        
        # Split by paragraph boundaries
        paragraphs = page_content.split("\n\n")
        
        for para in paragraphs:
            para_stripped = para.strip()
            if not para_stripped:
                continue
                
            para_words = para_stripped.split()
            para_word_count = len(para_words)
            
            # If adding this para exceeds limit and we have enough words, finalize current chunk
            current_word_count = len(current_chunk_words)
            if current_word_count >= target_min_words and (current_word_count + para_word_count > target_max_words):
                chunk_text = "\n\n".join(current_chunk_text_blocks)
                pages_str = "-".join(map(str, sorted(current_chunk_pages)))
                
                chunks.append({
                    "chunk_id": f"chunk_{chunk_index}",
                    "page": pages_str or str(page_num),
                    "text": chunk_text
                })
                
                chunk_index += 1
                current_chunk_words = []
                current_chunk_pages = set()
                current_chunk_text_blocks = []
                
            # Add block content to active chunk
            current_chunk_words.extend(para_words)
            current_chunk_pages.add(page_num)
            current_chunk_text_blocks.append(para_stripped)

    # Finalize remaining text
    if current_chunk_text_blocks:
        chunk_text = "\n\n".join(current_chunk_text_blocks)
        pages_str = "-".join(map(str, sorted(current_chunk_pages)))
        chunks.append({
            "chunk_id": f"chunk_{chunk_index}",
            "page": pages_str,
            "text": chunk_text
        })

    # Calculate statistics
    total_chunks = len(chunks)
    if total_chunks > 0:
        avg_size = int(sum(len(c["text"]) for c in chunks) / total_chunks)
    else:
        avg_size = 0

    return {
        "success": True,
        "total_chunks": total_chunks,
        "average_chunk_size": avg_size,
        "chunks": chunks
    }

import faiss
import json
import numpy as np
from sentence_transformers import SentenceTransformer
from app.schemas.index import PDFIndexRequestSchema, PDFIndexResponseSchema

# get_embedding_model imported from app.core.rag

@router.post("/index", response_model=PDFIndexResponseSchema, status_code=status.HTTP_200_OK)
async def index_pdf(payload: PDFIndexRequestSchema):
    """
    Generate text embeddings and compile a local FAISS index for the uploaded PDF.
    Saves index and metadata list under uploads/vector_store/<pdf_id>/.
    Skips generation if index already exists for the safe filename.
    """
    filename = payload.filename
    safe_filename = os.path.basename(filename)
    pdf_id = os.path.splitext(safe_filename)[0]
    
    pdf_path = Path(settings.UPLOAD_DIR) / "pdfs" / safe_filename
    if not pdf_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested PDF document was not found."
        )

    # Resolve vector store paths
    vector_store_dir = Path(settings.UPLOAD_DIR) / "vector_store" / pdf_id
    index_path = vector_store_dir / "faiss.index"
    metadata_path = vector_store_dir / "metadata.json"

    model_name = "BAAI/bge-small-en-v1.5"

    # Check if index and metadata already exist
    if index_path.exists() and metadata_path.exists():
        try:
            index = faiss.read_index(str(index_path))
            return {
                "success": True,
                "embedding_model": model_name,
                "vector_dimension": index.d,
                "total_vectors": index.ntotal,
                "index_location": f"uploads/vector_store/{pdf_id}/faiss.index",
                "metadata_location": f"uploads/vector_store/{pdf_id}/metadata.json"
            }
        except Exception:
            # If reading failed for some reason, proceed to regenerate
            pass


@router.post("/index_async", status_code=status.HTTP_202_ACCEPTED)
async def index_pdf_async(payload: PDFIndexRequestSchema):
    """
    Submits PDF text extraction and FAISS vector indexing to the background JobService.
    Returns HTTP 202 with job_id immediately for real-time progress tracking.
    """
    from app.services.job_service import JobService
    from app.services.job_worker_service import JobWorkerService

    filename = payload.filename
    safe_filename = os.path.basename(filename)
    pdf_id = os.path.splitext(safe_filename)[0]
    pdf_path = Path(settings.UPLOAD_DIR) / "pdfs" / safe_filename

    if not pdf_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested PDF document was not found."
        )

    job = JobService.create_job(
        job_type="pdf_indexing",
        document_id=pdf_id,
        metadata={"filename": safe_filename}
    )

    JobService.submit_job_task(
        job["job_id"],
        JobWorkerService.run_pdf_indexing_task,
        filename=safe_filename
    )

    return {
        "job_id": job["job_id"],
        "status": "queued",
        "message": f"PDF indexing task for '{safe_filename}' submitted in background.",
        "progress_url": f"/api/v1/jobs/{job['job_id']}"
    }

    # Re-extract and chunk text to generate index
    try:
        doc = fitz.open(str(pdf_path))
        page_count = doc.page_count
        
        extracted_text_list = []
        for page_num in range(page_count):
            page = doc.load_page(page_num)
            text = page.get_text("text") or ""
            extracted_text_list.append(text)
        doc.close()
        
        # Build chunks
        chunks = []
        chunk_index = 0
        current_chunk_words = []
        current_chunk_pages = set()
        current_chunk_text_blocks = []
        target_min_words = 500
        target_max_words = 800

        for idx, page_content in enumerate(extracted_text_list):
            page_num = idx + 1
            paragraphs = page_content.split("\n\n")
            
            for para in paragraphs:
                para_stripped = para.strip()
                if not para_stripped:
                    continue
                para_words = para_stripped.split()
                para_word_count = len(para_words)
                
                current_word_count = len(current_chunk_words)
                if current_word_count >= target_min_words and (current_word_count + para_word_count > target_max_words):
                    chunk_text = "\n\n".join(current_chunk_text_blocks)
                    pages_str = "-".join(map(str, sorted(current_chunk_pages)))
                    
                    chunks.append({
                        "chunk_id": f"chunk_{chunk_index}",
                        "page": pages_str or str(page_num),
                        "text": chunk_text
                    })
                    
                    chunk_index += 1
                    current_chunk_words = []
                    current_chunk_pages = set()
                    current_chunk_text_blocks = []
                    
                current_chunk_words.extend(para_words)
                current_chunk_pages.add(page_num)
                current_chunk_text_blocks.append(para_stripped)

        if current_chunk_text_blocks:
            chunk_text = "\n\n".join(current_chunk_text_blocks)
            pages_str = "-".join(map(str, sorted(current_chunk_pages)))
            chunks.append({
                "chunk_id": f"chunk_{chunk_index}",
                "page": pages_str,
                "text": chunk_text
            })

        if not chunks:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="PDF contains no valid text blocks to index."
            )

        # Generate embeddings using BAAI/bge-small-en-v1.5
        model = get_embedding_model()
        sentences = [c["text"] for c in chunks]
        embeddings = model.encode(sentences, convert_to_numpy=True)
        
        dimension = int(embeddings.shape[1])
        total_vectors = int(embeddings.shape[0])

        # Compile FAISS Index
        index = faiss.IndexFlatL2(dimension)
        index.add(embeddings.astype("float32"))

        # Save to vector store folder
        vector_store_dir.mkdir(parents=True, exist_ok=True)
        faiss.write_index(index, str(index_path))

        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(chunks, f, ensure_ascii=False, indent=2)

        try:
            from app.services.workspace_service import WorkspaceService
            from app.core.database import SessionLocal
            async with SessionLocal() as db:
                await WorkspaceService.persist_vector_store(
                    db=db,
                    index_path=f"uploads/vector_store/{pdf_id}/faiss.index",
                    embedding_model=model_name,
                    chunk_count=len(chunks)
                )
        except Exception:
            pass

        return {
            "success": True,
            "embedding_model": model_name,
            "vector_dimension": dimension,
            "total_vectors": total_vectors,
            "index_location": f"uploads/vector_store/{pdf_id}/faiss.index",
            "metadata_location": f"uploads/vector_store/{pdf_id}/metadata.json"
        }

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate embeddings and build FAISS index: {str(e)}"
        )

import httpx
from app.schemas.chat import PDFChatRequestSchema, PDFChatResponseSchema

@router.post("/chat", response_model=PDFChatResponseSchema, status_code=status.HTTP_200_OK)
async def chat_pdf(payload: PDFChatRequestSchema):
    """
    Perform local RAG chat over the PDF knowledge base using FAISS vector retrieval and local Ollama model.
    """
    safe_filename = os.path.basename(payload.filename)
    pdf_id = os.path.splitext(safe_filename)[0]
    
    # Check if index and metadata exist
    vector_store_dir = Path(settings.UPLOAD_DIR) / "vector_store" / pdf_id

    system_prompt = (
        "You are a highly precise AI assistant answering questions based solely on the provided contents of a PDF document.\n"
        "Follow these strict directives:\n"
        "1. Base your answer ONLY on the provided context blocks. Do not assume, extrapolate, or invent facts. Never hallucinate.\n"
        "2. If the answer cannot be determined from the context, state clearly and concisely that the information is not present in the document.\n"
        "3. Keep your answers concise yet complete. Prefer structure and bullet lists when summarizing or listing items.\n"
        "4. Do not reference internal components, vector indexes, FAISS, embeddings, or technical systems in your answers."
    )
    
    from app.services.rag_orchestrator import RagOrchestrator

    return await RagOrchestrator.query(
        question=payload.question,
        vector_store_dir=vector_store_dir,
        history=payload.history,
        system_prompt=system_prompt,
        k=3,
        mode="local"
    )



