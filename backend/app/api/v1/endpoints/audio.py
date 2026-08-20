import os
import time
import logging
from pathlib import Path
import faiss
import json
from fastapi import APIRouter, HTTPException, status
import faster_whisper
import static_ffmpeg

from app.core.config import settings
from app.schemas.audio import (
    AudioTranscribeRequestSchema,
    AudioTranscribeResponseSchema,
    AudioChatRequestSchema,
    AudioChatResponseSchema
)
from app.core.rag import get_embedding_model, execute_local_rag

# Initialize static-ffmpeg to add binaries to PATH
static_ffmpeg.add_paths()

logger = logging.getLogger(__name__)
router = APIRouter()

from app.core.model_manager import model_manager

def get_whisper_model():
    """
    Retrieves the single managed Faster-Whisper model via ModelManager.
    """
    return model_manager.get_whisper_model(
        model_size="small",
        device=getattr(settings, "WHISPER_DEVICE", "cpu"),
        compute_type=getattr(settings, "WHISPER_COMPUTE_TYPE", "int8")
    )

def chunk_whisper_segments(segments_list, target_min_words=120, target_max_words=180) -> list:
    """
    Slices Whisper transcription segments into chunks of approximately 120-180 words, 
    preserving segment boundaries (which align with sentences/natural pauses).
    Assigns correct start_time and end_time to each chunk.
    """
    chunks = []
    current_chunk_segments = []
    current_word_count = 0
    chunk_index = 0

    for seg in segments_list:
        text = seg.text.strip()
        if not text:
            continue
            
        words = text.split()
        word_count = len(words)
        
        # If adding this segment exceeds target_max_words and we've reached min_words, finalize current chunk
        if current_word_count >= target_min_words and (current_word_count + word_count > target_max_words):
            chunk_text = " ".join([s.text.strip() for s in current_chunk_segments])
            start_time = float(current_chunk_segments[0].start)
            end_time = float(current_chunk_segments[-1].end)
            chunks.append({
                "chunk_id": f"chunk_{chunk_index}",
                "page": "audio",
                "start_time": round(start_time, 2),
                "end_time": round(end_time, 2),
                "text": chunk_text
            })
            chunk_index += 1
            current_chunk_segments = []
            current_word_count = 0
            
        current_chunk_segments.append(seg)
        current_word_count += word_count
        
    # Finalize the last chunk
    if current_chunk_segments:
        chunk_text = " ".join([s.text.strip() for s in current_chunk_segments])
        start_time = float(current_chunk_segments[0].start)
        end_time = float(current_chunk_segments[-1].end)
        chunks.append({
            "chunk_id": f"chunk_{chunk_index}",
            "page": "audio",
            "start_time": round(start_time, 2),
            "end_time": round(end_time, 2),
            "text": chunk_text
        })
        
    return chunks

