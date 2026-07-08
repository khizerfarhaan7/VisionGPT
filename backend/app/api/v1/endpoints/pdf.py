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
