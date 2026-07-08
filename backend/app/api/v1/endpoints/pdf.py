import os
import fitz  # PyMuPDF
from pathlib import Path
from fastapi import APIRouter, HTTPException, status
from app.core.config import settings
from app.schemas.extract import PDFExtractRequestSchema, PDFExtractResponseSchema

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

