import os
import uuid
import logging
from pathlib import Path
from urllib.parse import urlparse
import asyncio
import httpx
import fitz  # PyMuPDF
import yt_dlp
from fastapi import HTTPException, status
from app.core.config import settings
from app.schemas.import_schema import ImportAnalyzeResponseSchema, ContentTypeLiteral
from app.schemas.index import PDFIndexRequestSchema
from app.api.v1.endpoints.pdf import index_pdf

logger = logging.getLogger(__name__)

MAX_PDF_DOWNLOAD_SIZE = 50 * 1024 * 1024  # 50 MB
DOWNLOAD_TIMEOUT = 30.0  # 30 seconds timeout

def is_valid_youtube_url(url: str) -> bool:
    """
    Validate that the provided URL belongs to YouTube.
    """
    try:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        if not any(domain in hostname for domain in ["youtube.com", "youtu.be"]):
            return False
        if "youtu.be" in hostname and len(parsed.path.strip("/")) > 0:
            return True
        if "youtube.com" in hostname and any(p in parsed.path for p in ["/watch", "/shorts", "/v/", "/embed"]):
            return True
        return False
    except Exception:
        return False

class ImportService:
    """
    Import pipeline service architecture.
    Handles content routing to dedicated processors for PDF, YouTube, and Audio resources.
    """

    @staticmethod
    async def route_to_pdf(url: str) -> ImportAnalyzeResponseSchema:
        """
        PDF import pipeline:
        1. Downloads PDF file from URL.
        2. Validates HTTP Content-Type header (application/pdf).
        3. Validates PDF binary file signature (%PDF-).
        4. Validates document structure via PyMuPDF.
        5. Invokes existing PDF extraction, chunking, and FAISS indexing pipeline.
        6. Cleans up temporary files on any download or validation failure.
        """
        upload_dir = Path(settings.UPLOAD_DIR) / "pdfs"
        upload_dir.mkdir(parents=True, exist_ok=True)

        unique_filename = f"{uuid.uuid4()}.pdf"
        destination_path = upload_dir / unique_filename

        # 1. Download PDF from URL and perform Step 1 & Step 2 validations
        try:
            async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT, follow_redirects=True) as client:
                response = await client.get(url)
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="The downloaded resource is not a valid PDF."
                    )

                # STEP 1: Validate HTTP Content-Type header
                content_type_header = response.headers.get("content-type", "").lower()
                if "application/pdf" not in content_type_header:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="The downloaded resource is not a valid PDF."
                    )

                content = response.content
                if len(content) > MAX_PDF_DOWNLOAD_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="Downloaded PDF size exceeds the maximum limit of 50MB."
                    )

                # STEP 2: Validate PDF binary signature (%PDF-)
                if not content.startswith(b"%PDF-"):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Downloaded file is not a valid PDF document."
                    )

                with destination_path.open("wb") as f:
                    f.write(content)

        except httpx.TimeoutException:
            if destination_path.exists():
                destination_path.unlink()
            raise HTTPException(
                status_code=status.HTTP_408_REQUEST_TIMEOUT,
                detail="PDF download request timed out. Please verify URL accessibility."
            )
        except httpx.RequestError:
            if destination_path.exists():
                destination_path.unlink()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unable to reach the provided URL for PDF download."
            )
        except HTTPException:
            if destination_path.exists():
                destination_path.unlink()
            raise
        except Exception as e:
            if destination_path.exists():
                destination_path.unlink()
            logger.error(f"Unexpected error downloading PDF: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred while downloading the PDF file."
            )

        # 3. Validate PDF document format using PyMuPDF (fitz)
        try:
            doc = fitz.open(str(destination_path))
            page_count = doc.page_count
            doc.close()
            if page_count == 0:
                destination_path.unlink()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Downloaded file is not a valid PDF document."
                )
        except Exception as e:
            if destination_path.exists():
                destination_path.unlink()
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Downloaded file is not a valid PDF document."
            )

        # 4. Reuse existing PDF pipeline for text extraction, chunking & FAISS vector indexing
        try:
            index_result = await index_pdf(PDFIndexRequestSchema(filename=unique_filename))

            return ImportAnalyzeResponseSchema(
                success=True,
                message="PDF imported and indexed successfully.",
                content_type="pdf",
                status="completed",
                filename=unique_filename,
                page_count=page_count,
                total_vectors=index_result.get("total_vectors"),
                index_location=index_result.get("index_location"),
                metadata_location=index_result.get("metadata_location")
            )
        except Exception as e:
            if destination_path.exists():
                destination_path.unlink()
            if isinstance(e, HTTPException):
                raise e
            logger.error(f"PDF indexing error during import: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to extract text and index the downloaded PDF document."
            )

    @staticmethod
    async def route_to_youtube(url: str) -> ImportAnalyzeResponseSchema:
        """
        YouTube import pipeline:
        1. Validates YouTube URL.
        2. Downloads video and extracts audio using yt-dlp.
        3. Cleans up temporary video files, keeping extracted audio in uploads/audio/.
        4. Returns metadata (title, duration, channel, audio_path).
        """
        if not is_valid_youtube_url(url):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid YouTube URL. Please provide a valid YouTube link."
            )

        audio_dir = Path(settings.UPLOAD_DIR) / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)

        audio_id = str(uuid.uuid4())
        outtmpl = str(audio_dir / f"{audio_id}.%(ext)s")

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': outtmpl,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'keepvideo': False,
        }

        try:
            def run_yt_dlp():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    return info

            loop = asyncio.get_running_loop()
            info_dict = await loop.run_in_executor(None, run_yt_dlp)

            if not info_dict:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Unable to fetch video metadata from YouTube."
                )

            # Resolve the saved audio file
            saved_audio_file = None
            possible_files = list(audio_dir.glob(f"{audio_id}.*"))

            for file_path in possible_files:
                if file_path.suffix.lower() in [".mp4", ".webm", ".mkv", ".mov", ".avi"]:
                    file_path.unlink(missing_ok=True)
                elif file_path.suffix.lower() in [".mp3", ".m4a", ".wav", ".ogg", ".opus"]:
                    saved_audio_file = file_path

            if not saved_audio_file or not saved_audio_file.exists():
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to extract audio from YouTube video."
                )

            relative_audio_path = f"uploads/audio/{saved_audio_file.name}"
            title = info_dict.get("title") or "YouTube Video"
            duration = info_dict.get("duration") or 0
            channel = info_dict.get("uploader") or info_dict.get("channel") or "Unknown Channel"

            return ImportAnalyzeResponseSchema(
                success=True,
                message="YouTube video downloaded successfully.",
                content_type="youtube",
                status="ready_for_transcription",
                title=title,
                duration=duration,
                channel=channel,
                audio_path=relative_audio_path
            )

        except yt_dlp.utils.DownloadError as e:
            err_msg = str(e).lower()
            if "private" in err_msg:
                detail = "This YouTube video is private."
            elif "removed" in err_msg or "not available" in err_msg:
                detail = "This YouTube video is unavailable or has been removed."
            elif "age" in err_msg or "sign in" in err_msg:
                detail = "This YouTube video is age-restricted or requires login."
            else:
                detail = "Failed to download YouTube video. Please check the URL and try again."

            logger.error(f"yt-dlp DownloadError: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=detail
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected YouTube import error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while processing the YouTube video."
            )

    @staticmethod
    async def route_to_audio(url: str) -> ImportAnalyzeResponseSchema:
        """Placeholder for Audio import pipeline."""
        return ImportAnalyzeResponseSchema(
            success=True,
            message="Import pipeline initialized.",
            content_type="audio",
            status="pending"
        )

    @classmethod
    async def import_and_analyze(cls, url: str, content_type: ContentTypeLiteral) -> ImportAnalyzeResponseSchema:
        """
        Main entry point for importing resources. Routes to specific handlers.
        """
        if content_type == "pdf":
            return await cls.route_to_pdf(url)
        elif content_type == "youtube":
            return await cls.route_to_youtube(url)
        elif content_type == "audio":
            return await cls.route_to_audio(url)
        else:
            raise ValueError(f"Unsupported content type: {content_type}")
