import os
import fitz  # PyMuPDF
from pathlib import Path
import logging
import traceback
from fastapi import APIRouter, HTTPException, status
from app.core.config import settings
from app.schemas.extract import PDFExtractRequestSchema, PDFExtractResponseSchema

logger = logging.getLogger(__name__)

def exclude_embeddings(data):
    if isinstance(data, dict):
        return {
            k: exclude_embeddings(v) 
            for k, v in data.items() 
            if "embed" not in k.lower()
        }
    elif isinstance(data, list):
        return [exclude_embeddings(item) for item in data]
    return data

def log_http_exception_details(e: Exception, ollama_url: str, model_name: str, payload: dict):
    tb = traceback.format_exc()
    exc_type = type(e).__name__
    exc_msg = getattr(e, "detail", str(e))
    cleaned_payload = exclude_embeddings(payload)
    logger.error(
        f"Local LLM Error Details:\n"
        f"Exception Type: {exc_type}\n"
        f"Exception Message: {exc_msg}\n"
        f"Ollama URL: {ollama_url}\n"
        f"Model Name: {model_name}\n"
        f"Request Payload: {cleaned_payload}\n"
        f"Traceback:\n{tb}"
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

_embedding_model = None

def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer("BAAI/bge-small-en-v1.5")
    return _embedding_model

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
    index_path = vector_store_dir / "faiss.index"
    metadata_path = vector_store_dir / "metadata.json"

    if not index_path.exists() or not metadata_path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The requested PDF document is not indexed. Please build the knowledge base first."
        )

    # Load FAISS index and metadata
    try:
        index = faiss.read_index(str(index_path))
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load vector store or metadata: {str(e)}"
        )

    # 1. Generate embedding for query using BAAI/bge-small-en-v1.5
    try:
        model = get_embedding_model()
        query_vector = model.encode([payload.question], convert_to_numpy=True).astype("float32")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate query embedding: {str(e)}"
        )

    # 2. Search FAISS index (Top K=3)
    k = 3
    try:
        distances, indices = index.search(query_vector, k)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"FAISS search execution failed: {str(e)}"
        )

    # 3. Retrieve chunks and construct prompt context
    sources = []
    context_blocks = []
    
    for rank, idx_val in enumerate(indices[0]):
        if idx_val == -1 or idx_val >= len(metadata):
            continue
        chunk_info = metadata[idx_val]
        dist = float(distances[0][rank])
        
        sources.append({
            "chunk_id": chunk_info["chunk_id"],
            "page": str(chunk_info["page"]),
            "similarity_score": dist
        })
        context_blocks.append(f"Source: {chunk_info['chunk_id']} (Page {chunk_info['page']})\n{chunk_info['text']}")

    rag_context = "\n\n---\n\n".join(context_blocks)

    # 4. Formulate instructions and messages list for Ollama
    system_prompt = (
        "You are a helpful assistant answering questions about a PDF document.\n"
        "Answer the question naturally and accurately based only on the provided context.\n"
        "If the answer cannot be determined from the context, clearly say so."
    )
    
    messages = [{"role": "system", "content": system_prompt}]
    
    # Feed conversation history (keep only the last 1 user and last 2 assistant messages from history,
    # so that combined with the current query, we send exactly 2 user and 2 assistant messages)
    history_messages = []
    user_count = 0
    assistant_count = 0
    for msg in reversed(payload.history or []):
        if msg.role == "user":
            if user_count < 1:
                history_messages.append(msg)
                user_count += 1
        elif msg.role == "assistant":
            if assistant_count < 2:
                history_messages.append(msg)
                assistant_count += 1
    
    history_messages.reverse()
    
    for msg in history_messages:
        role = "user" if msg.role == "user" else "assistant"
        messages.append({"role": role, "content": msg.content})

    # Add final query turn incorporating RAG context
    final_content = (
        f"Context from PDF:\n{rag_context}\n\n"
        f"Question: {payload.question}"
    )
    messages.append({"role": "user", "content": final_content})

    # Calculate prompt statistics
    total_messages = len(messages)
    total_chars = sum(len(msg["content"]) for msg in messages)
    estimated_tokens = int(total_chars / 4)

    logger.info(
        f"Prompt stats for Ollama query:\n"
        f"Total messages sent to Ollama: {total_messages}\n"
        f"Total characters in the prompt: {total_chars}\n"
        f"Estimated token count: {estimated_tokens}"
    )

    # 5. Query Ollama model
    ollama_url = f"{settings.OLLAMA_BASE_URL}/api/chat"
    ollama_payload = {
        "model": settings.OLLAMA_MODEL,
        "messages": messages,
        "stream": False
    }

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(ollama_url, json=ollama_payload)
            if response.status_code != 200:
                logger.error(
                    f"Ollama returned a non-200 response:\n"
                    f"Status Code: {response.status_code}\n"
                    f"Response Body: {response.text}"
                )
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Local LLM service returned status code {response.status_code}. Please verify Ollama is running and has model {settings.OLLAMA_MODEL} loaded."
                )
            
            res_data = response.json()
            logger.info(f"Ollama raw JSON response: {res_data}")
            answer = res_data.get("message", {}).get("content", "").strip()
            
            return {
                "success": True,
                "answer": answer,
                "sources": sources
            }
            
    except HTTPException as e:
        log_http_exception_details(e, ollama_url, settings.OLLAMA_MODEL, ollama_payload)
        raise e
    except httpx.RequestError as e:
        log_http_exception_details(e, ollama_url, settings.OLLAMA_MODEL, ollama_payload)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Local LLM service (Ollama) is unavailable: {str(e)}. Please verify Ollama is running on {settings.OLLAMA_BASE_URL}."
        )



