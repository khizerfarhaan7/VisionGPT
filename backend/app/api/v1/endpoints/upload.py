import os
import uuid
import shutil
import fitz
from pathlib import Path
from fastapi import APIRouter, File, UploadFile, HTTPException, status
from app.core.config import settings
from app.schemas.upload import ImageUploadResponseSchema
from app.schemas.pdf import PDFUploadResponseSchema
from app.schemas.audio import AudioUploadResponseSchema

router = APIRouter()

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB

@router.post("/image", response_model=ImageUploadResponseSchema, status_code=status.HTTP_200_OK)
async def upload_image(file: UploadFile = File(...)):
    """
    Upload an image file to the server.
    Validates file type (png, jpg, jpeg, webp) and file size (max 20MB).
    Saves the image under a unique UUID filename.
    """
    # 1. Validate file extension
    original_filename = file.filename or "unknown"
    file_ext = Path(original_filename).suffix.lower()
    
    # 2. Validate content type
    content_type = file.content_type or ""
    
    # Validate extension and content-type
    is_valid_ext = file_ext in ALLOWED_EXTENSIONS
    is_valid_mime = content_type.lower() in ALLOWED_CONTENT_TYPES or any(
        content_type.lower().startswith(mime) for mime in ["image/png", "image/jpeg", "image/webp"]
    )
    
    if not (is_valid_ext and is_valid_mime):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type. Allowed formats: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
        
    # 3. Validate file size
    file_size = getattr(file, "size", None)
    if file_size is None:
        try:
            # Determine size by seeking end
            file.file.seek(0, 2)
            file_size = file.file.tell()
            file.file.seek(0)  # Reset cursor position
        except Exception:
            file_size = 0
            
    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded image file is empty (0 bytes) and cannot be processed."
        )

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File size exceeds the maximum limit of 20MB."
        )
        
    # 4. Resolve destination path and create directories
    upload_dir = Path(settings.UPLOAD_DIR) / "images"
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # 5. Generate unique UUID filename while preserving extension
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    destination_path = upload_dir / unique_filename
    
    # 6. Save file payload
    try:
        with destination_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception:
        if destination_path.exists():
            destination_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save uploaded image file. Please try again."
        )
        
    # 7. Construct response parameters
    relative_path = f"uploads/images/{unique_filename}"
    
    try:
        from app.services.workspace_service import WorkspaceService
        from app.core.database import SessionLocal
        async with SessionLocal() as db:
            await WorkspaceService.persist_document(
                db=db,
                filename=unique_filename,
                original_source=original_filename,
                media_type="image",
                file_path=relative_path,
                status="uploaded"
            )
    except Exception as db_err:
        pass

    return {
        "success": True,
        "filename": unique_filename,
        "original_name": original_filename,
        "content_type": content_type,
        "size": file_size,
        "path": relative_path
    }

PDF_MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

@router.post("/pdf", response_model=PDFUploadResponseSchema, status_code=status.HTTP_200_OK)
async def upload_pdf(file: UploadFile = File(...)):
    """
    Upload a PDF document to the server.
    Validates format (.pdf) and file size (max 50MB).
    Saves the PDF under uploads/pdfs/ and extracts page count metadata using PyMuPDF.
    """
    # 1. Validate file extension
    original_filename = file.filename or "unknown"
    file_ext = Path(original_filename).suffix.lower()
    
    if file_ext != ".pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Only PDF (.pdf) format is supported."
        )
        
    # 2. Validate file size
    file_size = getattr(file, "size", None)
    if file_size is None:
        try:
            file.file.seek(0, 2)
            file_size = file.file.tell()
            file.file.seek(0)
        except Exception:
            file_size = 0
            
    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded PDF document is empty (0 bytes) and cannot be processed."
        )

    if file_size > PDF_MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File size exceeds the maximum limit of 50MB."
        )
        
    # 3. Resolve destination path and create directories
    upload_dir = Path(settings.UPLOAD_DIR) / "pdfs"
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # 4. Generate unique UUID filename while preserving extension
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    destination_path = upload_dir / unique_filename
    
    # 5. Save file payload
    try:
        with destination_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception:
        if destination_path.exists():
            destination_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save uploaded PDF file. Please try again."
        )
        
    # 6. Extract page count metadata using PyMuPDF (fitz)
    doc = None
    try:
        doc = fitz.open(str(destination_path))
        page_count = doc.page_count
        doc.close()
    except Exception:
        if doc is not None:
            try:
                doc.close()
            except Exception:
                pass
        doc = None
        import gc
        gc.collect()
        if destination_path.exists():
            try:
                destination_path.unlink()
            except Exception:
                pass
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded PDF file is invalid or corrupted. Please choose a valid PDF file."
        )
        
    # 7. Construct response parameters
    relative_path = f"uploads/pdfs/{unique_filename}"
    
    try:
        from app.services.workspace_service import WorkspaceService
        from app.core.database import SessionLocal
        async with SessionLocal() as db:
            await WorkspaceService.persist_document(
                db=db,
                filename=unique_filename,
                original_source=original_filename,
                media_type="pdf",
                file_path=relative_path,
                status="uploaded"
            )
    except Exception:
        pass

    return {
        "success": True,
        "filename": unique_filename,
        "original_name": original_filename,
        "page_count": page_count,
        "size": file_size,
        "path": relative_path
    }

AUDIO_MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".mp4", ".mov", ".avi", ".mkv", ".webm"}

@router.post("/audio", response_model=AudioUploadResponseSchema, status_code=status.HTTP_200_OK)
async def upload_audio(file: UploadFile = File(...)):
    """
    Upload an audio file to the server.
    Validates format (.mp3, .wav, .m4a, etc.) and file size (max 50MB).
    Saves the audio file under uploads/audio/ using unique UUID name.
    """
    # 1. Validate file extension
    original_filename = file.filename or "unknown"
    file_ext = Path(original_filename).suffix.lower()
    
    if file_ext not in ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type. Supported formats: {', '.join(sorted(ALLOWED_AUDIO_EXTENSIONS))}"
        )
        
    # 2. Validate file size
    file_size = getattr(file, "size", None)
    if file_size is None:
        try:
            file.file.seek(0, 2)
            file_size = file.file.tell()
            file.file.seek(0)
        except Exception:
            file_size = 0
            
    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded audio file is empty (0 bytes) and cannot be processed."
        )

    if file_size > AUDIO_MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File size exceeds the maximum limit of 50MB."
        )
        
    # 3. Resolve destination path and create directories
    upload_dir = Path(settings.UPLOAD_DIR) / "audio"
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # 4. Generate unique UUID filename while preserving extension
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    destination_path = upload_dir / unique_filename
    
    # 5. Save file payload
    try:
        with destination_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception:
        if destination_path.exists():
            destination_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save uploaded audio file. Please try again."
        )
        
    # 6. Construct response parameters
    relative_path = f"uploads/audio/{unique_filename}"
    
    try:
        from app.services.workspace_service import WorkspaceService
        from app.core.database import SessionLocal
        async with SessionLocal() as db:
            await WorkspaceService.persist_document(
                db=db,
                filename=unique_filename,
                original_source=original_filename,
                media_type="audio",
                file_path=relative_path,
                status="uploaded"
            )
    except Exception:
        pass

    return {
        "success": True,
        "filename": unique_filename,
        "original_name": original_filename,
        "size": file_size,
        "path": relative_path
    }


