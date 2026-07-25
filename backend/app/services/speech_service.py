import os
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from faster_whisper import WhisperModel
from app.core.config import settings

logger = logging.getLogger(__name__)


class SpeechService:
    """
    Reusable Speech-to-Text Service using Faster-Whisper.
    Responsible ONLY for audio file transcription.
    """

    SUPPORTED_FORMATS = {
        ".mp3", ".wav", ".m4a", ".aac", ".flac",
        ".ogg", ".mp4", ".mov", ".avi", ".mkv", ".webm", ".opus"
    }

    def __init__(
        self,
        model_size: Optional[str] = None,
        device: Optional[str] = None,
        compute_type: Optional[str] = None,
    ):
        self.model_size = model_size or getattr(settings, "WHISPER_MODEL", "base")
        self.device = device or getattr(settings, "WHISPER_DEVICE", "cpu")
        self.compute_type = compute_type or getattr(settings, "WHISPER_COMPUTE_TYPE", "int8")
        self._model: Optional[WhisperModel] = None

    def _get_model(self) -> WhisperModel:
        if self._model is None:
            logger.info(f"Loading Faster-Whisper model '{self.model_size}' on device '{self.device}'...")
            try:
                self._model = WhisperModel(
                    self.model_size,
                    device=self.device,
                    compute_type=self.compute_type,
                )
            except Exception as e:
                logger.error(f"Failed to load Faster-Whisper model: {e}")
                if self.device != "cpu":
                    logger.info("Attempting fallback to CPU for Faster-Whisper model...")
                    try:
                        self._model = WhisperModel(
                            self.model_size,
                            device="cpu",
                            compute_type="int8",
                        )
                    except Exception as fallback_error:
                        logger.error(f"CPU fallback failed: {fallback_error}")
                        raise RuntimeError("Failed to load speech recognition model.") from fallback_error
                else:
                    raise RuntimeError("Failed to load speech recognition model.") from e
        return self._model

    def transcribe(self, audio_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Transcribe a local audio file into text with segment timing and language metadata.

        :param audio_path: Path to the local audio file (str or Path).
        :return: Dict with success flag, transcript, language, duration, segments, or error.
        """
        if not audio_path:
            return {
                "success": False,
                "error": "Audio file path was not provided.",
                "transcript": "",
                "language": None,
                "duration": 0,
                "segments": [],
            }

        path = Path(audio_path)

        if not path.exists() or not path.is_file():
            return {
                "success": False,
                "error": f"Audio file not found at path: '{audio_path}'",
                "transcript": "",
                "language": None,
                "duration": 0,
                "segments": [],
            }

        ext = path.suffix.lower()
        if ext not in self.SUPPORTED_FORMATS:
            supported_str = ", ".join(sorted(ext.lstrip(".") for ext in self.SUPPORTED_FORMATS))
            return {
                "success": False,
                "error": f"Unsupported audio format '{ext}'. Supported formats: {supported_str}",
                "transcript": "",
                "language": None,
                "duration": 0,
                "segments": [],
            }

        try:
            model = self._get_model()
        except Exception:
            return {
                "success": False,
                "error": "Failed to load speech recognition model.",
                "transcript": "",
                "language": None,
                "duration": 0,
                "segments": [],
            }

        try:
            segments_generator, info = model.transcribe(str(path), beam_size=5)

            segment_list: List[Dict[str, Any]] = []
            transcript_parts: List[str] = []

            for segment in segments_generator:
                text_clean = segment.text.strip()
                if text_clean:
                    transcript_parts.append(text_clean)
                segment_list.append(
                    {
                        "id": segment.id,
                        "start": round(segment.start, 2),
                        "end": round(segment.end, 2),
                        "text": text_clean,
                    }
                )

            full_transcript = " ".join(transcript_parts)

            return {
                "success": True,
                "transcript": full_transcript,
                "language": info.language if info else "unknown",
                "language_probability": (
                    round(info.language_probability, 4)
                    if info and hasattr(info, "language_probability") and info.language_probability is not None
                    else None
                ),
                "duration": (
                    round(info.duration, 2)
                    if info and hasattr(info, "duration") and info.duration is not None
                    else 0
                ),
                "segments": segment_list,
            }

        except Exception as e:
            logger.error(f"Error during transcription of '{audio_path}': {e}")
            return {
                "success": False,
                "error": "Transcription failed during processing.",
                "transcript": "",
                "language": None,
                "duration": 0,
                "segments": [],
            }


speech_service = SpeechService()