@router.post("/transcribe", response_model=AudioTranscribeResponseSchema, status_code=status.HTTP_200_OK)
async def transcribe_audio(payload: AudioTranscribeRequestSchema):
    """
    Transcribe an uploaded audio/video file using faster-whisper.
    Automatically fallback to CPU if GPU fails.
    Failsafe: Auto-chunks and builds a local FAISS index for RAG queries.
    """
    filename = payload.filename
    safe_filename = os.path.basename(filename)
    audio_path = Path(settings.UPLOAD_DIR) / "audio" / safe_filename

    if not audio_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested audio file was not found in the uploads directory."
        )

    file_ext = audio_path.suffix.lower()
    temp_wav_path = None
    transcription_source = audio_path

    try:
        # If it is .mp4, extract audio to a temporary wav file using FFmpeg
        if file_ext == ".mp4":
            temp_wav_path = audio_path.with_name(f"{audio_path.stem}_extracted.wav")
            cmd = [
                "ffmpeg", "-y", "-i", str(audio_path),
                "-vn", "-ac", "1", "-ar", "16000",
                str(temp_wav_path)
            ]
            import subprocess
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"FFmpeg audio extraction failed: {result.stderr}")
                if temp_wav_path.exists():
                    temp_wav_path.unlink()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to extract audio track from MP4. Please verify the file contains a valid audio track."
                )
            transcription_source = temp_wav_path

        # Perform Whisper transcription and measure time
        start_time = time.time()
        model = get_whisper_model()
        
        # Transcribe with forced English language for accuracy and speed
        segments, info = model.transcribe(str(transcription_source), language="en", task="transcribe")
        
        # Exhaust the generator to perform transcription completely
        segments_list = list(segments)
        processing_time = time.time() - start_time
        
        # Stitch segments together to form a full transcript
        transcript = " ".join([segment.text for segment in segments_list]).strip()
        word_count = len(transcript.split())
        duration = info.duration
        
        # Build RAG indexes automatically
        metadata_chunks = chunk_whisper_segments(segments_list, target_min_words=120, target_max_words=180)
            
        # Create embeddings and build FAISS index
        audio_id = os.path.splitext(safe_filename)[0]
        vector_store_dir = Path(settings.UPLOAD_DIR) / "vector_store" / "audio" / audio_id
        vector_store_dir.mkdir(parents=True, exist_ok=True)
        
        if len(metadata_chunks) > 0:
            embed_model = get_embedding_model()
            sentences = [c["text"] for c in metadata_chunks]
            embeddings = embed_model.encode(sentences, convert_to_numpy=True)
            
            dimension = int(embeddings.shape[1])
            index = faiss.IndexFlatL2(dimension)
            index.add(embeddings.astype("float32"))
            
            faiss.write_index(index, str(vector_store_dir / "faiss.index"))
        else:
            # Empty index fallback
            dimension = 384  # Default dimension of bge-small-en-v1.5
            index = faiss.IndexFlatL2(dimension)
            faiss.write_index(index, str(vector_store_dir / "faiss.index"))

        with open(vector_store_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata_chunks, f, ensure_ascii=False, indent=2)

        return {
            "success": True,
            "transcript": transcript,
            "detected_language": "english",
            "duration": round(duration, 2),
            "processing_time": round(processing_time, 2),
            "word_count": word_count,
            "chunks": metadata_chunks
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to transcribe audio file")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transcription failed: {str(e)}"
        )
    finally:
        if temp_wav_path and temp_wav_path.exists():
            try:
                temp_wav_path.unlink()
            except Exception as cleanup_err:
                logger.warning(f"Failed to delete temporary audio file {temp_wav_path}: {cleanup_err}")

@router.post("/chat", response_model=AudioChatResponseSchema, status_code=status.HTTP_200_OK)
async def chat_audio(payload: AudioChatRequestSchema):
    """
    Perform local RAG chat over the transcribed audio text using FAISS vector retrieval and local Ollama model.
    """
    safe_filename = os.path.basename(payload.filename)
    audio_id = os.path.splitext(safe_filename)[0]
    
    vector_store_dir = Path(settings.UPLOAD_DIR) / "vector_store" / "audio" / audio_id

    system_prompt = (
        "You are a highly precise AI assistant answering questions based solely on the provided transcript of an audio recording.\n"
        "Follow these strict directives:\n"
        "1. Base your answer ONLY on the provided context transcript. Do not assume, extrapolate, or invent facts. Never hallucinate.\n"
        "2. If the answer cannot be determined from the transcript context, state clearly and concisely that the information is not present in the audio recording.\n"
        "3. Ignore obvious speech-to-text transcription mistakes (e.g. typos, homophones, phonetic anomalies) when the intended meaning remains clear.\n"
        "4. Keep your answers concise yet complete. Prefer structure and bullet lists when summarizing or listing items.\n"
        "5. If a section of the transcript appears fragmented, unclear, or of poor quality, mention this uncertainty in your response.\n"
        "6. Do not reference internal components, vector indexes, FAISS, embeddings, or technical systems in your answers."
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
