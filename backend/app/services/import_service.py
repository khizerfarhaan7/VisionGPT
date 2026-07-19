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

import json
import faiss
from app.services.speech_service import speech_service
from app.core.rag import get_embedding_model

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
        3. Invokes reusable SpeechService to generate speech transcript.
        4. Chunks transcript text/segments into indexing chunks.
        5. Generates text embeddings and compiles local FAISS vector store.
        6. Persists metadata.json and FAISS index.
        7. Cleans up temporary video and audio files.
        8. Returns YouTube import response with vector store location & metadata.
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

        saved_audio_file = None

        def cleanup_temp_files():
            nonlocal saved_audio_file
            try:
                if saved_audio_file and saved_audio_file.exists():
                    saved_audio_file.unlink(missing_ok=True)
                for file_path in audio_dir.glob(f"{audio_id}.*"):
                    if file_path.exists():
                        file_path.unlink(missing_ok=True)
            except Exception as ce:
                logger.warning(f"Failed to clean up temporary YouTube files for {audio_id}: {ce}")

        # 1. Download video and extract audio
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

            # Resolve saved audio file & remove any temporary video files
            possible_files = list(audio_dir.glob(f"{audio_id}.*"))
            for file_path in possible_files:
                if file_path.suffix.lower() in [".mp4", ".webm", ".mkv", ".mov", ".avi"]:
                    file_path.unlink(missing_ok=True)
                elif file_path.suffix.lower() in [".mp3", ".m4a", ".wav", ".ogg", ".opus"]:
                    saved_audio_file = file_path

            if not saved_audio_file or not saved_audio_file.exists():
                cleanup_temp_files()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to extract audio from YouTube video."
                )

            title = info_dict.get("title") or "YouTube Video"
            duration = info_dict.get("duration") or 0
            channel = info_dict.get("uploader") or info_dict.get("channel") or "Unknown Channel"

        except yt_dlp.utils.DownloadError as e:
            cleanup_temp_files()
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
            cleanup_temp_files()
            raise
        except Exception as e:
            cleanup_temp_files()
            logger.error(f"Unexpected YouTube download error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while downloading the YouTube video."
            )

        # 2. Call SpeechService to transcribe audio
        try:
            transcribe_result = await loop.run_in_executor(
                None, speech_service.transcribe, str(saved_audio_file)
            )

            if not transcribe_result.get("success"):
                cleanup_temp_files()
                err_detail = transcribe_result.get("error") or "Speech transcription failed."
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Speech transcription error: {err_detail}"
                )

            transcript = transcribe_result.get("transcript", "").strip()
            segments = transcribe_result.get("segments", [])

            if not transcript:
                cleanup_temp_files()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No speech content or transcript could be extracted from the video."
                )

        except HTTPException:
            cleanup_temp_files()
            raise
        except Exception as e:
            cleanup_temp_files()
            logger.error(f"Speech transcription pipeline error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to transcribe audio from YouTube video."
            )

        # 3. Text Chunking, Embedding Generation & FAISS Indexing
        try:
            chunks = []
            if segments:
                chunk_index = 0
                current_chunk_segments = []
                current_word_count = 0
                target_min_words = 120
                target_max_words = 180

                for seg in segments:
                    text = seg.get("text", "").strip()
                    if not text:
                        continue
                    words = text.split()
                    word_count = len(words)
                    if current_word_count >= target_min_words and (current_word_count + word_count > target_max_words):
                        chunk_text = " ".join([s.get("text", "").strip() for s in current_chunk_segments])
                        start_time = float(current_chunk_segments[0].get("start", 0))
                        end_time = float(current_chunk_segments[-1].get("end", 0))
                        chunks.append({
                            "chunk_id": f"chunk_{chunk_index}",
                            "page": "youtube",
                            "start_time": round(start_time, 2),
                            "end_time": round(end_time, 2),
                            "text": chunk_text
                        })
                        chunk_index += 1
                        current_chunk_segments = []
                        current_word_count = 0
                    current_chunk_segments.append(seg)
                    current_word_count += word_count

                if current_chunk_segments:
                    chunk_text = " ".join([s.get("text", "").strip() for s in current_chunk_segments])
                    start_time = float(current_chunk_segments[0].get("start", 0))
                    end_time = float(current_chunk_segments[-1].get("end", 0))
                    chunks.append({
                        "chunk_id": f"chunk_{chunk_index}",
                        "page": "youtube",
                        "start_time": round(start_time, 2),
                        "end_time": round(end_time, 2),
                        "text": chunk_text
                    })

            if not chunks:
                words = transcript.split()
                chunk_size = 150
                for i in range(0, len(words), chunk_size):
                    chunk_words = words[i:i+chunk_size]
                    chunks.append({
                        "chunk_id": f"chunk_{len(chunks)}",
                        "page": "youtube",
                        "text": " ".join(chunk_words)
                    })

            if not chunks:
                cleanup_temp_files()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="YouTube transcript contains no valid text to index."
                )

            # Embedding generation using existing get_embedding_model
            model = get_embedding_model()
            sentences = [c["text"] for c in chunks]
            embeddings = model.encode(sentences, convert_to_numpy=True)

            dimension = int(embeddings.shape[1])
            total_vectors = int(embeddings.shape[0])

            index = faiss.IndexFlatL2(dimension)
            index.add(embeddings.astype("float32"))

            vector_store_dir = Path(settings.UPLOAD_DIR) / "vector_store" / audio_id
            vector_store_dir.mkdir(parents=True, exist_ok=True)

            index_path = vector_store_dir / "faiss.index"
            metadata_path = vector_store_dir / "metadata.json"

            faiss.write_index(index, str(index_path))

            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(chunks, f, ensure_ascii=False, indent=2)

        except HTTPException:
            cleanup_temp_files()
            raise
        except Exception as e:
            cleanup_temp_files()
            logger.error(f"YouTube indexing error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate embeddings and build vector store for YouTube video."
            )

        # 4. Clean up temporary video & audio files
        cleanup_temp_files()

        # 5. Return success response with metadata
        return ImportAnalyzeResponseSchema(
            success=True,
            message="YouTube video imported and indexed successfully.",
            content_type="youtube",
            status="completed",
            title=title,
            channel=channel,
            duration=int(round(duration)) if duration else 0,
            transcript_length=len(transcript),
            total_chunks=len(chunks),
            total_vectors=total_vectors,
            index_location=f"uploads/vector_store/{audio_id}/faiss.index",
            metadata_location=f"uploads/vector_store/{audio_id}/metadata.json"
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
